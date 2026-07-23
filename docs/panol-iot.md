# Pañol IoT — el espacio en el homelab

El homelab **hospeda los servicios** del sistema de control de acceso al pañol.
El código del proyecto (motor de estados, API, puente MQTT, firmware) vive en
otro repo: `~/Documents/panol-iot`. Acá vive solo la **infraestructura** que
esos programas y esos dispositivos necesitan para hablarse.

| Qué | Dónde | Para qué |
|---|---|---|
| Stack Compose | `compose/panol/compose.yml` | broker + base + tablero |
| Config del broker | `compose/panol/mosquitto/mosquitto.conf` | listeners, persistencia, auth cerrada |
| Rol Ansible | `ansible/roles/panol/` | despliegue, credenciales, firewall |
| Publicación web | `compose/proxy/Caddyfile` (bloque `{$PANOL_SUBDOMAIN}`) | Node-RED detrás de SSO |

## Qué se levanta

```
                LAN / WLAN 192.168.100.0/24
   ESP32 puerta ─┐
   ESP32 armarios┴──► homelab-01:1883 ──► panol-mosquitto ──► red docker `panol`
                        (MQTT, con usuario y clave)             │
                                                                ├─ panol-postgres  (auditoría)
                                                                ├─ panol-nodered   (tablero)
                                                                └─ api + puente    (repo panol-iot)
                                                                        ▲
                            https://panol.lucasland.duckdns.org ────────┘ (Caddy + Authelia)
```

| Servicio | Contenedor | Escucha | Por qué así |
|---|---|---|---|
| Mosquitto | `panol-mosquitto` | `<IP de la LAN>:1883` (MQTT) y `127.0.0.1:19001` (websockets) | los ESP32 son hardware en la red: no pueden entrar por el proxy. UFW limita el 1883 a las redes de dispositivos |
| PostgreSQL | `panol-postgres` | `127.0.0.1:15432` | **no** el 5432: ese puerto del host ya lo usa el Postgres compartido del aula |
| Node-RED | `panol-nodered` | `127.0.0.1:11880` + Caddy | se publica en `https://panol.<dominio>` detrás de Authelia, solo operadores |

Dos puertos del host no son los "de siempre" por la misma razón: **el aula ya
está ahí**. El `5432` lo tiene el Postgres compartido, y el `127.0.0.1:1883` lo
publica el Mosquitto de un equipo. Por eso la base va en `15432` y el broker se
ata a la IP de la LAN en vez de a `0.0.0.0` (pedir `0.0.0.0:1883` choca con la
reserva de loopback). Efecto lateral bueno: el broker no queda accesible desde
loopback, que es donde vive el laboratorio de los alumnos. Efecto lateral a
tener presente: por Tailscale no se llega al broker, sí a la API.

Los tres cuelgan de la red Docker **`panol`**. Cualquier stack que se una a esa
red resuelve `mosquitto`, `postgres` y `nodered` por nombre.

## Desplegar

En **homelab-01**, como usuario `homelab`, desde `/home/homelab/homelab`:

```bash
cd ~/homelab/ansible
~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production --tags panol -K
```

(o `make panol` desde la raíz del repo). La primera corrida sortea todas las
contraseñas, construye el archivo de contraseñas del broker y levanta el stack.
Es idempotente: correrlo de nuevo no rota nada.

## Dónde quedan las credenciales

Todo bajo `/etc/panol/` **en el servidor** — nunca en el repo, nunca en el vault.
Se generan en el host con `openssl rand` la primera vez y sobreviven a las
converges siguientes (`creates:`), así que agregar un nodo no obliga a editar
secretos cifrados.

| Archivo | Permisos | Contenido |
|---|---|---|
| `/etc/panol/secrets/*.pass` | `root` 0700 | una clave por identidad, incluida la de Grafana (fuente de verdad) |
| `/etc/panol/secrets/nodos.txt` | `root` 0600 | hoja para grabar el firmware: broker, usuario, clave y topics de cada nodo |
| `/etc/panol/app.env` | `root:ansible` 0640 | `PANOL_DSN` + credenciales MQTT del servidor |
| `/opt/homelab/stacks/panol/.env` | `ansible` 0600 | puertos y claves que consume Compose |

