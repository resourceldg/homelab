#!/usr/bin/env bash
# Dice cuál es la mejor forma de conectarse a homelab-01 AHORA, y te imprime el
# comando listo para pegar.
#
# Por qué así: al server se puede llegar por varios caminos (nombre MagicDNS, IP
# del tailnet, IP de la LAN) y cuál sirve cambia según dónde estés parado y qué
# esté roto ese día. Cuando algo falla, el error que ves —"timed out", "host
# desconocido"— es el mismo para causas muy distintas: Tailscale apagado, la
# máquina sin aprobar, el server caído, el firewall apuntando a otra red. Este
# script prueba los caminos en orden, dice cuál anda y, sobre todo, POR QUÉ los
# otros no.
#
# Se corre EN TU COMPUTADORA, no en el servidor.
#
#   como-conectar                    prueba todo y recomienda
#   como-conectar jessi              además arma el comando con ese usuario
#   como-conectar jessi --equipo 01  y le suma el túnel a tu Node-RED (y tu web)
#   como-conectar --ayuda
#
# En Windows corre sobre Git Bash o WSL; en PowerShell pelado, no.
set -euo pipefail

# --- a dónde queremos llegar (overridable por entorno) ----------------------
NOMBRE="${HOMELAB_NOMBRE:-homelab-01.tail4eda13.ts.net}"
IP_TAILNET="${HOMELAB_IP_TAILNET:-100.110.123.76}"
# IP de LAN: solo sirve si estás en la misma casa que el server. Cambió con cada
# mudanza de red (192.168.100.x → 192.168.0.x → 192.168.8.x); si vuelve a
# cambiar, se actualiza acá o se pasa por entorno (varias, separadas por espacio).
IPS_LAN="${HOMELAB_IPS_LAN:-192.168.8.144}"
PUERTO="${HOMELAB_PUERTO:-22}"

USUARIO="tu-usuario"
EQUIPO=""

# Puertos de cada equipo EN EL SERVIDOR: Node-RED y (si tiene) su web. Es la
# misma tabla de docs/handbook/guia-equipo.md; si se suma un equipo, van en los
# dos lados. En TU compu siempre quedan en localhost:1880 y localhost:8080.
declare -A NODERED=( [01]=1880 [03]=1882 [04]=1884 )
declare -A WEB=( [03]=8083 [04]=8084 )

# --- salida ----------------------------------------------------------------
if [[ -t 1 ]]; then
  BOLD=$'\e[1m'; RED=$'\e[31m'; GRN=$'\e[32m'; YLW=$'\e[33m'; BLU=$'\e[36m'; DIM=$'\e[2m'; RST=$'\e[0m'
else
  BOLD=""; RED=""; GRN=""; YLW=""; BLU=""; DIM=""; RST=""
fi
say()  { printf '%s\n' "${BLU}${BOLD}==>${RST} ${BOLD}$*${RST}"; }
ok()   { printf '%s\n' "${GRN}  ✓${RST} $*"; }
warn() { printf '%s\n' "${YLW}  !${RST} $*"; }
bad()  { printf '%s\n' "${RED}  ✗${RST} $*"; }
nota() { printf '%s\n' "${DIM}    $*${RST}"; }

ayuda() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ayuda|-h|--help) ayuda ;;
    --equipo)          EQUIPO="${2:-}"; shift ;;
    --equipo=*)        EQUIPO="${1#*=}" ;;
    -*)                echo "opción desconocida: $1 (probá --ayuda)" >&2; exit 2 ;;
    *)                 USUARIO="$1" ;;
  esac
  shift
