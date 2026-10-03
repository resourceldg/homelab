#!/usr/bin/env bash
# Vigila homelab-01 y, cuando vuelve después de una caída, averigua POR QUÉ se
# cayó y deja un informe. Corre EN TU COMPUTADORA (no en el servidor).
#
# Por qué así: cuando el servidor se cae, no se le puede instalar nada ni
# preguntarle nada. Lo único posible es esperar a que vuelva y, apenas vuelve,
# leer sus registros antes de que se pierdan o se mezclen con los nuevos. Este
# script hace exactamente eso, solo, y no depende de que haya alguien mirando.
#
# Cómo decide la causa: junta las pistas del arranque anterior y de la ventana
# de la caída (si se reinició, si el apagado fue ordenado o de golpe, si fue la
# actualización automática, si se desconectó el WiFi USB, si se quedó sin
# memoria o se recalentó) y las ordena de más a menos probable. Las pistas crudas
# van al final del informe, para revisarlas a mano.
#
#   diagnosticar-caida              chequea una vez y explica qué ve
#   diagnosticar-caida --cron       modo silencioso para cron (cada 5 min)
#   diagnosticar-caida --desde "2026-10-03 12:30"   marca a mano el inicio de una caída
#   diagnosticar-caida --ayuda
#
# Instalación (una vez, en tu compu):
#   crontab -e    y agregar:
#   */5 * * * * /home/zen/homelab/scripts/diagnosticar-caida.sh --cron
#
# Los informes quedan en ~/homelab-reportes/caida-<fecha>.md
set -euo pipefail

HOST="${HOMELAB_SSH:-ansible@homelab-01}"
DIR="${HOMELAB_REPORTES:-$HOME/homelab-reportes}"
ESTADO="$DIR/.caida-en-curso"     # existe mientras el servidor está caído: guarda desde cuándo
MODO_CRON=0

mkdir -p "$DIR"

ayuda() { sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ayuda|-h|--help) ayuda ;;
    --cron)  MODO_CRON=1 ;;
    --desde) shift; date -d "${1:?falta la fecha}" '+%Y-%m-%d %H:%M:%S' > "$ESTADO"
             echo "Caída marcada desde $(cat "$ESTADO")"; exit 0 ;;
    *) echo "opción desconocida: $1 (probá --ayuda)" >&2; exit 2 ;;
  esac
  shift
done

decir() { [[ $MODO_CRON -eq 1 ]] || printf '%s\n' "$*"; }

avisar() {
  # cron no tiene sesión gráfica: se le indica el bus de la sesión del usuario.
  local titulo="$1" cuerpo="$2"
  if command -v notify-send >/dev/null; then
    DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/$(id -u)/bus}" \
      notify-send -u critical -a homelab "$titulo" "$cuerpo" 2>/dev/null || true
  fi
}

responde() {
  timeout 20 ssh -o BatchMode=yes -o ConnectTimeout=12 "$HOST" true 2>/dev/null
}

# --- 1. ¿Está? -------------------------------------------------------------------
if ! responde; then
  if [[ ! -f "$ESTADO" ]]; then
    date '+%Y-%m-%d %H:%M:%S' > "$ESTADO"
    avisar "homelab-01 no responde" "Se cayó o perdió la red. Cuando vuelva, te dejo el informe del porqué."
  fi
  decir "homelab-01 no responde (caído desde $(cat "$ESTADO"))."
  exit 0
fi

if [[ ! -f "$ESTADO" ]]; then
  decir "homelab-01 responde y no hay ninguna caída pendiente de explicar."
  exit 0
fi

# --- 2. Volvió: juntar las pistas EN el servidor ------------------------------------
DESDE="$(cat "$ESTADO")"
INFORME="$DIR/caida-$(date '+%Y%m%d-%H%M').md"
VOLVIO="$(date '+%Y-%m-%d %H:%M:%S')"
decir "homelab-01 volvió. Juntando pistas desde $DESDE…"

# Todo lo que sigue corre en el servidor, con sudo (la cuenta ansible no pide
# contraseña). Solo lee: no cambia nada. LC_ALL=C para que las palabras clave de
# los registros salgan en inglés y se puedan buscar.
PISTAS="$(timeout 120 ssh -o BatchMode=yes "$HOST" "sudo env LC_ALL=C DESDE='$DESDE' bash -s" <<'REMOTO' || true
set -u
seccion() { printf '\n### %s\n' "$1"; }

seccion "arranques"
journalctl --list-boots --no-pager 2>/dev/null | tail -4
echo "uptime: $(uptime -s 2>/dev/null) (arrancó a esa hora)"

