#!/usr/bin/env bash
# Guardián de red de homelab-01. Lo corre un timer de systemd cada minuto.
#
# Por qué existe: el servidor depende de un WiFi USB viejo (RTL8187B) que lo ha
# dejado horas sin red sin nadie cerca para reiniciarlo. Este script nota el
# corte y prueba arreglarlo solo, de lo más suave a lo más fuerte, anotando cada
# paso para poder explicar después qué pasó.
#
# Distingue tres problemas distintos (y solo actúa en los que puede arreglar):
#   - no responde el router (gateway)     -> es NUESTRO enlace: escalera de arreglos.
#   - responde el router pero no internet -> está AFUERA (router o proveedor):
#                                            reiniciar nuestro WiFi no sirve; solo anota.
#   - hay internet pero Tailscale no anda -> reinicia tailscaled.
#
# Escalera, por minutos SEGUIDOS sin router (ajustable en /etc/default/vigia-red):
#   PASO1  reconectar el WiFi; si quedó sin conexión (típico al arrancar), buscar
#          redes y conectar a la mejor guardada  (nmcli device connect)
#   PASO2  reiniciar NetworkManager
#   PASO3  "desenchufar y enchufar" el USB del adaptador (por software)
#   PASO4  probar las otras redes WiFi guardadas que estén al alcance
#   REINICIO  último recurso: reiniciar el servidor. Solo si pasó REINICIO_MIN,
#          el equipo lleva más de GRACIA_MIN encendido (evita bucles de reinicio)
#          y no reinició por esto en las últimas REINICIO_CADA_H horas.
# Los pasos 1-4 se repiten en ciclo mientras siga caído.
#
# Además deja un LATIDO cada minuto: si el servidor muere de golpe, el último
# latido dice a qué hora (lo lee postmortem-arranque al volver).
set -uo pipefail
export LC_ALL=C

[[ -r /etc/default/vigia-red ]] && . /etc/default/vigia-red
PASO1="${VIGIA_PASO1:-2}"
PASO2="${VIGIA_PASO2:-6}"
PASO3="${VIGIA_PASO3:-10}"
PASO4="${VIGIA_PASO4:-14}"
CICLO="${VIGIA_CICLO:-15}"
REINICIO_MIN="${VIGIA_REINICIO_MIN:-30}"          # 0 = nunca reiniciar
REINICIO_CADA_H="${VIGIA_REINICIO_CADA_H:-6}"
GRACIA_MIN="${VIGIA_GRACIA_MIN:-20}"
TAILSCALE_MIN="${VIGIA_TAILSCALE_MIN:-3}"          # 0 = no tocar tailscaled
DESTINOS="${VIGIA_DESTINOS:-1.1.1.1 8.8.8.8}"
ESTADO_DIR="${VIGIA_ESTADO_DIR:-/var/lib/vigia-red}"
LOG="${VIGIA_LOG:-/var/log/homelab/vigia-red.log}"
# Para las pruebas: permite reemplazar los comandos que cambian cosas.
NMCLI="${VIGIA_NMCLI:-nmcli}"
SYSTEMCTL="${VIGIA_SYSTEMCTL:-systemctl}"
TAILSCALE="${VIGIA_TAILSCALE:-tailscale}"
SYSFS="${VIGIA_SYSFS:-/sys}"
UPTIME_F="${VIGIA_UPTIME:-/proc/uptime}"
ESPERA="${VIGIA_ESPERA:-5}"   # segundos entre buscar redes y conectar (0 en las pruebas)

mkdir -p "$ESTADO_DIR" "$(dirname "$LOG")"
F_FALLAS="$ESTADO_DIR/minutos-sin-router"
F_DESDE="$ESTADO_DIR/sin-router-desde"
F_AFUERA="$ESTADO_DIR/sin-internet-desde"
F_TS="$ESTADO_DIR/minutos-sin-tailscale"
F_REINICIO="$ESTADO_DIR/ultimo-reinicio"
F_LATIDO="$ESTADO_DIR/latido"

ahora_txt() { date '+%Y-%m-%d %H:%M:%S'; }
anotar() {
  printf '%s %s\n' "$(ahora_txt)" "$*" >> "$LOG"
  logger -t vigia-red -- "$*" 2>/dev/null || true
}
leer() { cat "$1" 2>/dev/null || echo "${2:-0}"; }

