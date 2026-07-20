# Guía práctica del equipo

🎯 **Objetivo:** poder trabajar de punta a punta en el proyecto de tu equipo:
conectarte, saber **dónde vive cada archivo**, escribir un `compose.yml` que pase la
política, usar la base de datos compartida, y dejar un servicio listo para **salir a
la web**.

🧩 **Prerequisitos:** [cap. 3 (Docker)](03-docker.md), [cap. 9 (Plataforma de aula)](09-plataforma-aula.md).

🆕 **Conceptos nuevos:** túnel SSH, directorio del equipo, `.shared-services.env`,
publicación (`student_exposures`), terminación TLS en el borde.

> Todos los ejemplos de `compose.yml` de esta guía están **verificados contra la
> política del aula** (`labctl validate`). El ejemplo completo y ya probado vive en
> [`ejemplos/nodered-mqtt/`](ejemplos/nodered-mqtt/).

> **El modelo en una frase:** trabajás dentro de la carpeta de tu equipo con
> `labctl` (nunca tocás Docker ni `sudo`). Tus servicios escuchan **solo en loopback**
> (`127.0.0.1`) y los alcanzás por un **túnel SSH**. Cuando algo sale a la web, **lo
> publica el operador** con HTTPS automático — vos no abrís puertos públicos.

---

## 1. Conectarte

**Qué necesitás (te lo da el operador):** tu usuario y contraseña, y estar en la red
**Tailscale** del aula. El server es `homelab-01.tail4eda13.ts.net` (IP de respaldo
`100.110.123.76`).

1. Encendé **Tailscale** en tu compu y verificá que diga *Connected*.
2. Abrí el **túnel SSH** (dejá la ventana abierta mientras trabajás):
   ```bash
   ssh -L 1880:localhost:1880 -L 1883:localhost:1883 <usuario>@homelab-01.tail4eda13.ts.net
   ```
   Trae Node-RED (`1880`) y MQTT (`1883`) a tu máquina. Si el nombre no resuelve, usá la IP.
3. En el navegador → `http://localhost:1880`. MQTT → `localhost:1883`.

Para entrar solo a la terminal del server, el mismo comando **sin** los `-L`.

**Por qué así:** el SSH de alumnos solo se acepta desde la LAN o el tailnet (nunca
desde internet), y los servicios escuchan en loopback. El túnel es la forma segura de
alcanzarlos sin exponer nada. Ver [cap. 7 (Seguridad)](07-seguridad.md).

---

## 2. Dónde vive cada cosa

Todo tu proyecto vive en **una sola carpeta** (`/srv/classroom/<tu-equipo>/`), con
cuota de disco propia:

```
/srv/classroom/equipo-01/
├── compose.yml                 # LA definición de tu stack (lo editás vos)
├── mosquitto/
│   └── mosquitto.conf          # config del broker MQTT (lo editás vos)
├── data/                       # acá PERSISTEN los datos (cuentan contra tu cuota)
│   ├── nodered/                # flows y settings de Node-RED
│   └── mosquitto/              # persistencia del broker
└── .shared-services.env        # credenciales de DB/Redis/MQTT (SOLO LECTURA)
```

**Por qué acá:** la carpeta es `2770` con setgid → solo tu equipo entra, y vive sobre
un disco con **tope de 20 GB**. Nada afuera de esta carpeta cuenta contra tu cuota, y
la política rechaza montar rutas de afuera. **Guardá todo acá.**

- **`compose.yml`** — qué contenedores levantás y cómo. Es el archivo central.
- **`data/...`** — lo que quieras que sobreviva a un reinicio va en un *bind mount*
  bajo `data/` (ej. `./data/nodered:/data`).
- **`.shared-services.env`** — lo genera el operador; trae las credenciales de tu
  Postgres/Redis/MQTT. Lo **leés**, no lo editás:
  ```
  PGHOST=postgres   PGUSER=equipo_01   PGPASSWORD=…   PGDATABASE=db_equipo_01
  REDIS_URL=redis://redis:6379/2
  MQTT_HOST=mosquitto  MQTT_USER=equipo_01  MQTT_PASSWORD=…
  ```

