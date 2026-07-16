# Glosario

Cada entrada tiene una **definición simple**, una **técnica** y **dónde aparece**
en este proyecto. Ordenado alfabéticamente.

### ACL (Access Control List)
- **Simple:** una lista de reglas de "quién puede hacer qué".
- **Técnica:** conjunto de reglas de autorización asociadas a un recurso.
- **Dónde:** las reglas SSH de Tailscale (modo `check` vs `accept`); las reglas de
  acceso por grupo de Authelia.

### ACME
- **Simple:** el protocolo para pedir certificados HTTPS automáticamente.
- **Técnica:** *Automated Certificate Management Environment*; lo usan Let's
  Encrypt y ZeroSSL.
- **Dónde:** Caddy lo usa (con el desafío DNS-01 de DuckDNS) para emitir/renovar
  los certificados solo.

### AIDE
- **Simple:** un "detector de cambios" en archivos del sistema.
- **Técnica:** *Advanced Intrusion Detection Environment*; guarda huellas de los
  archivos y avisa si cambian.
- **Dónde:** rol `audit`, corre por un timer.

### Ansible
- **Simple:** una herramienta para configurar servidores escribiendo archivos.
- **Técnica:** motor de automatización/IaC sin agente, declarativo e idempotente.
- **Dónde:** todo el plano del host. Ver [cap. 4](04-ansible-iac.md).

### AppArmor
- **Simple:** un "chaleco" que limita qué puede hacer cada programa.
- **Técnica:** módulo de seguridad del kernel (MAC) basado en perfiles por
  programa.
- **Dónde:** rol `apparmor`, en modo enforce.

### Authelia
- **Simple:** el portal de login único (SSO) del laboratorio.
- **Técnica:** servidor de autenticación/forward-auth con reglas por grupo.
- **Dónde:** stack `auth`, integrado a Caddy con `forward_auth`. Ver
  [cap. 7](07-seguridad.md).

### Backup
- **Simple:** una copia de seguridad de los datos.
- **Técnica:** respaldo versionado y cifrado (aquí, con Borg/borgmatic).
- **Dónde:** rol `backups`; requiere un disco montado en `/mnt/backup`.

### Bind mount
- **Simple:** montar una carpeta del server dentro de un contenedor.
- **Técnica:** mapeo directo de una ruta del host a una ruta del contenedor.
- **Dónde:** los alumnos guardan datos así (obligatorio por la política).

### Caddy
- **Simple:** el portero web: recibe todo y reparte, con HTTPS automático.
- **Técnica:** servidor web / proxy inverso con gestión automática de TLS.
- **Dónde:** stack `proxy`; única entrada web. Ver [cap. 5](05-servicios.md).

### cAdvisor
- **Simple:** mide cuánto consume cada contenedor.
- **Técnica:** *Container Advisor*; exporta métricas por contenedor a Prometheus.
- **Dónde:** stack `monitoring`.

### cgroup
- **Simple:** un mecanismo para limitar recursos de un grupo de procesos.
- **Técnica:** *control group* del kernel (v2); limita CPU/RAM/PIDs.
- **Dónde:** límites de compose + slices de systemd por equipo.

### CI (Integración Continua)
- **Simple:** robots que revisan tu código cada vez que subís cambios.
- **Técnica:** pipeline automatizado (lint, tests) en cada push/PR.
- **Dónde:** GitHub Actions (`.github/workflows/ci.yml`). Ver [cap. 8](08-pipeline.md).

### Compose (Docker Compose)
- **Simple:** describir contenedores en un archivo y prenderlos juntos.
- **Técnica:** herramienta para definir apps multi-contenedor en YAML.
- **Dónde:** todo el plano de servicios (`compose/`).

### Contenedor
- **Simple:** una imagen en ejecución, aislada.
- **Técnica:** proceso(s) aislados con namespaces + cgroups.
- **Dónde:** todos los servicios y proyectos de alumnos.

### Daemon
- **Simple:** un servicio que corre de fondo, permanente.
- **Técnica:** proceso en segundo plano (suele terminar en `d`).
- **Dónde:** `dockerd`, `sshd`, `tailscaled`, `labctld`, `dnsmasq`.

