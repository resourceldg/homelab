# Guía del alumno — conectarse y desplegar tu entorno

Esta guía es todo lo que necesitás para trabajar en el laboratorio. Vas a usar
**una sola herramienta**: `labctl`. **No** tenés (ni necesitás) acceso a Docker,
sudo, ni al socket de Docker.

## 1. Conectarte por SSH

Tu profe te da un usuario (tu nombre) y el laboratorio ya tiene tu clave pública
cargada. Desde tu notebook:

```bash
ssh tu-usuario@<ip-o-host-del-servidor>
```

Si es la primera vez, aceptá la huella del servidor (`yes`). Si te pide password
y no lo esperabas, avisá al profe: el acceso es por **clave SSH**.

## 2. Ir al directorio de tu equipo

Cada equipo tiene su carpeta, y **solo tu equipo puede entrar**:

```bash
cd /srv/classroom/equipo-01     # el número de tu equipo
```

Ahí ponés tu proyecto: el `compose.yml` y los archivos que monte tu app
(configs, etc.). Todo lo que persistas tiene que vivir **dentro de esta carpeta**
(tenés una cuota de disco propia).

## 3. Escribir tu `compose.yml`

Tu Compose tiene que cumplir la [política del laboratorio](docker-compose-policy.md).
En resumen, cada servicio necesita:

- imagen **con tag fijo** (no `latest`),
- límites bajo `deploy.resources.limits`: `cpus`, `memory`, `pids`,
- `logging` (rotación) y `restart`,
- puertos publicados **solo** en `127.0.0.1` (o ninguno),
- montajes **dentro** de tu carpeta (nada de `/`, `/etc`, ni el socket de Docker).

Ejemplo mínimo válido:

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

## 4. Usar `labctl`

Desde tu carpeta:

```bash
labctl validate    # revisa tu compose contra la política (¡empezá siempre por acá!)
labctl up          # despliega
labctl ps          # ver contenedores
labctl logs        # ver logs recientes
labctl usage       # cuánto disco estás usando
labctl status      # estado + límites de tu equipo
labctl restart     # recrea los contenedores
labctl down        # baja todo
```

Si `validate` rechaza algo, te dice **exactamente qué corregir**. Arreglá y
volvé a intentar.

## 5. Servicios compartidos (base de datos, etc.)

No levantes tu propio Postgres/Redis. El laboratorio te da los tuyos, con
credenciales en `.shared-services.env` dentro de tu carpeta. Cargalas con
`env_file` y conectá por hostname (`postgres`, `redis`, `mailpit`). Detalle
completo en [servicios-compartidos.md](servicios-compartidos.md).

## 6. Límites de tu equipo

- **RAM:** hasta ~1.25 GiB para todo tu stack.
- **CPU:** hasta 1 núcleo.
- **Servicios:** máximo 5.
- **Disco:** 20 GB (tope duro).

Si te pasás de RAM, el kernel puede frenar/matar tus contenedores. Usá `labctl
status` y el dashboard **Team Detail** en Grafana para verte.

## 7. Publicar en Internet

**Vos no exponés puertos públicos.** Si tu proyecto tiene que verse desde afuera,
lo pide el profe (operador), que lo publica de forma controlada. Ver
[operator-guide.md](operator-guide.md).

## Problemas comunes

| Síntoma | Causa | Solución |
|---|---|---|
| `Compose rechazado por la política…` | tu compose viola una regla | leé la lista, corregí, `labctl validate` |
| `no compose file in …` | no hay `compose.yml` en tu carpeta | creá `compose.yml` en el dir de tu equipo |
| `no puedo contactar a labctld` | el servicio no está corriendo | avisá al profe |
| tu app no conecta a `postgres` | faltó `env_file: .shared-services.env` | agregalo a tu servicio |