seccion "final_arranque_anterior"
journalctl -b -1 -n 25 --no-pager -o short-iso 2>/dev/null

seccion "apagado_ordenado"
journalctl -b -1 --no-pager 2>/dev/null | grep -cE "systemd-shutdown|Reached target.*(Power-Off|Reboot|Shutdown)|System is (rebooting|powering down)" || true

seccion "reinicio_por_actualizacion"
journalctl -b -1 --no-pager 2>/dev/null | grep -iE "unattended-upgrade.*reboot|Rebooting.*unattended|reboot-required" | tail -5
grep -h "$(date -d "$DESDE" +%Y-%m-%d)" /var/log/unattended-upgrades/unattended-upgrades.log 2>/dev/null | grep -i "reboot" | tail -5

# Solo cortes REALES: los cambios de estado normales de un arranque
# (unmanaged -> unavailable, etc.) aparecen siempre y no dicen nada.
CORTE='activated -> (deactivating|disconnected|failed)|CTRL-EVENT-DISCONNECTED|deauthenticat|disassociat|[Bb]eacon loss|link becomes not ready|no carrier|reason .(supplicant-disconnect|ssid-not-found|supplicant-timeout|carrier-changed|device-removed)'
seccion "red_en_la_ventana"
journalctl -u NetworkManager --since "$DESDE" --no-pager -o short-iso 2>/dev/null | grep -E "$CORTE" | head -40

seccion "info_red_fin_arranque_anterior"
journalctl -u NetworkManager -b -1 --no-pager -o short-iso 2>/dev/null | grep -E "$CORTE" | tail -15

# Solo fallas: desconexión o reseteo de un USB, errores del driver WiFi o del
# controlador USB. Se excluyen los avisos de "Firmware bug" que salen siempre.
FALLA_USB='USB disconnect|reset (high|full|super|low)-speed USB device|over-current|device descriptor read.*error|xhci.*(HC died|halt|error|fail)|wlx[0-9a-f]+:.*(disconnect|deauth|fail|error|timeout|reset)|(rtl|r8188|8821|mt76|mt7601|ath9k)[a-z0-9_]*.*(fail|error|timeout|reset|crash)'
seccion "usb_y_wifi_kernel"
journalctl -k --since "$DESDE" --no-pager -o short-iso 2>/dev/null | grep -E "$FALLA_USB" | grep -v "Firmware bug" | head -30
journalctl -k -b -1 --no-pager -o short-iso 2>/dev/null | grep -E "$FALLA_USB" | grep -v "Firmware bug" | tail -15

seccion "memoria"
journalctl -k --since "$DESDE" --no-pager 2>/dev/null | grep -iE "out of memory|oom-kill|killed process" | head -10
journalctl -k -b -1 --no-pager 2>/dev/null | grep -iE "out of memory|oom-kill|killed process" | tail -10

# Solo eventos críticos: "Registered thermal governor" y similares salen en cada arranque.
CRITICO='temperature above threshold|critical temperature|[Cc]ritical temp|thermal.*(shutdown|critical)|clock throttled|undervolt|power supply.*(fail|error)'
seccion "temperatura_y_energia"
journalctl -k -b -1 --no-pager 2>/dev/null | grep -E "$CRITICO" | tail -10
journalctl -k --since "$DESDE" --no-pager 2>/dev/null | grep -E "$CRITICO" | head -10

seccion "kernel_panico_o_cuelgue"
journalctl -k -b -1 --no-pager 2>/dev/null | grep -iE "panic|BUG:|hung task|soft lockup|hard lockup|watchdog" | tail -10

seccion "tailscale_en_la_ventana"
journalctl -u tailscaled --since "$DESDE" --no-pager -o short-iso 2>/dev/null \
  | grep -iE "link change|LinkChange|network is unreachable|no route|magicsock.*(error|fail)|DERP.*(error|fail)" | head -15

seccion "red_ahora"
nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device 2>/dev/null | grep -vE "^(br-|veth|docker|lo)"
ip -4 route | grep default
REMOTO
)"

# --- 3. Leer las pistas y decidir --------------------------------------------------
pista() { awk -v s="### $1" '$0==s{f=1;next} /^### /{f=0} f' <<<"$PISTAS"; }
tiene() { [[ -n "$(pista "$1" | grep -v '^[[:space:]]*$' | grep -v '^0$' || true)" ]]; }

