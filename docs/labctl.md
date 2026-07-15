# labctl — herramienta y broker

`labctl` es la **única interfaz** de los alumnos con Docker Compose. No entrega
acceso general a Docker: valida, aplica política, corre dentro del slice del
equipo y audita todo.

## Comandos

Se ejecutan **desde el directorio del equipo** (`/srv/classroom/equipo-NN`):

| Comando | Qué hace |
|---|---|
| `labctl validate` | Valida el `compose.yml` contra la [política](docker-compose-policy.md). |
| `labctl up` | Valida y despliega dentro del slice del equipo. |
| `labctl down` | Baja el stack del equipo. |
| `labctl restart` | Recrea los contenedores. |
| `labctl ps` | Lista los contenedores del equipo. |
| `labctl logs` | Últimas líneas de log del stack. |
| `labctl usage` | Uso de disco del directorio del equipo. |
| `labctl status` | Límites del slice + estado de los contenedores. |

## Arquitectura (cliente + daemon broker)

```
alumno → labctl (sin privilegios) → /run/labctld.sock → labctld (root)
                                                          → valida política
                                                          → cgroup_parent=slice
                                                          → docker compose …
                                                          → conecta infra a la red
                                                          → auditoría
```

- **`labctl`** (`/usr/local/bin/labctl`): cliente liviano. Manda la acción por un
  socket Unix. **Nunca toca Docker.**
- **`labctld`** (`/opt/labctl/labctld`, servicio systemd, root): el broker.
  - Identifica al que llama por **SO_PEERCRED** (uid del kernel, no falsificable).
  - Deriva el equipo por pertenencia al grupo `grp-equipo-NN`.
  - Enjaula toda la operación a `/srv/classroom/<equipo>`.
  - Valida el compose con `policy.py`.
  - Inyecta `cgroup_parent=classroom-<equipo>.slice` (techo de recursos duro).
  - Conecta Postgres/Redis/Mailpit/Caddy a la red privada del equipo en el `up`.
  - Registra cada acción en `/var/log/labctl/audit.log`.

El socket es `root:classroom 0660`: solo los alumnos (miembros del grupo
`classroom`) pueden conectarse; el daemon igual reverifica quién llama.

## Seguridad

- Los alumnos **no** están en el grupo `docker`, **no** tienen sudo, **no**
  acceden al socket de Docker.
- El daemon usa `subprocess` con listas de argumentos (**sin shell**), así la
  entrada del alumno no puede inyectar comandos.
- Todo queda auditado (usuario, equipo, acción, resultado).

## Auditoría

```bash
sudo tail -f /var/log/labctl/audit.log
# {"ts":"…","user":"jessi","team":"equipo-01","action":"up","result":"rc=0"}
```