```bash
sudo cat /etc/panol/secrets/nodos.txt     # para flashear los ESP32
sudo cat /etc/panol/app.env               # para la api y el puente
```

### Credenciales por defecto (cambiar antes del colegio)

Para ver el sistema andando de punta a punta sin ir a buscar nada, cada
identidad arranca con una clave **conocida**, declarada en
`ansible/roles/panol/defaults/main.yml`. Se llaman `cambiar-*` justamente
porque eso es lo que hay que hacer antes de montar en producción.

| Identidad | Clave por defecto | Quién la usa |
|---|---|---|
| `panol-servidor` | `cambiar-servidor-panol` | api + puente (`/etc/panol/app.env`) |
| `panol-nodered` | `cambiar-nodered-panol` | tablero Node-RED (se carga a mano en el nodo MQTT) |
| `nodo-panol-puerta` | `cambiar-nodo-puerta` | ESP32 #1 (`firmware/nodo_panol/config.py`) |
| `nodo-panol-armarios` | `cambiar-nodo-armarios` | ESP32 #2 (etapa posterior) |
| Postgres `panol` | `cambiar-db-panol` | base de auditoría (dueño) |
| Postgres `grafana_ro` | `cambiar-grafana-panol` | Grafana, solo SELECT |

**Rotar una clave** — el `.pass` es la fuente de verdad, así que se borra el
archivo (y se saca o se cambia el valor en `panol_mqtt_default_passwords`; si
la identidad ya no figura ahí, el rol le sortea una aleatoria de 24 bytes):

```bash
sudo rm /etc/panol/secrets/mqtt-nodo-panol-puerta.pass
make panol      # nueva clave, passwd reconstruido, broker reiniciado
sudo grep -A4 nodo-panol-puerta /etc/panol/secrets/nodos.txt   # la nueva, para regrabar
```

Rotar la del servidor (`panol-servidor`) además reescribe `/etc/panol/app.env`:
hay que reiniciar la api y el puente para que la tomen.

## El broker está cerrado (y por qué importa)

`allow_anonymous false` + `password_file` + `acl_file`. La versión local del
proyecto corre anónima para probar en banco; **acá no**: un broker abierto en la
red del colegio permite que cualquiera publique un `acceso CONCEDIDO` falso y
abra una sesión a nombre de otro. La auditoría dejaría de valer, que es
exactamente lo que el sistema existe para dar.

Las ACL (`ansible/roles/panol/templates/mosquitto-acl.j2`) reparten el árbol:

| Identidad | Puede |
|---|---|
| `panol-servidor` (api + puente) | leer y escribir `panol/#` |
| `panol-nodered` (tablero) | solo leer `panol/#` |
| `nodo-panol-puerta` | escribir **solo** `panol/panol-lab01/panol-lab01-puerta/evento/#` y `.../heartbeat`, leer `.../cmd/#` |
| `nodo-panol-armarios` | lo mismo, en su propia rama |

Un nodo comprometido solo puede mentir sobre sí mismo. Los nodos se declaran en
`ansible/roles/panol/defaults/main.yml` (`panol_mqtt_nodes`): agregar uno es
sumar tres líneas y correr `make panol`.

> **Ojo con la identidad:** `ubicacion` y `nodo` forman el topic y tienen que
> coincidir exactamente con `UBICACION_ID` / `NODO_ID` del firmware
> (`panol-iot/firmware/nodo_panol/config.py`, hoy `panol-lab01` y
> `panol-lab01-puerta`). Si no coinciden, el nodo publica en una rama que su
> propia ACL le prohíbe y el broker lo rechaza sin ruido.

## Firewall

El puerto 1883 lo publica Docker, así que el tráfico entra por `FORWARD`, no por
`INPUT`. Con `ufw-docker` instalado, la regla que decide es `ufw route` — una
`ufw allow 1883` común no haría nada y encima daría una falsa sensación de
control. El rol crea una regla por red de dispositivos
(`panol_device_cidrs`: LAN + Tailscale por defecto):

```bash
sudo ufw status | grep 1883
```

Si mañana los nodos van a una VLAN IoT propia, agregás ese CIDR a
`panol_device_cidrs` y corrés `make panol`.

## Ver: Grafana

