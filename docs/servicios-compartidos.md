# Servicios compartidos — contrato para los equipos

El laboratorio provee tres servicios compartidos, administrados por el operador.
**No los levantás vos**: ya están corriendo. Tu equipo recibe credenciales
propias y aisladas.

| Servicio | Para qué | Hostname |
|---|---|---|
| **PostgreSQL 16** | Base de datos de tu app | `postgres:5432` |
| **Redis 7** | Cache / colas | `redis:6379` |
| **Mailpit** | Servidor SMTP de prueba (ves los mails en una web) | `mailpit:1025` |

## Cómo llegan a tu proyecto

Cuando corrés `labctl up`, el broker conecta estos servicios a la **red privada
de tu proyecto**. Por eso tus contenedores los resuelven por hostname
(`postgres`, `redis`, `mailpit`) — **y ningún otro equipo puede ver tus
contenedores** (cada equipo tiene su propia red).

## Tus credenciales

Están en el archivo **`.shared-services.env`** dentro del directorio de tu
equipo (`/srv/classroom/equipo-NN/.shared-services.env`), legible solo por tu
grupo. Contiene, por ejemplo:

```bash
# PostgreSQL (base propia del equipo)
PGHOST=postgres
PGPORT=5432
PGDATABASE=db_equipo_01
PGUSER=equipo_01
PGPASSWORD=********************
DATABASE_URL=postgresql://equipo_01:********@postgres:5432/db_equipo_01

# Redis (base lógica propia del equipo)
REDIS_URL=redis://redis:6379/1

# Mailpit (SMTP de prueba, sin auth)
SMTP_HOST=mailpit
SMTP_PORT=1025
```

## Cómo usarlas en tu Compose

Cargá el archivo con `env_file` y referenciá las variables:

```yaml
services:
  api:
    image: mi-imagen:1.0
    env_file: .shared-services.env
    restart: unless-stopped
    logging: { driver: json-file, options: { max-size: 10m, max-file: "3" } }
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 256M
          pids: 200
```

> **Importante:** no incluyas `.shared-services.env` en tu repositorio ni lo
> pegues en ningún lado — tiene tu password de base de datos.

## Reglas del contrato

- **Aislamiento:** tu base `db_equipo_NN` y tu usuario `equipo_NN` son solo
  tuyos. No podés acceder a la base de otro equipo.
- **Redis:** usás una base lógica propia (el número al final de `REDIS_URL`). No
  hace falta prefijar claves, pero no asumas que Redis persiste datos (está en
  modo sin persistencia; es cache).
- **Mailpit:** cualquier mail que tu app "envíe" a `mailpit:1025` NO sale a
  Internet — queda en Mailpit para que lo veas. El operador expone la web de
  Mailpit de forma privada.
- **No levantes tu propio Postgres/Redis** — usá los compartidos (ahorra RAM y es
  lo que se evalúa). La política de Compose rechaza volúmenes con nombre
  justamente para que uses estos servicios en lugar de bases propias.
