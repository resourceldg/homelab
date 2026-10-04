#!/usr/bin/env bash
# Mide los uplinks del servidor y elige el mejor. Corre EN EL SERVIDOR.
#
# Por qué así: el estado del link y el nivel de señal MIENTEN. Este server
# estuvo colgado de un WiFi que reportaba señal excelente (-31 dBm, calidad
# 70/70) mientras perdía el 57% de los paquetes contra su propio gateway, con
# 8964 reintentos de transmisión. NetworkManager veía "conectado" y se quedaba
# ahí. La única señal honesta es medir pérdida y latencia REALES por cada
# interfaz, que es lo que hace esto.
#
# Qué NO hace: bajar interfaces ni reconectar nada. Solo reordena la preferencia
# de NetworkManager (métrica de ruta y prioridad de autoconexión) para que el
# mejor uplink gane. Es deliberado: cortar el uplink activo de una máquina a la
# que entrás por red es la forma más rápida de quedarte afuera.
#
#   elegir-uplink              mide y muestra el ranking; NO toca nada
#   elegir-uplink --aplicar    además hace que gane el mejor
#   elegir-uplink --pings N    cuántos pings por interfaz (default 20)
#   elegir-uplink --ayuda
set -euo pipefail

# El server corre en locale es_AR: sin esto, ping y awk emiten "1,0" y toda
# comparación numérica se corta en la coma. Solo el separador decimal, para no
# tocar la codificación del texto.
export LC_NUMERIC=C

PINGS="${UPLINK_PINGS:-20}"
APLICAR=0
# Por encima de esta pérdida el enlace se considera degradado aunque "funcione".
PERDIDA_MALA="${UPLINK_PERDIDA_MALA:-20}"

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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ayuda|-h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --aplicar)         APLICAR=1 ;;
    --pings)           PINGS="${2:-}"; shift ;;
    --pings=*)         PINGS="${1#*=}" ;;
    *)                 echo "opción desconocida: $1 (probá --ayuda)" >&2; exit 2 ;;
  esac
  shift
done
[[ "$PINGS" =~ ^[0-9]+$ ]] && [ "$PINGS" -ge 4 ] || { echo "--pings debe ser un entero >= 4" >&2; exit 2; }

sudo_si_hace_falta() { if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo -n "$@"; fi; }

# --- candidatos: interfaces físicas, sin lo virtual --------------------------
candidatos() {
  local d t
  while IFS=: read -r d t _; do
    case "$d" in
      lo|tailscale0|docker*|veth*|br-*) continue ;;
    esac
    case "$t" in
      ethernet|wifi) printf '%s %s\n' "$d" "$t" ;;
    esac
  done < <(nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null)
}

# Un solo comando y una sola línea: si emitiera dos, el `| head -1` del llamador
# le cerraría el pipe al segundo y SIGPIPE + pipefail matarían el script.
gateway_de() { # gateway_de iface -> IP del gateway que usa esa interfaz
  ip route show default 2>/dev/null \
    | awk -v d="$1" '$0 ~ ("dev " d " ") || $0 ~ ("dev " d "$") {
        for (i = 1; i <= NF; i++) if ($i == "via") { print $(i+1); exit }
      }'
}

# Mide contra el gateway propio: aísla el enlace de cualquier problema de
# internet aguas arriba. Si acá ya hay pérdida, el enlace está mal.
medir() { # medir iface gw -> "perdida rtt jitter"
  local out
  out="$(ping -I "$1" -c "$PINGS" -i 0.3 -W 2 "$2" 2>/dev/null || true)"
  local p r j
  p="$(awk -F',' '/packet loss/ {gsub(/[^0-9.]/,"",$3); print $3+0; exit}' <<<"$out")"
  r="$(awk -F'/' '/^rtt|^round-trip/ {printf "%.1f", $5; exit}' <<<"$out")"
  j="$(awk -F'/' '/^rtt|^round-trip/ {printf "%.1f", $7; exit}' <<<"$out")"
  printf '%s %s %s' "${p:-100}" "${r:-0}" "${j:-0}"
}

# --- medición ----------------------------------------------------------------
say "Midiendo cada uplink (${PINGS} pings contra su propio gateway)"
RANKING=""   # "puntaje|iface|tipo|perdida|rtt|jitter|conexion"
ACTIVA="$(ip route show default | awk '{for(i=1;i<=NF;i++) if($i=="dev") print $(i+1); exit}')"