Dashboard **Pañol IoT — auditoría** (`https://grafana.<dominio>`, carpeta
Homelab). Lee la base del pañol directamente, con un rol propio
(`grafana_ro`) que **solo tiene SELECT**: un panel que puede escribir en un
registro de auditoría no es un panel, es un agujero.

| Panel | Para qué |
|---|---|
| Responsable actual | qué tarjeta tiene la sesión `EN_CURSO`, o "sin sesión" |
| Puerta | último estado del reed (el reed solo reporta cambios: si dice ABIERTA, sigue abierta) |
| Minutos desde el último heartbeat | el nodo late cada 60 s; en rojo pasados 10 min |
| Accesos por hora | CONCEDIDO/DENEGADO apilados — un pico de DENEGADO es alguien probando tarjetas |
| Nodos | heartbeat, RSSI y modo degradado por nodo |
| Alarmas / Accesos / Sesiones | el detalle, filtrable, con la ventana de tiempo del dashboard |

Grafana llega a la base por la red docker `panol` (que crea el rol `docker`,
igual que `edge`), no por el puerto de loopback. El datasource lo escribe el rol
`panol` dentro del stack de monitoreo, porque la contraseña la conoce ese rol y
no el de monitoreo.

## Accionar: Node-RED, no Grafana

Grafana **no** es para botones: los que hay son plugins de terceros y quedan a
mitad de camino. El lugar para accionar es Node-RED, que ya está desplegado y
tiene credencial en el broker (`panol-nodered`).

Ahora bien, hoy un botón no tendría a quién hablarle. La rama de comandos
`panol/<ubicacion>/<nodo>/cmd/#` está reservada en la ACL —el nodo tiene
permiso de lectura sobre ella— pero **el firmware todavía no escucha MQTT**:
reporta por HTTP y no hay canal de comandos en la API. Para que un botón "abrir
puerta" funcione hay que, en este orden:

1. Que el nodo se suscriba a su rama `cmd/#` (etapa 2b del firmware), o que la
   API exponga una cola de comandos que el nodo lea en su polling.
2. Decidir qué comandos existen y cuáles NO. Abrir a distancia una puerta con
   control de acceso es exactamente lo que el sistema existe para auditar: si
   se agrega, el comando tiene que quedar registrado como un evento más, con
   quién lo disparó.

Mientras tanto Node-RED sirve igual para lo que no es accionar: mostrar en
pantalla las sesiones y alarmas que el puente publica (`panol/<ubicacion>/sesion`
y `panol/<ubicacion>/alarma/<codigo>`), y mandar avisos.

## Backups

No hay que configurar nada: los tres lugares donde vive el estado del pañol ya
están en `borg_paths` (rol `backups`) — `/etc` (las claves), `/opt/homelab` (el
stack) y `/var/lib/docker/volumes` (la base de auditoría y la persistencia del
broker). Eso sí, los backups siguen esperando el disco montado en `/mnt/backup`.

## Conectar la aplicación (repo panol-iot)

El "cerebro" (api + puente) no se despliega desde este repo: se construye desde
su propio código. El repo `panol-iot` ya trae el compose para eso —
`docker-compose.homelab.yml`— que no levanta ni base ni broker, sino que se une
a la red `panol` y toma las credenciales de `/etc/panol/app.env`.

En el servidor, con el repo clonado (por ejemplo en `~/panol-iot`):

```bash
cd ~/panol-iot
docker compose -f docker-compose.homelab.yml up -d --build
```

Levanta dos contenedores: `panol-api` (HTTP en el 18500, que es por donde
reporta el ESP32) y `panol-puente-mqtt` (suscrito al broker con el usuario
`panol-servidor`). Los dos escriben en la **misma** base que ya está corriendo.

El puente ya autentica: `server/puente_mqtt.py` lee `MQTT_USER` / `MQTT_PASSWORD`
y llama a `username_pw_set()` antes de conectar. Si esas variables no están
—como en el stack local, que corre con broker anónimo— se conecta igual que
antes, así que el banco de pruebas no cambió.

## Recorrido end-to-end

Con el plano arriba y la app desplegada, esto es lo que hay que ver:

