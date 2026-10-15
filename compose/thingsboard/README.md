# Stack `thingsboard`

ThingsBoard CE 4.3.1.6: tableros IoT por proyecto, con publicación pública de
solo lectura. **La guía completa (arquitectura, despliegue, seguridad, recursos,
respaldo y rollback) está en [docs/thingsboard.md](../../docs/thingsboard.md).**

Se despliega con el rol Ansible `thingsboard` (`make thingsboard`, o
`--tags shared-services,thingsboard`). Está apagado por defecto
(`thingsboard_enabled`).

## Qué hay acá

| Archivo | Qué es |
|---|---|
| `compose.yml` | ThingsBoard, su Postgres, el exportador de métricas, el puente MQTT, el proxy público, el nodo Tailscale (perfil `publico`) y el simulador (perfil `demo`) |
| `.env.example` | Variables. El `.env` real lo escribe el rol (root, 0600) |
| `conf/` | `thingsboard.conf` y `logback.xml` propios: sin log de GC a archivo y logs solo por stdout |
| `puente/` | `tb-puente` (mqtt-aula → ThingsBoard) y el simulador de placas. Su contrato es el mismo que `aula-iot/telegraf/mqtt.star`, y lo controla `tests/test_tb_puente.py` |
| `publico/` | Proxy público (`Caddyfile`, deniega por defecto) y `serve.json` del nodo Tailscale |
| `provision/tb-provision.py` | Aprovisionamiento idempotente: tenant, admin, gateway, dashboards y reconciliación de lo público. Escribe la portada |
| `scripts/probar-acceso-publico.py` | Prueba la superficie pública desde afuera. Sale con error si algo falla |
| `scripts/capturar-rutas-publicas.js` | Captura con un navegador real las rutas que usa la vista pública (al actualizar ThingsBoard) |

## Comandos útiles (en homelab-01)

```bash
cd /opt/homelab/stacks/thingsboard
sudo docker compose ps                                   # estado
sudo docker compose logs --since 30m thingsboard         # logs
sudo systemctl start tb-backup.service                   # respaldo ya
sudo cat /srv/tableros/.tableros.json                    # links de los tableros
sudo /usr/local/sbin/tb-provision --config /etc/thingsboard/tableros.json   # re-aprovisionar
```

Probar la superficie pública, desde cualquier máquina:

```bash
python3 scripts/probar-acceso-publico.py https://tableros.<tailnet>.ts.net \
  --dashboard '<link público>' --privado <id de un dashboard privado>
```

**Nunca** `docker compose down -v`: borra la base. Para apagar, ver
[docs/thingsboard.md](../../docs/thingsboard.md#desactivar-rollback).
