#!/usr/bin/env bash
# Al arrancar, deja por escrito qué pasó en el arranque ANTERIOR.
#
# Por qué: si el servidor se congeló o se quedó sin luz, la evidencia está en el
# arranque anterior y se va perdiendo entre los registros nuevos. Este resumen
# queda en /var/log/homelab/arranques/ y lo lee también scripts/diagnosticar-caida.sh
# (en la compu del operador).
#
# Lo más valioso que agrega: el ÚLTIMO LATIDO del guardián de red (vigia-red
# escribe la hora cada minuto). Si el diario se corta sin apagado, el latido dice
# a qué minuto murió la máquina.
set -uo pipefail
export LC_ALL=C

DIR="${POSTMORTEM_DIR:-/var/log/homelab/arranques}"
ESTADO_DIR="${VIGIA_ESTADO_DIR:-/var/lib/vigia-red}"
mkdir -p "$DIR"
OUT="$DIR/$(date '+%Y%m%d-%H%M%S').txt"

if ! journalctl -b -1 -n 1 --no-pager >/dev/null 2>&1; then
  echo "sin arranque anterior en el diario" > "$OUT"; exit 0
fi

# Apagado ORDENADO = el gestor del SISTEMA (systemd[1]) llegó al apagado. Ojo: las
# sesiones de usuario también dicen "Reached target Shutdown" al cerrar sesión; esas
# no cuentan (pasó: daba "ordenado" un servidor que se había congelado).
ordenado=$(journalctl -b -1 --no-pager 2>/dev/null \
  | grep -cE "systemd\[1\]: .*(Reached target .*(System Power Off|System Reboot|Power-Off|Reboot)|Shutting down)|systemd-shutdown\[|System is (rebooting|powering down)")
ultimo="$(journalctl -b -1 --no-pager -o short-iso -n 1 2>/dev/null | cut -c1-25)"
# El latido se lee ANTES de que vigia-red escriba uno nuevo (orden en systemd).
# Si igual es de ESTE arranque (p. ej. al correrlo a mano), no sirve: se descarta.
latido="sin latido del arranque anterior"
if [[ -r "$ESTADO_DIR/latido" ]]; then
  l="$(cat "$ESTADO_DIR/latido")"
  if [[ "$(date -d "$l" +%s 2>/dev/null || echo 0)" -lt "$(date -d "$(uptime -s)" +%s)" ]]; then
    latido="$l  → la máquina murió entre esa hora y un minuto después"
  fi
fi
# El chip del watchdog recuerda si fue ÉL quien reinició el equipo (CARDRESET en
# la columna BOOT-STATUS de wdctl). Es la prueba directa de un congelamiento.
watchdog_hw="$(wdctl 2>/dev/null | awk '$1=="CARDRESET"{print $NF}')"

{
  echo "== Arranque actual:       $(uptime -s)"
  echo "== Último registro previo: ${ultimo:-?}"
  echo "== Último latido previo:   ${latido}"
  if [[ "${ordenado:-0}" -gt 0 ]]; then
    echo "== Apagado anterior: ORDENADO (alguien lo apagó o reinició, o fue un reinicio programado)"
  else
    echo "== Apagado anterior: DE GOLPE (sin apagado del sistema: corte de luz, botón o CONGELAMIENTO)"
  fi
  [[ "${watchdog_hw:-0}" == "1" ]] && echo "== EL WATCHDOG DE HARDWARE REINICIÓ EL EQUIPO: estaba congelado."
  echo
  echo "== Guardián de red (vigia-red) en el arranque anterior:"
  journalctl -b -1 -t vigia-red --no-pager -o short-iso 2>/dev/null | tail -20
  echo
  echo "== Pedidos de reinicio de la actualización automática:"
  journalctl -b -1 --no-pager 2>/dev/null | grep -iE "unattended-upgrade.*reboot|reboot-required" | tail -5
  echo
  echo "== Fallas de USB / WiFi del kernel:"
  journalctl -k -b -1 --no-pager -o short-iso 2>/dev/null \
    | grep -E "USB disconnect|reset (high|full|super|low)-speed USB device|over-current|xhci.*(HC died|halt|error|fail)|wlx[0-9a-f]+:.*(disconnect|deauth|fail|error|timeout|reset)|rtl8187.*(fail|error|timeout|reset)" | tail -15
  echo
  echo "== Memoria, temperatura, cuelgues (solo eventos reales):"
  journalctl -k -b -1 --no-pager 2>/dev/null \
    | grep -E "Out of memory|oom-kill|Killed process|temperature above threshold|[Cc]ritical temperature|Kernel panic|BUG: |hung_task|soft lockup|hard LOCKUP|watchdog: BUG" | tail -10
  echo
  echo "== Últimas 15 líneas del SISTEMA en el arranque anterior:"
  journalctl -b -1 --no-pager -o short-iso _PID=1 2>/dev/null | tail -15
} > "$OUT"

ls -1t "$DIR"/*.txt 2>/dev/null | tail -n +31 | xargs -r rm -f