ARRANQUE="$(pista arranques | sed -n 's/^uptime: \([0-9-]* [0-9:]*\).*/\1/p')"
REINICIO=0
if [[ -n "$ARRANQUE" ]] && [[ "$(date -d "$ARRANQUE" +%s)" -ge "$(date -d "$DESDE" +%s)" ]]; then
  REINICIO=1
fi
ORDENADO="$(pista apagado_ordenado | tr -dc '0-9')"; ORDENADO="${ORDENADO:-0}"

CAUSAS=()
# Primero lo que pasó DURANTE la caída (red, hardware): suele ser la causa.
# El reinicio o el apagado de golpe van después: muchas veces son la consecuencia.
if tiene usb_y_wifi_kernel; then
  CAUSAS+=("**El adaptador WiFi USB se desconectó o se reinició** (mensajes del kernel sobre USB / \`wlx…\`). Es la sospecha principal de las caídas anteriores: un cable de red, o un adaptador/puerto USB distinto, lo resuelve.")
fi
if tiene red_en_la_ventana; then
  CAUSAS+=("**El WiFi se cortó o se reconectó** durante la caída (NetworkManager registró cambios de estado). Si el servidor **no** se reinició, esta es la causa: la máquina estuvo prendida pero sin red. Medir la calidad con \`make uplink\`.")
fi
if tiene memoria; then
  CAUSAS+=("**Se quedó sin memoria** (el kernel mató procesos para liberar RAM). Ver qué proceso en \`memoria\`.")
fi
if tiene temperatura_y_energia; then
  CAUSAS+=("**Temperatura o energía** (avisos de recalentamiento o de la fuente). Revisar ventilación y polvo.")
fi
if [[ $REINICIO -eq 1 ]]; then
  if tiene reinicio_por_actualizacion; then
    CAUSAS+=("**Reinicio por la actualización automática** (unattended-upgrades reinicia a las 04:30 si una actualización lo pide). Si después del reinicio no volvió a la red, el problema real es el WiFi al arrancar.")
  fi
  if tiene kernel_panico_o_cuelgue; then
    CAUSAS+=("**El sistema se colgó o tuvo un error grave del kernel** (ver \`kernel_panico_o_cuelgue\`). Después se reinició.")
  fi
  if [[ "$ORDENADO" -eq 0 ]]; then
    CAUSAS+=("**Se apagó de golpe, sin apagado ordenado** (el arranque anterior termina sin los mensajes de apagado). Lo más típico: **corte de luz** o alguien lo desenchufó/apagó con el botón. Si pasa seguido, una UPS (batería) lo resuelve.")
  else
    CAUSAS+=("**Se reinició o apagó de forma ordenada** (alguien lo apagó, o un reinicio programado). Revisá \`final_arranque_anterior\` para ver quién lo pidió.")
  fi
fi
if [[ ${#CAUSAS[@]} -eq 0 ]]; then
  CAUSAS+=("**No quedó una pista clara.** El servidor no se reinició y no hay registros de red en la ventana: puede haber sido algo **afuera** del servidor (el router, el proveedor de internet, o Tailscale). Revisar el router.")
fi

# --- 4. Escribir el informe ---------------------------------------------------------
{
  echo "# Informe de caída de homelab-01"
  echo
  echo "| | |"
  echo "|---|---|"
  echo "| Dejó de responder (aprox.) | $DESDE |"
  echo "| Volvió a responder | $VOLVIO |"
  echo "| ¿Se reinició? | $([[ $REINICIO -eq 1 ]] && echo "**sí** (arrancó $ARRANQUE)" || echo "no: estuvo prendido todo el tiempo (arrancó $ARRANQUE)") |"
  if [[ $REINICIO -eq 1 ]]; then
    echo "| ¿Apagado ordenado? | $([[ "$ORDENADO" -gt 0 ]] && echo "sí" || echo "**no** (se apagó de golpe)") |"
  fi
  echo
  echo "## Causa más probable"
  echo
  i=1; for c in "${CAUSAS[@]}"; do echo "$i. $c"; i=$((i+1)); done
  echo
  echo "## Pistas crudas (del servidor)"
  echo
  echo '```'
  printf '%s\n' "$PISTAS"
  echo '```'
  echo
  echo "_Generado por \`scripts/diagnosticar-caida.sh\` el $VOLVIO._"
} > "$INFORME"

rm -f "$ESTADO"
avisar "homelab-01 volvió" "Informe de la caída: $INFORME"
decir "Informe listo: $INFORME"
decir ""
decir "Causa más probable:"
for c in "${CAUSAS[@]}"; do decir "  - $c"; done
