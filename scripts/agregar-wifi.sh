#!/usr/bin/env bash
# Suma una red WiFi al servidor SIN borrar las que ya tiene. Corre EN EL SERVIDOR.
#
# Por qué así: este server ya se mudó de red más de una vez, y cada mudanza a
# mano arriesga dejarlo sin red (y sin Tailscale, que es por donde se entra).
# El script guarda la red nueva como un perfil más de NetworkManager, la
# prueba, y si no levanta vuelve a la red que estaba usando. Las redes viejas
# quedan guardadas con autoconexión: si la nueva desaparece, el server vuelve
# solo a la que encuentre.
#
# La clave NO va en la línea de comandos ni en el repo: se pide al correrlo
# (o se pasa por la variable WIFI_PASS), para que no quede en el historial.
#
#   sudo agregar-wifi.sh "Nombre-de-la-red"
#   sudo agregar-wifi.sh "Nombre-de-la-red" --solo-guardar   # no la activa ahora
#   sudo agregar-wifi.sh --ayuda
set -euo pipefail

if [[ -t 1 ]]; then
  BOLD=$'\e[1m'; RED=$'\e[31m'; GRN=$'\e[32m'; YLW=$'\e[33m'; BLU=$'\e[36m'; RST=$'\e[0m'
else
  BOLD=""; RED=""; GRN=""; YLW=""; BLU=""; RST=""
fi
say()  { printf '%s\n' "${BLU}${BOLD}==>${RST} ${BOLD}$*${RST}"; }
ok()   { printf '%s\n' "${GRN}  ✓${RST} $*"; }
warn() { printf '%s\n' "${YLW}  !${RST} $*"; }
bad()  { printf '%s\n' "${RED}  ✗${RST} $*"; }

SSID=""
SOLO_GUARDAR=0
for arg in "$@"; do
  case "$arg" in
    --ayuda|-h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --solo-guardar)    SOLO_GUARDAR=1 ;;
    -*)                echo "opción desconocida: $arg (probá --ayuda)" >&2; exit 2 ;;
    *)                 SSID="$arg" ;;
  esac
done

[[ -n "$SSID" ]] || { echo "falta el nombre de la red (probá --ayuda)" >&2; exit 2; }
[[ $EUID -eq 0 ]] || { echo "correlo con sudo" >&2; exit 1; }
command -v nmcli >/dev/null || { bad "no está nmcli (NetworkManager)"; exit 1; }

# --- placa WiFi ---------------------------------------------------------------
mapfile -t PLACAS < <(nmcli -t -f DEVICE,TYPE device | awk -F: '$2=="wifi"{print $1}')
[[ ${#PLACAS[@]} -gt 0 ]] || { bad "no hay ninguna placa WiFi"; exit 1; }
PLACA="${PLACAS[0]}"
say "Placa WiFi: $PLACA (de ${#PLACAS[@]}: ${PLACAS[*]})"

# Lo que está activo ahora, para volver si la nueva no levanta.
ANTERIOR="$(nmcli -t -f NAME,DEVICE connection show --active | awk -F: -v d="$PLACA" '$2==d{print $1}')"
[[ -n "$ANTERIOR" ]] && ok "Ahora está en: $ANTERIOR (queda guardada)" || warn "La placa no está conectada a nada ahora"

# --- clave ----------------------------------------------------------------------
CLAVE="${WIFI_PASS:-}"
if [[ -z "$CLAVE" ]]; then
  read -r -s -p "Clave de \"$SSID\": " CLAVE; echo
fi
[[ ${#CLAVE} -ge 8 ]] || { bad "una clave WPA tiene al menos 8 caracteres"; exit 1; }

# --- ¿la red se ve? ---------------------------------------------------------------
say "Buscando \"$SSID\"..."
nmcli device wifi rescan ifname "$PLACA" 2>/dev/null || true
sleep 3
if nmcli -t -f SSID device wifi list ifname "$PLACA" | grep -Fxq "$SSID"; then
  ok "La red está al alcance"
else
  warn "No la veo ahora (lejos, apagada o de 5 GHz si la placa no lo soporta). La guardo igual."
  SOLO_GUARDAR=1
fi

# --- perfil -----------------------------------------------------------------------
# Prioridad alta: entre varias redes conocidas a la vista, NetworkManager elige
# esta. Las viejas quedan con la suya y siguen siendo el plan B.
if nmcli -t -f NAME connection show | grep -Fxq "$SSID"; then
  say "Ya existía un perfil \"$SSID\": actualizo la clave"
  nmcli connection modify "$SSID" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$CLAVE" \
    connection.autoconnect yes connection.autoconnect-priority 20 \
    connection.autoconnect-retries 0
else
  say "Guardando el perfil \"$SSID\""
  nmcli connection add type wifi ifname "$PLACA" con-name "$SSID" ssid "$SSID" \
    wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$CLAVE" \
    connection.autoconnect yes connection.autoconnect-priority 20 \
    connection.autoconnect-retries 0 >/dev/null
fi
ok "Guardado (autoconexión sí, prioridad 20, reintenta para siempre)"

if [[ $SOLO_GUARDAR -eq 1 ]]; then
  ok "No la activo ahora; se va a conectar sola cuando esté al alcance"
  exit 0
fi

# --- activar, con vuelta atrás ------------------------------------------------------
say "Conectando a \"$SSID\"..."
if ! nmcli --wait 40 connection up "$SSID" ifname "$PLACA"; then
  bad "No levantó \"$SSID\" (¿clave equivocada?)"
  if [[ -n "$ANTERIOR" ]]; then
    warn "Vuelvo a \"$ANTERIOR\""
    nmcli --wait 40 connection up "$ANTERIOR" ifname "$PLACA" || bad "Tampoco volvió: revisar con 'nmcli device status'"
  fi
  exit 1
fi

IP="$(nmcli -g IP4.ADDRESS device show "$PLACA" | head -1)"
GW="$(nmcli -g IP4.GATEWAY device show "$PLACA" | head -1)"
ok "Conectado. IP: ${IP:-?}  gateway: ${GW:-?}"

# --- ¿anda de verdad? -----------------------------------------------------------------
# "Conectado" no alcanza: este server ya estuvo "conectado" perdiendo el 57% de
# los paquetes. Se mide.
say "Probando la conexión"
if [[ -n "$GW" ]] && ping -c 5 -W 2 "$GW" >/dev/null 2>&1; then ok "Gateway responde"; else warn "El gateway no responde al ping"; fi
if ping -c 3 -W 3 1.1.1.1 >/dev/null 2>&1; then ok "Hay internet"; else bad "Sin internet"; fi

if command -v tailscale >/dev/null; then
  sleep 5
  if tailscale status >/dev/null 2>&1 && tailscale ip -4 >/dev/null 2>&1; then
    ok "Tailscale arriba: $(tailscale ip -4 | head -1) (se entra igual que siempre)"
  else
    warn "Tailscale todavía no levantó; en un minuto debería. Ver: tailscale status"
  fi
fi

echo
ok "Listo. Redes guardadas:"
nmcli -t -f NAME,TYPE,AUTOCONNECT,AUTOCONNECT-PRIORITY connection show \
  | awk -F: '$2 ~ /wireless/ {printf "    %-28s autoconexión=%s prioridad=%s\n", $1, $3, $4}'
echo
warn "Si la red nueva usa otro rango (no 192.168.100.0/24), el SSH por LAN queda"
warn "bloqueado por el firewall hasta actualizar lan_cidr. Por Tailscale se entra igual."