placa_wifi() { $NMCLI -t -f DEVICE,TYPE device 2>/dev/null | awk -F: '$2=="wifi"{print $1; exit}'; }
gateway()    { ip -4 route show default 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="via"){print $(i+1); exit}}'; }
llega()      { [[ -n "${1:-}" ]] && ping -c 2 -W 3 -q "$1" >/dev/null 2>&1; }
hay_internet() { local d; for d in $DESTINOS; do llega "$d" && return 0; done; return 1; }
minutos_encendido() { awk '{print int($1/60)}' "$UPTIME_F"; }

# --- Latido ------------------------------------------------------------------------
ahora_txt > "$F_LATIDO"

PLACA="$(placa_wifi)"
GW="$(gateway)"
fallas="$(leer "$F_FALLAS")"

# ===================================================================================
# 1. El router responde: nuestro enlace está bien
# ===================================================================================
if llega "$GW"; then
  if [[ "$fallas" -gt 0 ]]; then
    anotar "RECUPERADO: el router responde de nuevo tras ${fallas} min sin red (desde $(leer "$F_DESDE" '?')). Placa: ${PLACA:-?}, gateway: $GW."
  fi
  echo 0 > "$F_FALLAS"; rm -f "$F_DESDE"

  if hay_internet; then
    if [[ -f "$F_AFUERA" ]]; then
      anotar "RECUPERADO: volvió internet (afuera estaba caído desde $(leer "$F_AFUERA"))."
      rm -f "$F_AFUERA"
    fi
    # --- Tailscale: hay internet, ¿anda la red privada? ----------------------------
    if [[ "$TAILSCALE_MIN" -gt 0 ]] && command -v "$TAILSCALE" >/dev/null 2>&1; then
      estado_ts="$($TAILSCALE status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState",""))' 2>/dev/null || true)"
      if [[ "$estado_ts" == "Running" ]]; then
        [[ "$(leer "$F_TS")" -gt 0 ]] && anotar "RECUPERADO: Tailscale volvió a Running."
        echo 0 > "$F_TS"
      else
        ts=$(( $(leer "$F_TS") + 1 )); echo "$ts" > "$F_TS"
        if [[ "$ts" -eq "$TAILSCALE_MIN" ]] || [[ "$ts" -gt "$TAILSCALE_MIN" && $(( (ts - TAILSCALE_MIN) % 10 )) -eq 0 ]]; then
          anotar "TAILSCALE: hay internet pero Tailscale está '${estado_ts:-sin respuesta}' hace ${ts} min. Reinicio tailscaled."
          $SYSTEMCTL restart tailscaled || anotar "  falló el reinicio de tailscaled"
        fi
      fi
    fi
  elif [[ ! -f "$F_AFUERA" ]]; then
    ahora_txt > "$F_AFUERA"
    anotar "SIN INTERNET pero el router responde: el problema está AFUERA (router o proveedor). No se toca nada."
  fi
  exit 0
fi

# ===================================================================================
# 2. El router no responde: el problema es nuestro enlace
# ===================================================================================
fallas=$((fallas + 1))
echo "$fallas" > "$F_FALLAS"
[[ -f "$F_DESDE" ]] || ahora_txt > "$F_DESDE"
paso=$(( (fallas - 1) % CICLO + 1 ))

if [[ "$fallas" -eq 1 ]]; then
  anotar "SIN RED: el router (${GW:-sin ruta por defecto}) no responde. Placa: ${PLACA:-ninguna}. Estado: $($NMCLI -t -f DEVICE,STATE device 2>/dev/null | grep -E "^${PLACA:-x}:" || echo '?')"
fi

# --- Último recurso: reiniciar ------------------------------------------------------
if [[ "$REINICIO_MIN" -gt 0 && "$fallas" -ge "$REINICIO_MIN" ]]; then
  enc="$(minutos_encendido)"
  ult="$(leer "$F_REINICIO")"
  hace_h=$(( ( $(date +%s) - ult ) / 3600 ))
  if [[ "$enc" -lt "$GRACIA_MIN" ]]; then
    : # recién arrancó: le damos tiempo a la red antes de pensar en reiniciar
  elif [[ "$ult" -gt 0 && "$hace_h" -lt "$REINICIO_CADA_H" ]]; then
    [[ $(( fallas % 30 )) -eq 0 ]] && anotar "REINICIO EVITADO: ya reinicié por esto hace ${hace_h} h (límite: uno cada ${REINICIO_CADA_H} h). Sigo con la escalera."
  else
    date +%s > "$F_REINICIO"
    anotar "REINICIO (último recurso): ${fallas} min sin router y la escalera no alcanzó. Reinicio el servidor."
    sync
    $SYSTEMCTL reboot
    exit 0
  fi