### Dashboard
- **Simple:** un tablero con gráficos.
- **Técnica:** conjunto de paneles de visualización (en Grafana).
- **Dónde:** los 3 dashboards del aula + el de homelab.

### DDNS / DuckDNS
- **Simple:** mantener un dominio apuntando a tu casa aunque cambie tu IP.
- **Técnica:** DNS dinámico; DuckDNS es un proveedor gratuito.
- **Dónde:** rol `ddns`, con un timer que actualiza la IP.

### DevSecOps
- **Simple:** desarrollar, asegurar y operar, todo integrado y automatizado.
- **Técnica:** cultura/práctica que integra seguridad en el ciclo Dev+Ops.
- **Dónde:** el pipeline (CI, lint, tests, gitleaks). Ver [cap. 8](08-pipeline.md).

### DNS
- **Simple:** la guía telefónica que traduce nombres a IPs.
- **Técnica:** *Domain Name System*.
- **Dónde:** DuckDNS (público) + dnsmasq (Split DNS del tailnet).

### Docker
- **Simple:** empaquetar y correr apps en contenedores.
- **Técnica:** plataforma de contenedores (engine + CLI + formatos).
- **Dónde:** el corazón del plano de servicios y de aula. Ver [cap. 3](03-docker.md).

### Exporter
- **Simple:** un programita que "traduce" métricas a un formato que Prometheus
  entiende.
- **Técnica:** endpoint HTTP que expone métricas en formato Prometheus.
- **Dónde:** `node-exporter` (host), `cAdvisor` (contenedores).

### Filesystem
- **Simple:** cómo se organizan los archivos en el disco.
- **Técnica:** estructura jerárquica desde `/`.
- **Dónde:** `/opt/homelab/stacks`, `/srv/classroom`, loopbacks de cuota.

### Grafana
- **Simple:** la app que muestra los gráficos de las métricas.
- **Técnica:** plataforma de visualización de series temporales.
- **Dónde:** stack `monitoring`, detrás de Authelia.

### HTTPS / TLS
- **Simple:** la web con candado (cifrada).
- **Técnica:** HTTP sobre TLS; requiere un certificado válido.
- **Dónde:** lo maneja Caddy automáticamente.

### IaC (Infraestructura como Código)
- **Simple:** definir la infraestructura en archivos de texto versionables.
- **Técnica:** gestionar servidores/servicios de forma declarativa y reproducible.
- **Dónde:** todo el repo (Ansible + Compose).

### Idempotencia
- **Simple:** aplicar algo dos veces da el mismo resultado que una.
- **Técnica:** propiedad que garantiza convergencia sin efectos acumulativos.
- **Dónde:** todos los playbooks de Ansible.

### Imagen
- **Simple:** la plantilla de una app (molde).
- **Técnica:** artefacto de solo lectura en capas.
- **Dónde:** cada `image:` de los compose.

### inode
- **Simple:** la ficha interna de un archivo en el disco.
- **Técnica:** estructura del filesystem con metadatos y punteros a los datos.
- **Dónde:** el bug del Caddyfile (bind mount al inode viejo). Ver [cap. 10](10-casos-practicos.md).

### labctl / labctld
- **Simple:** la única herramienta con la que los alumnos manejan sus contenedores.
- **Técnica:** cliente + daemon broker (Python) que valida y ejecuta compose.
- **Dónde:** roles `labctl`. Ver [cap. 9](09-plataforma-aula.md).

### LAN
- **Simple:** tu red local (casa, aula).
- **Técnica:** *Local Area Network*, con IPs privadas.
- **Dónde:** `lan_cidr: 192.168.100.0/24`.

### Mermaid
- **Simple:** una forma de escribir diagramas con texto.
- **Técnica:** lenguaje para diagramas embebibles en Markdown.
- **Dónde:** todos los diagramas de este manual.

### Métrica
- **Simple:** un número medido en el tiempo (uso de CPU, RAM…).
- **Técnica:** serie temporal con nombre y etiquetas.
- **Dónde:** Prometheus las guarda; Grafana las muestra.

