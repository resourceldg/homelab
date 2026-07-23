#!/usr/bin/env bash
# Prende los logs en vivo (Loki + Alloy) por un rato acotado y los apaga solos.
#
# Por qué así: indexar los logs de todos los contenedores cuesta RAM, CPU y
# disco de forma permanente, y este servidor además corre el laboratorio del
# aula. Entonces el stack vive APAGADO y esto lo enciende mientras haya alguien
# mirando. Cada TURNO minutos pregunta si seguir; si nadie contesta, se apaga.
#
# La garantía que importa es el `trap`: se apague como se apague este script
# —Ctrl+C, cierre de la terminal, error— el stack se baja. Un observador que
# queda prendido solo es exactamente lo que se quiere evitar.
#
#   logs-en-vivo            prende y pregunta cada 5 min
#   logs-en-vivo 15         turnos de 15 minutos
#   logs-en-vivo --off      apaga y sale (por si algo quedó colgado)
#   logs-en-vivo --estado   dice si está prendido
set -euo pipefail

STACK="${STACK_LOGS:-/opt/homelab/stacks/logs}"
TURNO_MIN="${1:-5}"
ESPERA_RESPUESTA_S=60

docker_compose() { sudo docker compose --project-directory "$STACK" "$@"; }

esta_prendido() {
  [ -n "$(sudo docker ps -q --filter name='^/loki$')" ]
}

apagar() {
  echo
  echo "==> apagando los logs en vivo…"
  docker_compose down >/dev/null 2>&1 || true
  echo "==> apagados. La auditoría del pañol sigue en Postgres, intacta."
}

case "${1:-}" in
  --off)
    apagar
    exit 0
    ;;
  --estado)
    if esta_prendido; then
      echo "prendidos"
      sudo docker ps --filter name='^/loki$' --filter name='^/alloy$' \
        --format '  {{.Names}}  {{.Status}}'
    else
      echo "apagados"
    fi
    exit 0
    ;;
esac

if ! [[ "$TURNO_MIN" =~ ^[0-9]+$ ]] || [ "$TURNO_MIN" -lt 1 ]; then
  echo "Uso: $(basename "$0") [minutos-por-turno | --off | --estado]" >&2
  exit 2
fi

# Pase lo que pase de acá en adelante, se apaga.
trap apagar EXIT INT TERM

echo "==> prendiendo Loki + Alloy…"
docker_compose up -d

echo "==> esperando a que Loki esté listo…"
for _ in $(seq 1 40); do
  if sudo docker inspect --format '{{.State.Health.Status}}' loki 2>/dev/null | grep -q healthy; then
    break
  fi
  sleep 3
done

cat <<EOF

  Logs en vivo PRENDIDOS.

  Grafana → dashboard "Pañol IoT — logs en vivo"
    https://grafana.${DOMINIO:-lucasland.duckdns.org}/d/panol-logs

  Están todos los contenedores del host, filtrables por stack y por
  contenedor. Se apagan solos si no contestás.

EOF

turno=0
while true; do
  sleep $((TURNO_MIN * 60))
  turno=$((turno + 1))
  printf '¿Seguir con los logs en vivo? [s/N] (turno %d, %d min; sin respuesta en %ds se apagan): ' \
    "$turno" "$TURNO_MIN" "$ESPERA_RESPUESTA_S"
  # -t: si nadie contesta, `read` falla y se sale del bucle -> trap -> apagar.
  if ! read -r -t "$ESPERA_RESPUESTA_S" respuesta; then
    echo
    echo "==> sin respuesta"
    exit 0
  fi
  case "$respuesta" in
    s | S | si | SI | Si | y | Y) echo "==> otros $TURNO_MIN minutos" ;;
    *) exit 0 ;;
  esac
done