while read -r dev tipo; do
  [[ -z "$dev" ]] && continue
  estado="$(nmcli -t -f GENERAL.STATE device show "$dev" 2>/dev/null | cut -d: -f2- || true)"
  conn="$(nmcli -t -f GENERAL.CONNECTION device show "$dev" 2>/dev/null | cut -d: -f2- || true)"

  if ! ip link show "$dev" 2>/dev/null | grep -q "LOWER_UP"; then
    bad "$dev ($tipo) — sin enlace físico. ${estado:+[$estado]}"
    continue
  fi
  gw="$(gateway_de "$dev")"
  if [[ -z "$gw" ]]; then
    bad "$dev ($tipo) — enlace arriba pero sin gateway (no rutea)."
    continue
  fi

  read -r perdida rtt jitter <<<"$(medir "$dev" "$gw")"
  # Puntaje: la pérdida manda; la latencia y el jitter desempatan. Con enlace
  # cableado sumamos un poco: no sufre interferencia.
  puntaje="$(awk -v p="$perdida" -v r="$rtt" -v j="$jitter" -v t="$tipo" \
    'BEGIN{s=(100-p)*10 - r - j*2; if(t=="ethernet") s+=25; printf "%.0f", s}')"

  marca=""; [[ "$dev" == "$ACTIVA" ]] && marca=" ${DIM}(en uso)${RST}"
  linea="$dev ($tipo) — pérdida ${perdida}%, rtt ${rtt} ms, jitter ${jitter} ms${marca}"
  if awk "BEGIN{exit !($perdida >= $PERDIDA_MALA)}"; then
    bad "$linea"
    nota "degradado: más de ${PERDIDA_MALA}% de pérdida contra su propio gateway"
  elif awk "BEGIN{exit !($perdida > 0)}"; then
    warn "$linea"
  else
    ok "$linea"
  fi
  RANKING+="${puntaje}|${dev}|${tipo}|${perdida}|${rtt}|${jitter}|${conn}"$'\n'
done < <(candidatos)

[[ -z "$RANKING" ]] && { echo; bad "No hay ningún uplink usable."; exit 1; }

MEJOR="$(sort -t'|' -k1 -rn <<<"$RANKING" | head -1)"
IFS='|' read -r m_pts m_dev m_tipo m_perdida _ _ m_conn <<<"$MEJOR"

echo
say "El mejor uplink es: ${m_dev} (${m_tipo})"
if awk "BEGIN{exit !($m_perdida >= $PERDIDA_MALA)}"; then
  warn "Pero pierde ${m_perdida}% de los paquetes: es el mejor de los malos."
  nota "Revisá el enlace físico. Ningún ajuste de software arregla esto."
fi

# --- anomalía que vale la pena gritar ----------------------------------------
while IFS=: read -r nombre prio; do
  [[ -z "$nombre" ]] && continue
  if [ "${prio:-0}" -le -100 ] 2>/dev/null; then
    warn "El perfil «$nombre» tiene prioridad ${prio}: nunca va a ganar aunque funcione."
  fi
done < <(nmcli -t -f NAME,AUTOCONNECT-PRIORITY connection show 2>/dev/null)

# --- aplicar ------------------------------------------------------------------
if [[ "$APLICAR" != 1 ]]; then
  echo
  nota "esto fue solo un diagnóstico; para aplicarlo: $(basename "$0") --aplicar"
  exit 0
fi
if [[ -z "$m_conn" ]]; then
  echo; bad "El mejor uplink no tiene un perfil de NetworkManager asociado; no hay qué ajustar."
  exit 1
fi

echo
say "Aplicando la preferencia"
# Métrica más baja = ruta preferida. Solo tocamos preferencias: no bajamos ni
# reconectamos nada, así el uplink en uso nunca se corta bajo nuestros pies.
i=0
while IFS='|' read -r _ dev _ _ _ _ conn; do
  [[ -z "$conn" ]] && continue
  metrica=$((100 + i * 100)); prioridad=$((50 - i * 10))
  sudo_si_hace_falta nmcli connection modify "$conn" \
    ipv4.route-metric "$metrica" connection.autoconnect-priority "$prioridad" 2>/dev/null \
    && ok "$conn → métrica $metrica, prioridad $prioridad" \
    || warn "no pude modificar «$conn»"
  i=$((i + 1))
done < <(sort -t'|' -k1 -rn <<<"$RANKING")

echo
nota "los cambios rigen en la próxima reconexión de cada perfil."
nota "para que tomen efecto ya: sudo nmcli connection up \"$m_conn\""
nota "(eso sí corta un instante la red; hacelo con acceso por consola a mano)"
