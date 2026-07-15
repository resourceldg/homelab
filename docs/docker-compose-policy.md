# Política de Docker Compose

Antes de desplegar, `labctld` valida tu `compose.yml` contra estas reglas (código
en `roles/labctl/files/policy.py`, con tests unitarios en
`tests/test_labctl_policy.py`). Si algo no cumple, el despliegue **se rechaza** y
te muestra qué corregir.

## Se RECHAZA

| Regla | Por qué |
|---|---|
| `privileged: true` | daría control casi total del host |
| `network_mode: host`, `pid: host`, `ipc: host` | rompen el aislamiento |
| `userns_mode: host` | rompe el aislamiento de usuarios |
| montar el socket de Docker (`/var/run/docker.sock`) | equivale a ser root del host |
| `cap_add` peligrosas (SYS_ADMIN, NET_ADMIN, SYS_PTRACE, …) | escapes de contenedor |
| bind mounts de `/`, `/etc`, o **fuera** de tu carpeta | acceso a archivos ajenos |
| **volúmenes con nombre** (named volumes) | tu persistencia debe ir en tu carpeta (cuota) |
| imágenes `:latest` o **sin tag** | despliegues no reproducibles |
| puertos en `0.0.0.0` o sin `127.0.0.1` explícito | exposición no controlada |
| top-level `mem_limit` / `pids_limit` | chocan con `deploy` en Compose v2 |
| más de **5 servicios** | límite del laboratorio |

## Se EXIGE en cada servicio

- **Imagen con tag fijo**: `postgres:16.4-alpine`, no `postgres` ni `postgres:latest`.
- **Límites** bajo `deploy.resources.limits`:
  ```yaml
  deploy:
    resources:
      limits: { cpus: "0.5", memory: 256M, pids: 200 }
  ```
- **Logging** (rotación):
  ```yaml
  logging: { driver: json-file, options: { max-size: 10m, max-file: "3" } }
  ```
- **`restart`** (p. ej. `unless-stopped`).
- **`healthcheck`** cuando tenga sentido (recomendado, no obligatorio).

## Publicación de puertos

Solo `127.0.0.1`:

```yaml
ports:
  - "127.0.0.1:8080:80"     # ok: correcto
  # - "8080:80"             # rechazado (queda en 0.0.0.0)
  # - "0.0.0.0:8080:80"     # rechazado
```

Para que tu proyecto se vea desde afuera, no abrís puertos: lo publica el
operador vía Caddy (ver [operator-guide.md](operator-guide.md)).

## Persistencia

Nada de named volumes. Usá un bind mount **dentro de tu carpeta**:

```yaml
volumes:
  - ./datos:/var/lib/lo-que-sea      # ✔ dentro del proyecto (cuenta a tu cuota)
  # - misdatos:/var/lib/...          # ✘ named volume, rechazado
```

Para bases de datos, usá el **Postgres compartido** en lugar de tu propia base
(ver [servicios-compartidos.md](servicios-compartidos.md)).
