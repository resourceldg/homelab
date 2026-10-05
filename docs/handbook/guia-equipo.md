# Guía práctica del equipo

🎯 **Objetivo:** poder trabajar de punta a punta en el proyecto de tu equipo:
conectarte, saber **dónde vive cada archivo**, escribir un `compose.yml` que pase la
política, usar la base de datos compartida, y dejar un servicio listo para **salir a
la web**.

🧩 **Prerequisitos:** [cap. 3 (Docker)](03-docker.md), [cap. 9 (Plataforma de aula)](09-plataforma-aula.md).

🆕 **Conceptos nuevos:** túnel SSH, directorio del equipo, `.shared-services.env`,
publicación (`student_exposures`), terminación TLS en el borde.

> Todos los ejemplos de `compose.yml` de esta guía están **verificados contra la
> política del aula** (`labctl validate`, el comando que revisa tu proyecto).
> Ejemplos completos y probados: [`ejemplos/nodered-mqtt/`](ejemplos/nodered-mqtt/)
> y [`ejemplos/nginx-ui/`](ejemplos/nginx-ui/README.md) (tu propia página web).

> **El modelo en una frase:** trabajás dentro de la carpeta de tu equipo con
> `labctl` (nunca tocás Docker ni `sudo`). Tus servicios escuchan **solo en loopback**
> (`127.0.0.1`) y los alcanzás por un **túnel SSH**. Cuando algo sale a la web, **lo
> publica el operador** con HTTPS automático — vos no abrís puertos públicos.

---

## 1. Conectarte

Para trabajar en tu proyecto necesitás llegar al servidor del aula desde tu
compu. Son dos pasos: **entrar a la red privada** y **abrir un túnel**.

**Qué te da el profe:** tu **usuario** (tu nombre, ej. `jorge`), tu **contraseña
del aula** y una **clave de Tailscale** (empieza con `tskey-auth-`).

### 1.1 Tailscale: la red privada del aula

