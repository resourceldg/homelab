# Guía del alumno — paso a paso

Esta guía asume que **recién empezás** con Linux y Docker. Vamos despacio y
explicando todo. No necesitás saber nada de antemano.

**¿Qué vas a hacer?** Entrar al servidor del laboratorio desde tu compu, escribir
un archivo que describe tu aplicación, y prenderla con **un solo comando**
(`labctl`). No manejás Docker directamente ni necesitás permisos de administrador.

---

## Antes de empezar

Necesitás:
- Tu **notebook** con una terminal (en Linux/Mac ya viene; en Windows usá
  *PowerShell* o *Windows Terminal*).
- Un **nombre de usuario** que te da el profe (por ejemplo `jessi`).
- Que el profe ya haya cargado tu **clave** en el servidor (lo hace una vez).
- La **dirección del servidor** (una IP o un nombre, te la pasa el profe).

> **¿Qué es una "terminal"?** Es una ventana donde escribís comandos en texto en
> vez de hacer clic. Vas a escribir un comando, apretar Enter, y el servidor
> responde con texto.

---

## Paso 1 — Entrar al servidor (SSH)

**SSH** es la forma de conectarte a otra computadora por la red de forma segura.
En tu terminal (la de tu notebook) escribí, reemplazando por tus datos:

```bash
ssh tu-usuario@direccion-del-servidor
```

Ejemplo real:
```bash
ssh jessi@192.168.100.48
```

- **La primera vez** te va a mostrar algo como *"The authenticity of host…
  fingerprint… Are you sure you want to continue (yes/no)?"*. Escribí **`yes`** y
  Enter. (Es normal: tu compu está guardando la identidad del servidor.)
- Si todo está bien, **entrás**: el texto a la izquierda (el "prompt") cambia a
  algo como `jessi@homelab-01:~$`. Eso significa que ya **estás adentro del
  servidor**. Todo lo que escribas ahora corre allá, no en tu notebook.

> Si te pide una contraseña y no la tenés, avisá al profe: el acceso es por
> **clave**, no por contraseña.

Para **salir** del servidor en cualquier momento: escribí `exit` y Enter (volvés
a tu notebook).

---

## Paso 2 — Moverte por la terminal (3 comandos)

Estos 3 comandos son todo lo que necesitás para ubicarte:

| Comando | Qué hace | Ejemplo |
|---|---|---|
| `pwd` | Te dice **en qué carpeta estás** (print working directory) | `pwd` → `/home/jessi` |
| `ls` | **Lista** los archivos de la carpeta actual | `ls` |
| `cd` | **Entra** a una carpeta (change directory) | `cd /srv/classroom/equipo-01` |

Andá a la carpeta de tu equipo (cambiá el número por el tuyo):

```bash
cd /srv/classroom/equipo-01
pwd     # confirmá que dice /srv/classroom/equipo-01
ls      # ver qué hay (al principio, vacío o con tu compose)
```

> **Importante:** solo tu equipo puede entrar a esta carpeta. Es tu espacio de
> trabajo. Todo tu proyecto vive acá.

---

## Paso 3 — Escribir tu archivo `compose.yml`

Un **`compose.yml`** es un archivo de texto que describe **qué contenedores**
(mini-servidores con tu app adentro) querés prender y cómo. Docker lo lee y los
prende.

Para crear/editar el archivo usamos un editor de texto simple llamado **nano**:

```bash
nano compose.yml
```

Se abre el editor dentro de la terminal. Escribí (o pegá) tu contenido. Cuando
termines:
- **Guardar:** apretá `Ctrl` + `O`, después Enter.
- **Salir:** apretá `Ctrl` + `X`.

(Abajo, nano te muestra los atajos; `^O` significa `Ctrl+O`.)

### Un ejemplo mínimo que funciona

```yaml
services:
  web:
    image: nginxdemos/hello:plain-text
    restart: unless-stopped
    logging: { driver: json-file, options: { max-size: 10m, max-file: "3" } }
    deploy:
      resources:
        limits: { cpus: "0.25", memory: 128M, pids: 100 }
    ports: ["127.0.0.1:8080:80"]
```

**Qué dice, en criollo:**
- `services:` → acá listás tus contenedores.
- `web:` → el nombre que le ponés a tu contenedor.
- `image:` → qué programa corre adentro (acá, un web de prueba). **Siempre con un
  número de versión** (el `:plain-text`), nunca `latest`.