---

## 3. Configuración básica (ejemplos verificados)

La política exige: imagen con **versión fija** (no `latest`), **límites** de
CPU/RAM/procesos, **rotación de logs**, `restart`, puertos **solo en `127.0.0.1`**,
sin volúmenes con nombre (usá bind mounts de `./data`), y máximo 5 servicios.

### 3.1 `compose.yml` mínimo (pasa `labctl validate`)

```yaml
---
services:
  web:
    image: nginxdemos/hello:plain-text   # versión fija, nunca :latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:8080:80"              # SOLO loopback (nunca 0.0.0.0)
    volumes:
      - ./data/web:/data                 # persistencia dentro de tu cuota
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "3" }
    deploy:
      resources:
        limits: { cpus: "0.50", memory: 256M, pids: 200 }
```

### 3.2 Usar la base de datos compartida (recomendado)

**No levantes tu propia Postgres.** El aula te da una base propia, aislada y
respaldada. Tu servicio la usa cargando `.shared-services.env`:

```yaml
---
services:
  nodered:
    image: nodered/node-red:4.0
    restart: unless-stopped
    ports:
      - "127.0.0.1:1880:1880"
    env_file:
      - .shared-services.env             # trae PGHOST/PGUSER/PGPASSWORD/PGDATABASE
    volumes:
      - ./data/nodered:/data
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "3" }
    deploy:
      resources:
        limits: { cpus: "0.50", memory: 256M, pids: 200 }
```

En Node-RED: instalá el nodo `node-red-contrib-postgresql` (*Manage Palette*) y en el
config-node usá `${PGHOST}` `${PGUSER}` `${PGPASSWORD}` `${PGDATABASE}`. El host
`postgres` resuelve dentro de tu red porque `labctl up` lo conecta.

> **Permisos de `data/`:** cada imagen corre con su propio uid (Node-RED `1000`,
> Mosquitto `1883`). Si un contenedor queda en `Restarting` con `EACCES` sobre
> `/data`, la carpeta del host tiene que pertenecer a ese uid → avisá al operador
> para el `chown` (ver [cap. 10, Caso 3](10-casos-practicos.md)).

### 3.3 `mosquitto/mosquitto.conf` básico

```
listener 1883
allow_anonymous true          # OK en el aula: el broker solo se alcanza por túnel SSH

persistence true
persistence_location /mosquitto/data/
```

Tu equipo ya tiene credenciales MQTT en `.shared-services.env` por si querés activar
autenticación (lo provisiona el operador; ver [`ejemplos/nodered-mqtt/mosquitto.conf`](ejemplos/nodered-mqtt/mosquitto.conf)).

### 3.4 Comandos (`labctl`)

Los corrés con tu usuario, desde cualquier carpeta (el broker te jaula a la de tu equipo):

```bash
labctl validate   # revisa tu compose contra la política (hacelo SIEMPRE antes de up)
labctl up         # levanta tu stack
labctl ps         # estado de tus contenedores
labctl logs       # ver logs
labctl restart    # reiniciar tras un cambio de config
labctl usage      # cuánto disco/recursos usás
labctl down       # apagar tu stack
```

---

## 4. SSL / HTTPS — quién lo hace

**Vos NO configurás SSL en tu proyecto.** El certificado y el HTTPS los maneja
**Caddy** (el proxy inverso del server), automáticamente, con certificados gratuitos
que se renuevan solos.

| Capa | Quién | Qué |
|---|---|---|
| Tu servicio | vos | escucha **HTTP plano** en un puerto loopback (ej. `127.0.0.1:8080`) |
| HTTPS público | Caddy (operador) | termina el TLS, pone el candado, renueva el certificado |

Tu contenedor habla **HTTP** puertas adentro; el HTTPS lo agrega Caddy en el borde al
publicarte. **No metas certificados ni TLS dentro de tu compose** — es redundante y la
plataforma no lo usa. Este es el vhost que arma el operador (de referencia, no lo tocás):