fi

# --- Escalera ------------------------------------------------------------------------
if [[ "$paso" -eq "$PASO1" && -n "$PLACA" ]]; then
  estado_placa="$($NMCLI -t -f DEVICE,STATE device 2>/dev/null | awk -F: -v d="$PLACA" '$1==d{print $2}')"
  if [[ "$estado_placa" == "connected" ]]; then
    anotar "PASO 1 (${fallas} min): el WiFi dice 'connected' pero el router no responde: reconectar ($PLACA)."
    $NMCLI device reconnect "$PLACA" >/dev/null 2>&1 || anotar "  no se pudo reconectar $PLACA"
  else
    # Sin conexión activa (típico al arrancar, si el router tardó más que el
    # servidor): buscar redes de nuevo y dejar que NM elija la mejor guardada.
    anotar "PASO 1 (${fallas} min): el WiFi está '${estado_placa:-?}': busco redes y conecto a la mejor guardada ($PLACA)."
    $NMCLI device wifi rescan ifname "$PLACA" >/dev/null 2>&1 || true
    sleep "$ESPERA"
    $NMCLI device connect "$PLACA" >/dev/null 2>&1 || anotar "  todavía no hay ninguna red guardada al alcance"
  fi

elif [[ "$paso" -eq "$PASO2" ]]; then
  anotar "PASO 2 (${fallas} min): reiniciar NetworkManager."
  $SYSTEMCTL restart NetworkManager || anotar "  falló el reinicio de NetworkManager"

elif [[ "$paso" -eq "$PASO3" ]]; then
  if [[ -n "$PLACA" && -e "$SYSFS/class/net/$PLACA/device" ]]; then
    # /sys/class/net/<placa>/device -> .../X-Y/X-Y:1.0 ; el dispositivo USB es X-Y
    usbdir="$(dirname "$(readlink -f "$SYSFS/class/net/$PLACA/device")")"
    if [[ -w "$usbdir/authorized" ]]; then
      anotar "PASO 3 (${fallas} min): desenchufar y enchufar por software el USB del adaptador ($(basename "$usbdir"))."
      echo 0 > "$usbdir/authorized"; sleep "$ESPERA"; echo 1 > "$usbdir/authorized"
    else
      anotar "PASO 3 (${fallas} min): $PLACA no es un USB reseteable; reinicio NetworkManager."
      $SYSTEMCTL restart NetworkManager || true
    fi
  else
    anotar "PASO 3 (${fallas} min): no hay placa WiFi visible (¿se desconectó el USB?). Reinicio NetworkManager."
    $SYSTEMCTL restart NetworkManager || true
  fi

elif [[ "$paso" -eq "$PASO4" && -n "$PLACA" ]]; then
  # Otras redes guardadas (con autoconexión) que estén al alcance ahora.
  activa="$($NMCLI -t -f NAME,DEVICE connection show --active 2>/dev/null | awk -F: -v d="$PLACA" '$2==d{print $1}')"
  visibles="$($NMCLI -t -f SSID device wifi list ifname "$PLACA" --rescan yes 2>/dev/null | sort -u)"
  probo=0
  while IFS=: read -r nombre tipo auto; do
    [[ "$tipo" == "802-11-wireless" && "$auto" == "yes" && "$nombre" != "$activa" ]] || continue
    ssid="$($NMCLI -g 802-11-wireless.ssid connection show "$nombre" 2>/dev/null)"
    grep -Fxq "$ssid" <<<"$visibles" || continue
    anotar "PASO 4 (${fallas} min): pruebo otra red guardada al alcance: \"$nombre\"."
    probo=1
    if $NMCLI --wait 30 connection up "$nombre" ifname "$PLACA" >/dev/null 2>&1 && llega "$(gateway)"; then
      anotar "  conectado a \"$nombre\": el router responde."
      break
    fi
  done < <($NMCLI -t -f NAME,TYPE,AUTOCONNECT connection show 2>/dev/null)
  [[ "$probo" -eq 0 ]] && anotar "PASO 4 (${fallas} min): no hay otras redes guardadas al alcance."
fi
exit 0
