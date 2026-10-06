# Homelab — servidor del aula, seguro y descripto como código

[![CI](https://github.com/resourceldg/homelab/actions/workflows/ci.yml/badge.svg)](https://github.com/resourceldg/homelab/actions/workflows/ci.yml)

Infraestructura como código (IaC), reproducible y modular, para una computadora con
**Ubuntu LTS** que funciona a la vez como **servidor de desarrollo** y como
**plataforma para proyectos educativos**, incluida un **aula IoT** donde los
equipos de alumnos conectan placas ESP32 por MQTT y ven sus datos en Grafana.

**Autor:** Lucas D. Gómez, arquitecto de software (<resourceldg@gmail.com>). Los
proyectos de los alumnos están atribuidos a sus equipos en el manual (capítulo 14).

📚 **Manual de arquitectura (para empezar desde cero):** arquitectura de software
aplicada al diseño IoT, explicada para principiantes con este servidor como caso
real → [docs/handbook/](docs/handbook/index.md). Para verlo como libro:
`pip install mkdocs-material && mkdocs serve`. **En PDF** (ordenado desde
Fundamentos, con imágenes): [docs/manual-arquitectura-homelab.pdf](docs/manual-arquitectura-homelab.pdf),
se regenera con `python3 scripts/manual-pdf.py`.

## La idea en dos planos

- **Plano del host → Ansible:** sistema operativo, endurecimiento CIS, SSH,
  firewall, Fail2ban, AppArmor, actualizaciones automáticas, auditoría
  (Lynis/AIDE), Tailscale, DuckDNS y Docker.
- **Plano de servicios → Docker Compose:** Caddy (proxy inverso con HTTPS
  automático), login único, monitoreo, servicios del aula y los proyectos.

| Requisito | Cómo se cumple |
|---|---|
| IaC | roles de Ansible + Docker Compose |
| Endurecimiento (CIS) | Ubuntu Security Guide `usg` (CIS nivel 1, opcional) + controles propios |
| SSH | administradores solo con llave, sin `root`; alumnos con contraseña solo desde la LAN o Tailscale |
| Acceso remoto | Tailscale (el SSH nunca está expuesto a internet) |
| Firewall | UFW + `ufw-docker` (cierra el "atajo" que Docker abre en el firewall) |
| Fuerza bruta | Fail2ban (backend systemd, bloqueo vía UFW) |
| Control de acceso obligatorio | AppArmor, todos los perfiles en modo *enforce* |
| Actualizaciones | `unattended-upgrades` (solo seguridad, reinicio 04:30) |
| Auditoría | Lynis (semanal) + AIDE (integridad de archivos, diaria) |
| DNS dinámico | DuckDNS (timer de systemd) + Split DNS dentro del tailnet |
| Monitoreo | Prometheus + Grafana de operación (solo operadores) + node-exporter + cAdvisor; logs con Loki a pedido |
| Aula IoT | broker MQTT compartido `mqtt-aula` (usuario por equipo + ACL), alcanzable por las ESP32 vía Tailscale Funnel; Telegraf → VictoriaMetrics (15 días) → **Grafana del aula**, un folder por equipo |
| Resiliencia ante caídas | watchdog de hardware (reinicio ante congelamientos), guardián de red con escalera de arreglos, latido y resumen al arrancar, vigía externo desde la notebook ([vigia-red.md](docs/vigia-red.md)) |
| Copias de seguridad | Borg con borgmatic (cifradas, retención) — **diseñadas, todavía no activas:** falta un disco en `/mnt/backup` |
| Tests / CI | tests unitarios, gitleaks, yamllint + ansible-lint, chequeo de sintaxis, Molecule (Ubuntu 24.04) en GitHub Actions; testinfra e idempotencia en el servidor |

## Qué corre encima

- **Plataforma de aula:** 5 equipos de alumnos despliegan stacks aislados con
  `labctl`, sin acceso a Docker, `sudo` ni al socket. Ver
  [docs/classroom-architecture.md](docs/classroom-architecture.md) y las guías
  ([alumno](docs/student-guide.md), [operador](docs/operator-guide.md),
  [labctl](docs/labctl.md), [política](docs/docker-compose-policy.md),
  [recursos](docs/resource-model.md),
  [servicios compartidos](docs/servicios-compartidos.md),
  [quién ve qué: login y grupos](docs/control-de-acceso.md)).
- **Aula IoT:** cada equipo conecta sus ESP32 a un broker MQTT compartido y
  autenticado (`mqtt-aula`, publicado por Tailscale Funnel) y ve sus datos en su
  propio Grafana. Ver [docs/aula-iot.md](docs/aula-iot.md) y los capítulos 11 a 15
  del manual.
- **Pañol IoT:** broker MQTT + base de auditoría + Node-RED para el sistema de
  control de acceso al pañol (su código vive en el repo `panol-iot`). Los nodos
  ESP32 reportan a su API (por la LAN, o desde otra red vía Tailscale Funnel) y el
  tablero se publica detrás del login único. Ver [docs/panol-iot.md](docs/panol-iot.md).

Para montar el mismo servidor en otras máquinas o administrar varios sitios:
**[docs/replicar-y-escalar.md](docs/replicar-y-escalar.md)**.

Los diagramas y el porqué de cada decisión están en
[docs/architecture.md](docs/architecture.md). Antes de desplegar (o de volver a
desplegar después de un tiempo), leé
**[docs/deployment-guide.md](docs/deployment-guide.md)**: el recorrido completo,
con el modelo de acceso, cada trampa conocida y cómo recuperarse si te quedás
afuera.

## Estructura del repositorio

```
homelab/
├── ansible/
│   ├── site.yml                 # orquestador (roles con tags)
│   ├── ansible.cfg              # por defecto usa inventories/production
│   ├── group_vars/all/main.yml  # constantes comunes a todos los entornos
│   ├── inventories/
│   │   ├── production/
│   │   │   ├── hosts.ini
│   │   │   └── group_vars/all/  # identidad, red y dominio de prod + vault + roster del aula
│   │   └── staging/
│   │       ├── hosts.ini
│   │       └── group_vars/all/  # ajustes de staging + vault
│   └── roles/                   # cada rol trae sus defaults/main.yml
│       ├── bootstrap/ users_ssh/ tailscale/ ddns/ dns/ vigia_red/
│       ├── firewall/ fail2ban/ apparmor/ hardening/ auto_updates/ audit/
│       ├── docker/ monitoring/ backups/ authelia/
│       ├── classroom/ shared_services/ labctl/ classroom_publish/   # plataforma de aula
│       ├── aula_iot/            # aula IoT: Telegraf + VictoriaMetrics + Grafana del aula
│       └── panol/               # pañol IoT (MQTT + base de auditoría)
├── compose/
│   ├── proxy/                   # Caddy (compilado con DuckDNS para DNS-01)
│   ├── dashboard/               # Homepage (página de inicio con enlaces)
│   ├── monitoring/              # Prometheus + Grafana + exporters
│   ├── logs/                    # Loki + Alloy (a pedido: make logs-on)
│   ├── auth/                    # Authelia (login único)
│   ├── shared-data/             # servicios compartidos del aula + broker mqtt-aula
│   ├── aula-iot/                # capa de visualización del aula IoT
│   ├── apps/                    # proyecto educativo de ejemplo
│   └── panol/                   # pañol IoT: Mosquitto + Postgres + Node-RED
├── tests/                       # tests unitarios, testinfra y playbook de verificación
├── docs/                        # arquitectura, guías y el manual (handbook/)
└── Makefile                     # interfaz del operador (make help)
```

## Puesta en marcha rápida

Requisitos: Ubuntu **24.04 LTS** recién instalado (objetivo principal; 26.04
planificado), un usuario con `sudo`, un token de DuckDNS y tu llave pública SSH.

> Ubuntu Pro es **opcional** y está apagado por defecto (`usg_enabled: false`).
> Solo habilita la herramienta CIS `usg`; todo el endurecimiento complementario
> (sysctl, pwquality, core dumps, AppArmor, Fail2ban…) se aplica igual sin él.

```bash
# 0. Clonar en el servidor (o en una compu de control con acceso SSH).
git clone <este-repo> homelab && cd homelab

# 1. Instalar dependencias.
make deps

# 2. Completar los datos del entorno (producción por defecto).
$EDITOR ansible/inventories/production/group_vars/all/main.yml  # llaves, dominio, red (lan_cidr)…
make vault-create                            # crea y cifra los secretos del entorno
echo "tu-clave-del-vault" > ~/.vault_pass && chmod 600 ~/.vault_pass

# 3. Ver qué cambiaría (sin cambiar nada).
make dry-run                                 # agregar ENV=staging para staging

# 4. Aplicar.
make apply                                   # o: make apply ENV=staging

# 5. Autenticar Tailscale (una sola vez, interactivo).
sudo tailscale up --ssh --accept-routes

# 6. Verificar.
make verify        # chequeos de postura dentro de Ansible
make test          # pruebas testinfra sobre el servidor
make idempotence   # prueba que una segunda corrida no cambia nada
```

Después, el Grafana de operación queda en `https://grafana.<tu-dominio>`, el del
aula en `https://grafana-aula.<tu-dominio>` y la app de ejemplo en
`https://demo.<tu-dominio>`. En este despliegue esos nombres apuntan a la **IP de
Tailscale** (Split DNS), así que se entra por Tailscale.

## Precauciones

- **Primero `make dry-run`.** El endurecimiento cambia SSH y el firewall:
  asegurate de tener Tailscale o acceso a la consola antes de cerrar el SSH remoto.
- **`.vault_pass` y `vault.yml` están en `.gitignore`.** Nunca subas secretos
  descifrados.
- **Redirección de puertos en el router:** solo 80/443 → servidor, y solo si
  querés los proyectos accesibles desde internet. Hoy no está configurada: todo va
  por Tailscale, y las placas por Funnel.
- Perder `vault_borg_passphrase` es perder las copias de seguridad: guardala en un
  gestor de contraseñas.
- **La red local puede cambiar** (el servidor ya se mudó tres veces). Si cambia,
  actualizá `lan_cidr` y aplicá `--tags firewall,ssh -K` (el firewall y el
  bloque `Match Address` de `sshd` lo usan los dos); mientras tanto se entra por
  Tailscale.
- **Ubuntu 26.04 recién salido:** si el repositorio de Docker o de Tailscale da
  404 porque todavía no publicaron la versión nueva, poné
  `apt_repo_release: "noble"` en `main.yml` hasta que la publiquen.

## Operaciones comunes

| Tarea | Comando |
|---|---|
| Aplicar solo la seguridad | `make harden` |
| Aplicar solo el firewall | `make firewall` |
| Redesplegar monitoreo y proxy | `make monitoring` |
| Aplicar todo el aula (alumnos, broker, Grafana del aula) | `cd ansible && ansible-playbook site.yml --tags classroom -K` |
| Editar secretos | `make vault-edit` |
| Correr una copia de seguridad ya | `make backups` |
| ¿Cómo entro al servidor ahora? | `make como-conectar` |
| Logs en vivo (se apagan solos) | `make logs-on` |
| Lint | `make lint` |

Más en [docs/runbook.md](docs/runbook.md).