```caddy
equipo01.lucasland.duckdns.org {
    import secure_headers                 # cabeceras de seguridad
    encode zstd gzip                      # compresión
    reverse_proxy equipo-01-web-1:8080    # reenvía a TU contenedor 'web', puerto 8080
}
```

---

## 5. Salir a la web (producción)

Los alumnos **nunca** abren puertos públicos (la política lo bloquea). Si tu proyecto
tiene que verse desde internet, lo **habilita el operador**. Vos preparás el servicio.

**Qué preparás vos:**
1. Un servicio en tu `compose.yml` que sirva **HTTP** en un puerto **loopback**
   (ej. `web` en `127.0.0.1:8080:80`).
2. Que esté **sano** (`labctl ps` lo muestra `Up`/`healthy`) y responda en ese puerto.
3. **No publiques cosas peligrosas.** El editor de Node-RED sin login = ejecución de
   código para cualquiera → no se publica. Publicá una app web real o un dashboard con
   autenticación.

**Qué le pasás al operador:** nombre del equipo, nombre del servicio en tu compose,
puerto del contenedor y el hostname deseado.

**Qué hace el operador** (referencia — no lo hacés vos): agrega una entrada a
`student_exposures` en `ansible/inventories/production/group_vars/all/classroom.yml`…

```yaml
student_exposures:
  - team: equipo-01
    hostname: equipo01.lucasland.duckdns.org
    service: web
    port: 8080
    enabled: true
```

…y aplica `ansible-playbook site.yml --tags publish -K`. Caddy toma el cambio y tu
servicio queda en **`https://equipo01.lucasland.duckdns.org`** (HTTPS automático, sobre
el puerto estándar 443). El vhost responde aunque tu servicio esté apagado (verías un
502 hasta que hagas `labctl up`).

---

## 🧠 Ideas clave

- Trabajás **dentro de tu carpeta** (`/srv/classroom/<equipo>/`) con `labctl`; nunca
  Docker ni `sudo`.
- Puertos **solo en `127.0.0.1`**; los alcanzás por **túnel SSH**.
- La **base de datos** va a la **Postgres compartida** (`.shared-services.env`), no a
  una db propia.
- El **HTTPS lo pone Caddy**, no tu contenedor. La **publicación la decide el operador**.

## ⚠️ Errores comunes

`labctl validate` te dice **exactamente** qué rechaza. Ejemplos reales de un compose mal hecho:

```
service 'web': image 'nginx:latest' must be pinned to an explicit tag (not latest)
service 'web': missing CPU limit (deploy.resources.limits.cpus)
service 'web': missing logging (log rotation required)
service 'web': missing restart policy
service 'web': port '8080:80' must bind 127.0.0.1 explicitly (e.g. '127.0.0.1:8080:80')
named volumes are not allowed (datos); bind-mount a path under your project dir instead
```

Otros:

- **Contenedor en `Restarting` con `EACCES` en `/data`** → permisos del bind mount; el
  operador hace `chown` a la carpeta `data/` (uid del contenedor).
- **Tu app no encuentra `postgres`** → te faltó `env_file: .shared-services.env` o el
  stack no está `up`.
- **La URL pública da 502** → tu servicio no está arriba; `labctl up`.

## ❓ Preguntas de repaso

1. ¿Por qué tus servicios escuchan en `127.0.0.1` y no en `0.0.0.0`?
2. ¿Dónde guardás datos para que sobrevivan a un `labctl down`?
3. ¿Quién pone el HTTPS de tu servicio publicado, y dónde escucha tu contenedor?

## 🛠️ Ejercicios

1. Escribí un `compose.yml` con un servicio `web` que pase `labctl validate`.
2. Modificalo para que use la Postgres compartida (`env_file: .shared-services.env`).
3. Listá los 4 datos que le tenés que dar al operador para que publique tu servicio.