- `restart: unless-stopped` → si se cae, que se vuelva a prender solo.
- `logging:` → limita el tamaño de los logs (obligatorio).
- `deploy.resources.limits:` → los **topes** de CPU, memoria y procesos
  (obligatorio; es lo que impide que un error tuyo tumbe el servidor).
- `ports: ["127.0.0.1:8080:80"]` → publica el puerto solo **de forma privada**
  (`127.0.0.1`). Vos no exponés nada a Internet; eso lo hace el profe.

> **Cuidado con la indentación (los espacios al inicio de cada línea):** en YAML
> los espacios importan. Usá **2 espacios** por nivel y **nunca Tab**. Si algo
> falla, casi siempre es la indentación.

Las reglas completas están en [la política](docker-compose-policy.md), pero
`labctl` te avisa exactamente qué corregir si algo no cumple.

---

## Paso 4 — Prender tu proyecto con `labctl`

`labctl` es **la única herramienta que usás**. Corré estos comandos **desde la
carpeta de tu equipo**:

```bash
labctl validate    # revisa tu compose SIN prender nada. Empezá siempre por acá.
labctl up          # prende tu proyecto
labctl ps          # muestra tus contenedores y su estado
labctl logs        # muestra los mensajes (logs) de tu app
labctl status      # tu uso de recursos y los límites de tu equipo
labctl usage       # cuánto disco estás usando
labctl restart     # reinicia tus contenedores
labctl down        # apaga todo tu proyecto
```

**Flujo típico:**
1. `labctl validate` → si dice `compose is valid ✔`, seguí. Si no, te lista los
   errores; corregí con `nano compose.yml` y volvé a validar.
2. `labctl up` → deberías ver que baja la imagen y prende el contenedor.
3. `labctl ps` → confirmá que dice `Up` (arriba).
4. `labctl logs` → mirá que tu app arrancó bien.

> `labctl` **nunca** te deja hacer algo peligroso ni salir de tu carpeta. Si te
> rechaza algo, el mensaje te dice qué cambiar.

---

## Paso 5 — Usar la base de datos compartida

No prendas tu propia base de datos: el laboratorio te da una **Postgres** con
usuario y contraseña **solo para tu equipo**. Los datos de conexión están en un
archivo llamado `.shared-services.env` en tu carpeta.

Para usarla, en tu servicio agregá la línea `env_file` y conectá al host
`postgres`:

```yaml
services:
  api:
    image: mi-imagen:1.0
    env_file: .shared-services.env      # <-- carga tu usuario/clave de la base
    restart: unless-stopped
    logging: { driver: json-file, options: { max-size: 10m, max-file: "3" } }
    deploy:
      resources:
        limits: { cpus: "0.5", memory: 256M, pids: 200 }
```

Tu app se conecta a la base usando el nombre `postgres` (por ejemplo
`postgres:5432`). Más detalle en [servicios-compartidos.md](servicios-compartidos.md).

> **No compartas** ese archivo `.shared-services.env` ni lo subas a ningún lado:
> tiene tu contraseña.

---

## Errores comunes (y qué hacer)

| Lo que ves | Qué significa | Qué hacés |
|---|---|---|
| `Compose rechazado por la política…` | tu `compose.yml` viola una regla | leé la lista de abajo del mensaje, corregí con `nano`, y `labctl validate` |
| `no compose file in …` | no hay `compose.yml` en tu carpeta | asegurate de estar en la carpeta de tu equipo (`pwd`) y de haber guardado el archivo |
| `did not find expected key` / error de YAML | mala indentación (espacios) | revisá que uses 2 espacios y nada de Tab |
| `no puedo contactar a labctld` | el servicio del laboratorio no responde | avisá al profe |
| tu app no conecta a la base | te faltó `env_file: .shared-services.env` | agregá esa línea a tu servicio |
| `Permission denied` al hacer algo raro | quisiste salir de tu espacio permitido | quedate dentro de la carpeta de tu equipo y usá solo `labctl` |

---

## Chuleta (todo junto)

```bash
# 1. desde tu notebook: entrar
ssh tu-usuario@servidor

# 2. ir a tu carpeta
cd /srv/classroom/equipo-01

# 3. editar tu proyecto
nano compose.yml         # Ctrl+O guarda, Ctrl+X sale

# 4. validar, prender, mirar
labctl validate
labctl up
labctl ps
labctl logs

# 5. apagar cuando termines
labctl down

# salir del servidor
exit
```

¡Eso es todo! Si algo no sale, releé el mensaje de error (casi siempre te dice qué
corregir) y, si no, preguntale al profe.