**Tailscale** arma una red privada entre tu compu y el servidor, como si
estuvieran enchufados al mismo router aunque estés en tu casa. (**Por qué** la
usamos y qué resuelve → [Red y accesos](red-y-accesos.md#2-el-camino-de-las-personas-tailscale-una-red-privada).) Se hace **una
sola vez**. Instalalo desde <https://tailscale.com/download> y después:

**Windows** (en "Símbolo del sistema" / CMD, un comando por vez):

```
"C:\Program Files\Tailscale\tailscale.exe" logout
"C:\Program Files\Tailscale\tailscale.exe" up --auth-key=TU-CLAVE
```

**Linux** (en la Terminal, un comando por vez):

```
sudo tailscale logout
sudo tailscale up --auth-key=TU-CLAVE
```

El `logout` va primero por una razón: si alguna vez entraste a Tailscale con tu
cuenta de Google, te creó **una red tuya aparte**, y desde ahí no ves el
servidor. Para comprobar: `tailscale status` tiene que listar **`homelab-01`**.

### 1.2 El túnel SSH: traer tus servicios a tu compu

**SSH** (*Secure Shell*) es la forma segura de conectarte a otra computadora y
escribirle comandos. Con la opción `-L` además abre un **túnel**: un pasillo
privado que hace que un servicio del servidor aparezca en **tu** compu, en
`localhost` (que quiere decir "esta misma computadora").

Tus servicios escuchan **solo adentro del servidor** (en `127.0.0.1`, que es
`localhost` del servidor). Por eso nadie de afuera los ve, y vos llegás por el
túnel. Cada equipo tiene **sus propios números de puerto** (un puerto es como el
número de departamento de un servicio dentro del servidor; no se pueden repetir):

| Equipo | Node-RED en el servidor | Tu página (nginx) | Comando del túnel |
|---|---|---|---|
| equipo-01 | `1880` | — | `ssh -L 1880:localhost:1880 TU-USUARIO@100.110.123.76` |
| equipo-03 | `1882` | `8083` | `ssh -L 1880:localhost:1882 -L 8080:localhost:8083 TU-USUARIO@100.110.123.76` |
| equipo-04 | `1884` | `8084` | `ssh -L 1880:localhost:1884 -L 8080:localhost:8084 TU-USUARIO@100.110.123.76` |
| equipo-02 / 05 | se asignan al armar su stack | | pedíselo al profe |

Cómo se lee `-L 1880:localhost:1884`: "el **1880 de mi compu** lleva al **1884
del servidor**". Así, en tu navegador siempre usás los mismos números:

- Node-RED → `http://localhost:1880`
- Tu página → `http://localhost:8080`

Al conectarte: la primera vez escribí `yes`; después tu **contraseña del aula**
(no se ve mientras la tipeás, es normal). **Dejá esa ventana abierta**: si la
cerrás, se corta el túnel.

**Por qué así:** el SSH de alumnos solo se acepta desde la red privada (nunca
desde internet), y tus servicios no están publicados. El túnel es la forma de
usarlos sin exponer nada. Ver [cap. 7 (Seguridad)](07-seguridad.md).

---

## 2. Dónde vive cada cosa

Todo tu proyecto vive en **una sola carpeta** (`/srv/classroom/<tu-equipo>/`), con
cuota de disco propia:

```
/srv/classroom/equipo-04/
├── compose.yml                 # LA definición de tu stack (lo editás vos)
├── data/                       # acá PERSISTEN los datos (cuentan contra tu cuota)
│   └── nodered/                # flows y configuración de Node-RED
├── web/                        # tu página (si tu equipo tiene nginx)
│   └── index.html
├── nginx/
│   └── default.conf            # config de nginx (sirve web/ y el puente a Node-RED)
└── .shared-services.env        # credenciales de base de datos y MQTT (SOLO LECTURA)
```

**Por qué acá:** la carpeta tiene permisos que dejan entrar **solo a tu
equipo** (técnicamente, permisos `2770`. Cada número es un permiso: el `2` es
*setgid*, que hace que todo archivo nuevo quede también del equipo; el primer `7`
deja al dueño leer, escribir y entrar; el segundo `7`, lo mismo al grupo de tu
equipo; y el `0` final dice que **nadie más** puede ni mirar). Además
vive en un disco propio con **tope de 20 GB** (tu **cuota**). Nada afuera de esta
carpeta cuenta contra tu cuota, y la política rechaza usar carpetas de afuera.
**Guardá todo acá.**

- **`compose.yml`** — qué contenedores levantás y cómo. Es el archivo central.
- **`data/...`** — lo que quieras que sobreviva a un reinicio va acá. En el
  `compose.yml` se "conecta" una carpeta tuya con una carpeta del contenedor; eso
  se llama *bind mount* (ej. `./data/nodered:/data`: lo que Node-RED guarda en su
  `/data` queda en tu `data/nodered`).
- **`.shared-services.env`** — lo genera el operador; trae las credenciales de tu
  Postgres/Redis/MQTT. Lo **leés**, no lo editás:
  ```
  PGHOST=postgres   PGUSER=equipo_01   PGPASSWORD=…   PGDATABASE=db_equipo_01
  REDIS_URL=redis://redis:6379/2
  MQTT_HOST=mqtt-aula  MQTT_USER=equipo_01  MQTT_PASSWORD=…  MQTT_TOPIC_PREFIX=equipo-01/
  MQTT_DEVICE_HOST=homelab-01.tail4eda13.ts.net  MQTT_DEVICE_PORT=10000
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

### 3.3 MQTT: usá el broker del aula (`mqtt-aula`)

**MQTT** es el idioma con el que las placas se mandan mensajes, y el **broker**
es el programa que los reparte (lo explica, desde cero, el
[capítulo 11](11-arquitectura-iot.md)). El aula tiene **un broker para todos**:
`mqtt-aula`. Es el que tenés que usar, por tres razones:

1. **Tu ESP32 llega a él desde cualquier red** (tu casa, el colegio), por
   internet y cifrado. Un broker dentro de tu proyecto solo se alcanza por túnel
   SSH, y una placa no puede abrir un túnel.
2. **Lo que publicás se guarda y aparece en Grafana** solo
   ([capítulo 12](12-conectar-a-grafana.md)).
3. **Es cerrado:** entrás con el usuario y la clave de tu equipo, y **solo podés
   usar topics que empiecen con el nombre de tu equipo** (`equipo-04/...`). Un
   mensaje con otro nombre se descarta sin aviso.

| Desde | Host (dirección) | Puerto | ¿Cifrado (TLS)? | Usuario / clave |
|---|---|---|---|---|
| Tu Node-RED (en el servidor) | `mqtt-aula` | `1883` | no hace falta (viaja adentro del servidor) | `MQTT_USER` / `MQTT_PASSWORD` |
| Tu ESP32 (cualquier red) | `homelab-01.tail4eda13.ts.net` | `10000` | **sí** | los mismos |

Los datos están en tu `.shared-services.env`. Para verlos, entrá por SSH y corré
(cambiá `04` por tu número):

```
grep MQTT_ /srv/classroom/equipo-04/.shared-services.env
```

Ojo: el **usuario** va con **guion bajo** (`equipo_04`) y los **topics** con
**guion** (`equipo-04/...`). Es el error más común.

En Node-RED, el nodo *mqtt-broker* va a `mqtt-aula`, puerto `1883`, con usuario y
clave. `labctl up` conecta `mqtt-aula` a la red de tu proyecto, así que el nombre
`mqtt-aula` funciona solo.

> **¿Y un Mosquitto propio dentro de mi proyecto?** Se puede (hay un ejemplo en
> [`ejemplos/nodered-mqtt/`](ejemplos/nodered-mqtt/)), pero solo sirve para
> pruebas entre tus propios servicios: tu placa no lo alcanza y no aparece en
> Grafana.

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

### 3.5 Tu dashboard de Node-RED y tu página

Con el túnel abierto ([paso 1.2](#12-el-tunel-ssh-traer-tus-servicios-a-tu-compu)),
en tu navegador:

| Qué | Dirección | Para qué |
|---|---|---|
| **Editor** de Node-RED | `http://localhost:1880` | armar tus flujos (cajitas conectadas) |
| **Dashboard** de Node-RED | `http://localhost:1880/dashboard` | la pantalla con botones e indicadores: lo que se muestra |
| **Tu página** (si tu equipo tiene nginx) | `http://localhost:8080` | tu propia interfaz web |

Los equipos que ya tienen un tablero armado (equipo-01, equipo-03 y equipo-04) lo
encuentran en `/dashboard` → página **ESP32**. Para que el dashboard funcione, tu
Node-RED tiene que tener el nodo *mqtt-broker* conectado a `mqtt-aula`
([paso 3.3](#33-mqtt-usa-el-broker-del-aula-mqtt-aula)).

**¿Dashboard de Node-RED o Grafana?** El de Node-RED es para **controlar en vivo**
(botones, estados); Grafana es para **ver la historia**. Cuál usar →
[¿Node-RED, Grafana o ambos?](node-red-o-grafana.md).

> **Para la muestra:** el dashboard se abre en **tu** compu, con el túnel. Si lo
> van a mostrar en otra compu, esa compu necesita Tailscale y el túnel. Checklist
> completo → [chequeo rápido antes de la muestra](diagnostico.md#chequeo-rapido-antes-de-la-muestra).

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
tiene que tener una dirección propia con HTTPS, lo **habilita el operador**. Vos
preparás el servicio.

> ⚠️ **Hoy, "publicado" quiere decir "visible desde el tailnet", no desde internet.**
> El router de la casa del servidor no deja entrar conexiones de afuera (ver
> [Red y accesos](red-y-accesos.md#1-el-problema-el-servidor-esta-en-una-casa)).
> Una dirección como `https://equipo01.lucasland.duckdns.org` funciona para quien
> tenga **Tailscale** conectado. Para mostrar algo a público general hace falta
> otra salida, que se decide aparte con el profe.

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
el puerto estándar 443), alcanzable desde el tailnet. El vhost responde aunque tu servicio esté apagado (verías un
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

---

## Ahora deberías poder

- **Conectarte**: Tailscale + túnel SSH con los puertos de **tu** equipo.
- Saber **dónde vive** cada archivo de tu proyecto y por qué.
- Conectar tu Node-RED y tu placa al **broker del aula**.
- Abrir tu **dashboard** y tu **página** para la muestra.

**Seguí por acá:**

- Si querés **conectar tu placa** y que aparezca en Grafana → [capítulo 12](12-conectar-a-grafana.md).
- Si algo **no te deja entrar** → [Diagnóstico: no puedo entrar](diagnostico.md#no-puedo-entrar-a-algo).
- Si querés entender **por qué hay túneles y tantas contraseñas** → [Red y accesos](red-y-accesos.md).