```bash
# 1. Todo corriendo (5 contenedores: broker, base, tablero, api, puente)
docker ps --filter name=panol-

# 2. La API responde
curl -s http://localhost:18500/salud

# 3. Un evento entra por HTTP (el camino que usa el ESP32 hoy).
#    Tipos válidos: acceso, puerta, pir, armario. La ubicación se da de alta sola.
curl -s -X POST http://192.168.100.48:18500/api/evento/acceso \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"e2e-1","ubicacion_id":"panol-lab01","nodo_id":"panol-lab01-puerta",
       "uid_hex":"DEADBEEF","resultado":"CONCEDIDO","timestamp":"2026-07-22T10:00:00-03:00"}'

# 4. Quedó en la base (y con un acceso CONCEDIDO nace una sesión)
docker exec panol-postgres psql -U panol -d panol -c \
  'select ubicacion_id, uid_hex, resultado, timestamp from eventos_acceso order by timestamp desc limit 5;'
docker exec panol-postgres psql -U panol -d panol -c 'select * from sesiones;'

# 5. El mismo camino por MQTT, con la credencial del nodo (lo que hará el firmware).
#    El tipo sale del topic y la identidad también: el payload va mínimo.
mosquitto_pub -h 192.168.100.48 -p 1883 \
  -u nodo-panol-puerta -P cambiar-nodo-puerta -q 1 \
  -t panol/panol-lab01/panol-lab01-puerta/evento/acceso \
  -m '{"event_id":"e2e-2","timestamp":"2026-07-22T10:01:00-03:00",
       "datos":{"uid_hex":"DEADBEEF","resultado":"CONCEDIDO"}}'

# 6. El puente lo tomó (tiene que loguear el event_id)
docker logs --tail 20 panol-puente-mqtt

# 7. El nodo real: prender el ESP32 y ver su heartbeat
docker exec panol-postgres psql -U panol -d panol -c 'select * from nodos;'
```

En el paso 5, un `mosquitto_pub` con la credencial del nodo pero apuntando a
**otra** rama del árbol tiene que fallar: eso es la ACL haciendo su trabajo.

## Verificar

```bash
# Contenedores y salud
docker ps --filter name=panol-

# ¿El broker rechaza anónimos? (tiene que fallar)
docker exec panol-mosquitto mosquitto_sub -h 127.0.0.1 -t 'panol/#' -C 1 -W 3

# ¿Y acepta al servidor? (tiene que imprimir un número)
sudo bash -c 'set -a; . /etc/panol/app.env; \
  docker exec panol-mosquitto mosquitto_sub -h 127.0.0.1 \
    -u "$MQTT_USER" -P "$MQTT_PASSWORD" -t "\$SYS/broker/uptime" -C 1 -W 3'

# La ACL: el nodo NO puede escribir fuera de su rama.
# El -V 5 no es decorativo: con MQTT 3.1.1 el broker descarta el mensaje EN
# SILENCIO y el cliente cree que publicó. Con MQTT 5 avisa "Not authorized".
# Ojo igual: mosquitto_pub sale con código 0 en los dos casos, hay que LEER.
mosquitto_pub -h 192.168.100.48 -p 1883 -V 5 -q 1 \
  -u nodo-panol-puerta -P cambiar-nodo-puerta \
  -t panol/panol-lab01/panol-lab01-armarios/evento/acceso -m '{}'
#  -> Warning: Publish 1 failed: Not authorized.

# Suite de humo completa (en el servidor)
py.test -v --hosts=local:// --sudo tests/test_panol.py
```

## Etapas

1. **Hecho acá:** broker + base + tablero en el homelab, con auth, ACL, firewall
   y credenciales por defecto conocidas; api y puente desplegables desde el repo
   panol-iot con `docker-compose.homelab.yml`; el puente ya autentica.
2. **Siguiente:** el ESP32 apuntando al homelab (`SERVER_URL` ya cambiado en
   `config.py`), tablero Node-RED armado sobre los topics de sesión y alarma, y
   **cambiar las claves `cambiar-*`**.
3. **Después:** que el firmware publique por MQTT en vez de HTTP (las
   credenciales del nodo ya están en `config.py` y en la ACL), publicar la API
   por Caddy (`panol-api.<dominio>`) e integrar EMATP.