done
# "3", "03" y "equipo-03" son el mismo equipo.
EQUIPO="${EQUIPO#equipo-}"
[[ "$EQUIPO" =~ ^[0-9]+$ ]] && EQUIPO="$(printf '%02d' "$((10#$EQUIPO))")"
if [[ -n "$EQUIPO" && -z "${NODERED[$EQUIPO]:-}" ]]; then
  echo "no conozco los puertos del equipo «$EQUIPO» (equipos: ${!NODERED[*]})" >&2
  exit 2
fi

# --- sondas -----------------------------------------------------------------
# TCP sin depender de nc/netcat: bash abre el socket solo.
tcp_abierto() { # tcp_abierto host puerto
  timeout 5 bash -c "cat < /dev/null > /dev/tcp/$1/$2" 2>/dev/null
}

latencia_ms() { # latencia_ms host  -> "23.4" o vacío
  ping -c 2 -W 2 "$1" 2>/dev/null | awk -F'/' '/^rtt|^round-trip/ {printf "%.0f", $5}'
}

resuelve() { # resuelve nombre -> imprime la IP o vacío
  getent hosts "$1" 2>/dev/null | awk '{print $1; exit}'
}

# --- 1. Tailscale en tu máquina --------------------------------------------
say "Revisando Tailscale en tu computadora"
TS_OK=0
if ! command -v tailscale >/dev/null 2>&1; then
  bad "Tailscale no está instalado."
  nota "Instalalo: https://tailscale.com/download — es el paso 2 de la guía."
elif ! tailscale status >/dev/null 2>&1; then
  bad "Tailscale está instalado pero apagado (o sin iniciar sesión)."
  nota "Abrí la app y tocá 'Log in', o corré: sudo tailscale up"
else
  ok "Tailscale activo, tu computadora está en la red."
  TS_OK=1
fi

# --- 2. ¿Cómo ve al server el tailnet? -------------------------------------
RUTA=""
if [[ "$TS_OK" == 1 ]]; then
  linea="$(tailscale status 2>/dev/null | grep -F "$IP_TAILNET" || true)"
  if [[ -z "$linea" ]]; then
    warn "El server no aparece en tu tailnet."
    nota "Puede que tu máquina todavía no esté aprobada. Avisale al profe."
  elif grep -qi "offline" <<<"$linea"; then
    bad "El server figura OFFLINE en el tailnet."
    nota "No es tu conexión: el servidor no está saliendo a la red."
  else
    if grep -qi "relay" <<<"$linea"; then
      RUTA="relay"
      warn "Conexión por relay ($(sed -n 's/.*relay "\([^"]*\)".*/\1/p' <<<"$linea")), no directa: va a andar más lento."
      nota "Suele pasar cuando el server rebota entre Ethernet y WiFi."
    else
      RUTA="directa"
      ok "Conexión directa con el server."
    fi
  fi
fi

# --- 3. Probar cada camino --------------------------------------------------
say "Probando los caminos al servidor"
GANADOR=""; GANADOR_POR=""

probar() { # probar destino etiqueta
  local destino="$1" etiqueta="$2" ip lat
  if [[ "$destino" =~ ^[0-9]+\. ]]; then
    ip="$destino"
  else
    ip="$(resuelve "$destino")"
    if [[ -z "$ip" ]]; then
      bad "$etiqueta — el nombre no resuelve."
      return 1
    fi
  fi
  if ! tcp_abierto "$destino" "$PUERTO"; then
    lat="$(latencia_ms "$ip" || true)"
    if [[ -n "$lat" ]]; then
      bad "$etiqueta — responde al ping pero el puerto $PUERTO está cerrado."
      nota "El server está vivo; es el firewall o el sshd el que no te deja."
    else
      bad "$etiqueta — no responde."
    fi
    return 1
  fi
  lat="$(latencia_ms "$ip" || true)"
  ok "$etiqueta — puerto $PUERTO abierto${lat:+, ${lat} ms}"
  [[ -z "$GANADOR" ]] && { GANADOR="$destino"; GANADOR_POR="$etiqueta"; }
  return 0
}

# Orden de preferencia: el nombre primero, porque sobrevive a que el server
# cambie de IP. La IP del tailnet es el plan B cuando MagicDNS no resuelve.
[[ "$TS_OK" == 1 ]] && probar "$NOMBRE"     "nombre del tailnet" || true
[[ "$TS_OK" == 1 ]] && probar "$IP_TAILNET" "IP del tailnet"     || true
for ip in $IPS_LAN; do
  probar "$ip" "LAN $ip" || true
done

# --- 4. Veredicto -----------------------------------------------------------
echo
if [[ -z "$GANADOR" ]]; then
  say "${RED}Ningún camino funciona ahora${RST}"
  if [[ "$TS_OK" != 1 ]]; then
    echo "  Arrancá por Tailscale: sin eso no hay forma de entrar desde afuera."
  else
    echo "  Tailscale anda, pero el server no contesta por ningún lado."
    echo "  Probablemente esté caído o sin red. Avisale al profe."
  fi
  exit 1
fi

say "Conectate así"
echo
# Solo Node-RED y la web viajan por túnel. MQTT no: las placas (y MQTT Explorer)
# entran por el Funnel, sin SSH.
TUNEL=""
if [[ -n "$EQUIPO" ]]; then
  TUNEL="-L 1880:localhost:${NODERED[$EQUIPO]} "
  [[ -n "${WEB[$EQUIPO]:-}" ]] && TUNEL+="-L 8080:localhost:${WEB[$EQUIPO]} "
fi
echo "    ssh ${TUNEL}${USUARIO}@${GANADOR}"
echo
nota "camino elegido: ${GANADOR_POR}${RUTA:+ (${RUTA})}"
if [[ "$USUARIO" == "tu-usuario" ]]; then
  nota "pasale tu usuario para que salga listo: $(basename "$0") jessi"
fi
if [[ -n "$EQUIPO" ]]; then
  nota "dejá esa ventana abierta: el túnel vive mientras siga abierta."
  nota "después, en el navegador: http://localhost:1880 (Node-RED)"
  if [[ -n "${WEB[$EQUIPO]:-}" ]]; then
    nota "                         http://localhost:8080 (tu web)"
  fi
else
  nota "para llegar a tu Node-RED, sumá tu equipo: $(basename "$0") ${USUARIO} --equipo 03"
fi