### NAT
- **Simple:** el router comparte una IP pública entre muchos dispositivos.
- **Técnica:** *Network Address Translation*.
- **Dónde:** por eso hace falta port-forward para el acceso público.

### node-exporter
- **Simple:** mide el estado del server (CPU, RAM, disco).
- **Técnica:** exporter de métricas del host para Prometheus.
- **Dónde:** stack `monitoring`.

### OOM (Out Of Memory)
- **Simple:** cuando se acaba la memoria y el kernel mata procesos.
- **Técnica:** *Out Of Memory killer* del kernel.
- **Dónde:** lo previenen los límites de RAM por equipo.

### Playbook
- **Simple:** la "receta" de Ansible: qué configurar y en qué orden.
- **Técnica:** archivo YAML que orquesta roles/tareas sobre un inventario.
- **Dónde:** `ansible/site.yml`.

### Puerto
- **Simple:** el "interno" de un servicio dentro de una IP.
- **Técnica:** número (0-65535) que identifica un endpoint TCP/UDP.
- **Dónde:** 443 (Caddy), 22 (SSH), 5432 (Postgres), 9090 (Prometheus)…

### PostgreSQL
- **Simple:** una base de datos.
- **Técnica:** motor de base de datos relacional.
- **Dónde:** servicio compartido multi-tenant (una DB por equipo).

### Prometheus
- **Simple:** el que junta y guarda las métricas.
- **Técnica:** base de datos de series temporales + scraper + PromQL.
- **Dónde:** stack `monitoring`. Ver [cap. 6](06-observabilidad.md).

### PromQL
- **Simple:** el idioma para consultar las métricas de Prometheus.
- **Técnica:** lenguaje de consulta de series temporales.
- **Dónde:** las queries de los dashboards.

### Proxy inverso
- **Simple:** un portero que recibe todo y reparte a los servicios.
- **Técnica:** proxy del lado del servidor (single entry point).
- **Dónde:** Caddy.

### Role (Ansible)
- **Simple:** una carpeta con todo lo necesario para configurar una cosa.
- **Técnica:** unidad reutilizable de tareas/plantillas/variables.
- **Dónde:** `ansible/roles/*`.

### root
- **Simple:** el usuario que puede todo.
- **Técnica:** superusuario, UID 0.
- **Dónde:** se evita; los servicios usan cuentas sin privilegios.

### SSH
- **Simple:** entrar a la terminal de otra máquina de forma segura.
- **Técnica:** *Secure Shell*; acceso remoto cifrado, normalmente con claves.
- **Dónde:** administración del server (rol `users_ssh`).

### systemd
- **Simple:** el que prende y cuida los servicios del sistema.
- **Técnica:** init/manager de servicios (PID 1).
- **Dónde:** timers, slices, `labctld`, `dnsmasq`.

### Tailscale / Tailnet
- **Simple:** tu red privada propia para llegar al server desde cualquier lado.
- **Técnica:** red mesh basada en WireGuard; el *tailnet* es tu red.
- **Dónde:** acceso remoto seguro + Split DNS. Ver [cap. 7](07-seguridad.md).

### TCP
- **Simple:** enviar datos por red de forma confiable.
- **Técnica:** protocolo de transporte con control de entrega/orden.
- **Dónde:** web, SSH, bases de datos.

### UFW
- **Simple:** el firewall (decide qué puertos se abren).
- **Técnica:** *Uncomplicated Firewall*, front-end de iptables.
- **Dónde:** rol `firewall` (default deny).

### Vault (Ansible Vault)
- **Simple:** una caja fuerte para las contraseñas dentro del repo.
- **Técnica:** archivo cifrado que Ansible descifra al aplicar.
- **Dónde:** `inventories/*/group_vars/all/vault.yml`.

### YAML
- **Simple:** un formato de texto para configuraciones, sensible a la sangría.
- **Técnica:** lenguaje de serialización legible por humanos.
- **Dónde:** compose, playbooks, inventarios, dashboards.

---

> ¿Falta un término? Está anotado en [Mejoras futuras](mejoras-futuras.md) para
> agregarlo. Este glosario crece con el manual.
