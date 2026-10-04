# Guía de despliegue — servidor homelab

> **Leé esto primero si volvés después de un tiempo.** Esta guía guarda el
> **porqué** de cada decisión y las trampas que no son obvias y que se
> descubrieron desplegando este servidor de verdad: lo que es fácil de olvidar en
> seis meses. La primera vez se lee de arriba abajo; después, se usa de consulta.

**Para quién:** el operador, y quien quiera aprender infraestructura como código
usando este repositorio como ejemplo. La explicación para principiantes está en el
[manual](handbook/index.md).

---

## Índice

1. [Qué es este servidor](#1-qué-es-este-servidor)
2. [El modelo de acceso (leelo antes de tocar SSH)](#2-el-modelo-de-acceso)
3. [Estructura del repositorio y capas de variables](#3-estructura-del-repositorio-y-capas-de-variables)
4. [Dónde vive cada cosa en el servidor](#4-dónde-vive-cada-cosa-en-el-servidor)
5. [Desplegar desde cero: el procedimiento seguro](#5-desplegar-desde-cero)
6. [El diseño anti-bloqueo de SSH](#6-el-diseño-anti-bloqueo-de-ssh)
7. [Trampas y lecciones (la sección para "vos del futuro")](#7-trampas-y-lecciones)
8. [Operación del día a día](#8-operación-del-día-a-día)
9. [Copias de seguridad (pendientes)](#9-copias-de-seguridad)
10. [Verificación y chequeos de salud](#10-verificación-y-chequeos-de-salud)
11. [Diagnóstico de problemas](#11-diagnóstico-de-problemas)
12. [Recuperación de emergencia](#12-recuperación-de-emergencia)
13. [Cómo se llega a los servicios](#13-cómo-se-llega-a-los-servicios)

---

## 1. Qué es este servidor

Una sola máquina con Ubuntu **24.04 LTS** (nombre `homelab-01`) que es a la vez
**servidor de la casa** y **plataforma para proyectos educativos** (el aula y el
aula IoT). Se maneja completamente como código, en dos planos:

- **Plano del host → Ansible.** Sistema operativo, usuarios y SSH, firewall,
  Fail2ban, AppArmor, endurecimiento del kernel, actualizaciones automáticas,
  auditoría Lynis/AIDE, Tailscale, DuckDNS, instalación de Docker.
- **Plano de servicios → Docker Compose.** Caddy como proxy inverso (HTTPS
  automático con el desafío DNS-01 de DuckDNS), login único (Authelia),
  monitoreo (Prometheus + Grafana con node-exporter y cAdvisor), los servicios
  del aula y los proyectos.

**Sin Ubuntu Pro.** La herramienta CIS/USG queda apagada (`usg_enabled: false`);
todo el endurecimiento **complementario** (sysctl, pwquality, AppArmor, Fail2ban,
módulos bloqueados, login) se aplica igual sin token de Pro. El objetivo hoy es
24.04, con un pase futuro a 26.04 (para cuando los repositorios de los
proveedores tarden en publicar la versión nueva existe la salida
`apt_repo_release`).

---

## 2. El modelo de acceso

**Esta es la sección más importante. Entendela antes de correr cualquier tarea
de SSH: es lo que evita que te quedes afuera.**

Hay **tres formas de entrar**, y son independientes:

| Camino | Usuario | Cómo se autentica | ¿Lo afecta el endurecimiento de OpenSSH? |
|---|---|---|---|
| **Consola local** (física / escritorio) | `homelab` | login del escritorio | **No**: siempre funciona |
| **Tailscale SSH** | `ansible` (desde la notebook) | identidad y ACL de Tailscale | **No**: no pasa por el `sshd` del sistema |
| **OpenSSH directo** (LAN o tailnet) | `ansible`, `homelab` (llave); alumnos (contraseña, solo LAN/tailnet) | llave pública / contraseña | **Sí** |

### Por qué importa

El endurecimiento de SSH de Ansible (`PasswordAuthentication no`, `AllowUsers`,
cifrado fuerte) solo gobierna al **daemon OpenSSH del sistema**: la fila de
*OpenSSH directo*. **Tailscale SSH lo sirve `tailscaled`, no `sshd`**, así que
autentica por el tailnet sin importar `/etc/ssh/sshd_config`. Por eso se puede
endurecer OpenSSH a fondo sin perder el acceso diario por Tailscale, y por eso,
en el peor caso, siguen quedando la consola y Tailscale SSH como redes de
seguridad.

### Las cuentas

- **`ansible`:** la cuenta de automatización. **`sudo` sin contraseña** (un
  archivo NOPASSWD en `/etc/sudoers.d`) porque Ansible necesita escalar
  privilegios sin intervención. Es la identidad para Tailscale SSH desde la
  notebook.
- **`homelab`:** tu cuenta personal / de escritorio. **`sudo` CON contraseña**
  (en el grupo `sudo`, sin NOPASSWD). Con ella entrás a la consola, y es la dueña
  del repositorio clonado. Está en `AllowUsers`, así que también entra por SSH con
  llave.
- **Alumnos** (`jessi`, `mijael`, `jorge`…): sin `sudo` ni Docker; entran por SSH
  **con contraseña** solo desde la LAN o el tailnet (bloque `Match Group
  classroom`), y solo pueden abrir túneles locales (`-L`).
- **`familia`:** (opcional, sin crear) cuenta de uso diario: sin `sudo`,
  `ssh: false`; entra al escritorio pero nunca por SSH.

### Las llaves

La **notebook** del operador (`zen-precision-3561`, usuario `zen`) tiene una
llave **privada** ed25519. Su llave **pública** está en los group_vars de
producción y Ansible la instala en `authorized_keys` de `ansible` y `homelab`. Las
llaves públicas se pueden subir al repositorio sin problema; la privada nunca sale
de la notebook.

> Tailscale SSH **no** usa `authorized_keys`: la llave tradicional es el **plan
> B** para OpenSSH directo (por ejemplo, si Tailscale se cae).

---

## 3. Estructura del repositorio y capas de variables

La configuración se resuelve en **tres capas de precedencia** (de menor a mayor):

```
roles/<rol>/defaults/main.yml          # 1. ajustes del rol (valores razonables)
group_vars/all/main.yml                # 2. constantes comunes, iguales en todos lados
inventories/<entorno>/group_vars/all/  # 3. identidad, red y secretos del entorno
```

- Cada rol trae valores que funcionan, así es autocontenido y reutilizable.
- `group_vars/all` solo tiene lo que comparten varios roles y nunca cambia entre
  entornos (`admin_user`, `ssh_port`, `apt_repo_release`, `stacks_root`).
- `inventories/production/` e `inventories/staging/` traen cada uno su
  `hosts.ini`, un `group_vars/all/main.yml` (identidad, red, dominio), el roster
  del aula (`classroom.yml`, en producción) y un `vault.yml` cifrado (secretos). Se
  elige con `-i inventories/<entorno>` o `make <target> ENV=staging`.

```
ansible/
├── site.yml                     # orquestador (roles con tags por plano)
├── ansible.cfg                  # por defecto usa inventories/production
├── group_vars/all/main.yml      # constantes comunes
├── inventories/
│   ├── production/{hosts.ini, group_vars/all/{main,classroom,vault}.yml}
│   └── staging/{hosts.ini, group_vars/all/{main,vault}.yml}
└── roles/                       # cada rol: defaults/ tasks/ meta/ [templates/ handlers/ molecule/]
```

---

## 4. Dónde vive cada cosa en el servidor

**Estas rutas nos complicaron durante el despliegue: anotalas.**

| Qué | Dónde | Nota |
|---|---|---|
| Repositorio clonado | `/home/homelab/homelab` | dentro del **home del usuario `homelab`**, no en `/home/homelab` |
| Entorno Python con Ansible | `/home/homelab/homelab/.venv` | lo crea `make deps` |
| Programa `ansible-playbook` | `~/homelab/.venv/bin/ansible-playbook` | **no está en el `$PATH`**: llamalo por la ruta completa o activá el venv |
| Clave del vault | `~/.vault_pass` (o sea `/home/homelab/.vault_pass`) | `ansible.cfg` apunta ahí; es por usuario |
| Vault cifrado | `ansible/inventories/production/group_vars/all/vault.yml` | se movió acá desde el viejo `ansible/group_vars/all/vault.yml` |
| Stacks de Compose (desplegados) | `/opt/homelab/stacks` | `stacks_root` |
| Proyectos de los equipos | `/srv/classroom/equipo-NN` | uno por equipo, con cuota |
| Secretos generados en el host | `/etc/classroom/secrets/`, `/etc/panol/secrets/` | solo `root` |
| Repositorio de Borg | `/mnt/backup/borg-repo` | necesita un disco **montado** (ver §9) |

**Corré Ansible como el usuario `homelab`**, desde el repositorio clonado, con el
binario del venv. Como `homelab` tiene **`sudo` con contraseña**, tenés que pasar
`-K` (`--ask-become-pass`) para que Ansible pueda escalar: `ansible.cfg` tiene
`become_ask_pass = False`, así que sin `-K` la corrida falla con "sudo: a password
is required". (La cuenta `ansible` tiene `sudo` sin contraseña, pero el repositorio
vive en el home de `homelab`, así que lo práctico es `homelab` + `-K`.)

---

## 5. Desplegar desde cero

La regla de oro: **nunca endurezcas SSH antes de haber probado que podés seguir
entrando.** Dejá **una sesión de consola abierta** todo el tiempo como último
recurso.

> **Atajo guiado:** `scripts/bootstrap-production.sh` recorre estos mismos pasos
> en orden y frena a pedir confirmación antes de lo irreversible (el cierre de
> SSH). Se puede volver a correr: cada fase se puede saltear si ya está hecha.
> Esta sección explica qué hace cada paso y por qué.

### 5.0 Requisitos

- Ubuntu 24.04, el usuario `homelab` con `sudo`, Tailscale instalado y autenticado.
- La llave **pública** ed25519 de tu notebook (generala con
  `ssh-keygen -t ed25519` si no tenés; la privada queda en la notebook).

### 5.1 Traer el código al día

```bash
cd ~/homelab            # /home/homelab/homelab
git status              # tiene que decir "clean" (el vault.yml sin trackear está bien, ver 5.2)
git pull
```

### 5.2 Mover el vault (una vez, solo si venís de la estructura vieja)

El vault cifrado antes vivía en `ansible/group_vars/all/vault.yml`; la estructura
nueva lo espera por entorno. En la ruta nueva está en `.gitignore`, así que se mueve:

```bash
mv ansible/group_vars/all/vault.yml \
   ansible/inventories/production/group_vars/all/vault.yml
```

> Después de `git pull`, el vault en la ruta vieja aparece **sin trackear** (el
> `.gitignore` nuevo solo ignora la ruta por entorno). No lo agregues con
> `git add`: solo movelo.

### 5.3 Cargar los valores REALES en los group_vars de producción

Editá `ansible/inventories/production/group_vars/all/main.yml`:

- `lan_cidr` — **la red real de la casa** (averiguala con `hostname -I`). Si está
  mal, el firewall te bloquea en tu propia red sin avisar (ver §7).
- `admin_ssh_authorized_keys` — la llave pública real de la notebook (para `ansible`).
- `extra_users` — tu cuenta (`homelab`, `ssh: true`, en `sudo`, llave real).
- `server_timezone` / `server_locale` — por ejemplo
  `America/Argentina/Buenos_Aires`, `es_AR.UTF-8`.

No puede quedar ningún `REPLACE_ME` en una cuenta con `ssh: true`, o la guarda de
seguridad corta el play.

### 5.4 Asegurar las herramientas

```bash
make deps               # crea .venv e instala ansible-core + colecciones + herramientas
```

### 5.5 SSH — fase 1: usuarios y llaves, SIN cerrar nada

```bash
cd ~/homelab/ansible
~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production \
    --tags ssh --skip-tags ssh-lockdown -K
```

Crea o asegura las cuentas e instala las llaves, pero no toca `sshd`.

### 5.6 Arreglar el firewall para que tu red real esté permitida

Si la máquina se configuró antes con un `lan_cidr` equivocado, UFW sigue
bloqueando tu red. Aplicá el rol del firewall para agregar la regla correcta
**antes** de probar el SSH directo:

```bash
~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production \
    --tags firewall -K
```

### 5.7 PROBAR el acceso antes de endurecer (no te lo saltees)

Desde la **notebook**, por la LAN (así pega en OpenSSH y no en Tailscale SSH):

```bash
ssh homelab@<IP-LAN-del-server>      # hostname -I en el server
ssh ansible@<IP-LAN-del-server>
```

Las dos tienen que entrar con la llave. Si un usuario recibe
`Permission denied (publickey)` pero **llegás** al cartel de bienvenida, es un
problema de `AllowUsers` en el `sshd_config` **que está corriendo**, y lo arregla
el paso siguiente (§5.8). Si en cambio da **timeout**, el firewall sigue
bloqueando tu red: revisá `lan_cidr` y repetí §5.6.

### 5.8 SSH — fase 2: aplicar la configuración endurecida

```bash
~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production \
    --tags ssh -K
```

Primero corren las guardas (llave real presente, sin marcador, archivo en disco);
después se escribe el `sshd_config` endurecido (validado con `sshd -t`) y se
reinicia `sshd`. **Las sesiones abiertas no se cortan.** Repetí §5.7: la cuenta que
antes era rechazada ahora tiene que entrar.

### 5.9 Aplicar todo lo demás

¿Todavía no hay disco para copias? Salteá `backups` (la guarda de montaje cortaría,
y estaría bien que lo haga):

```bash
~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production \
    --skip-tags backups -K
```

Aplica el endurecimiento, Fail2ban, AppArmor, la auditoría (la base de AIDE se
inicializa y **puede tardar varios minutos**), las actualizaciones, Docker, los
stacks de servicios y el aula. Poné una contraseña a `homelab` para que funcione el
`sudo` con contraseña: `sudo passwd homelab`.

### 5.10 Tailscale y verificación

```bash
sudo tailscale up --ssh --accept-routes    # si no está levantado
make verify && make test                   # chequeos de postura + pruebas testinfra
```

---

## 6. El diseño anti-bloqueo de SSH

El rol `users_ssh` está partido en dos etapas para que una primera corrida no te
deje afuera:

- **Etapa 1 (arranque, tags `ssh`,`bootstrap`):** crea la cuenta de
  administración/automatización, las `extra_users`, instala todas las llaves y
  configura `sudo`. **Nunca restringe el login.** Siempre es seguro correrla.
- **Etapa 2 (cierre, tag `ssh-lockdown`):** escribe el `sshd_config` restrictivo y
  reinicia `sshd`. La protegen:
  - `ssh_lockdown_enabled` (por defecto `true`; en `false` posterga todo el cierre),
  - una **guarda** que verifica que `admin_ssh_authorized_keys` sea una llave real
    (sin `REPLACE_ME`) y que `/home/<admin>/.ssh/authorized_keys` exista y no esté
    vacío,
  - una segunda guarda que verifica que cada `extra_users` con `ssh: true` tenga
    una llave real, así nunca se agrega a `AllowUsers` una cuenta a la que no se
    puede entrar.

`AllowUsers` se **calcula**: `admin_user` más cada `extra_users` con `ssh: true`
(y los alumnos, que entran por el bloque `Match Group classroom`). Para saltear
todo el cierre en una primera corrida riesgosa: `--skip-tags ssh-lockdown`.

---

## 7. Trampas y lecciones

**Lo que nos costó tiempo: revisá esto primero cuando algo está raro.**

1. **`lan_cidr` tiene que coincidir con la red real.** El valor por defecto era
   `192.168.1.0/24`, la red real era `192.168.100.0/24`, y después el servidor se
   mudó a `192.168.0.x` y a `192.168.8.x`. Si no coincide, UFW descarta el SSH
   desde tu propia notebook → **timeout** (no "refused"). También achica el bloque
   `Match Address` de `sshd`. Confirmalo con `hostname -I`.
2. **Tailscale SSH ≠ OpenSSH.** Endurecer `sshd_config` **no** afecta a Tailscale
   SSH (lo sirve `tailscaled`). Por eso la cuenta de automatización siguió
   accesible todo el tiempo, y por eso es una red de seguridad confiable.
   Consecuencia: para probar el camino de **llave de OpenSSH** hay que conectarse
   a la **IP de la LAN**, no a la `100.x` del tailnet (que la intercepta Tailscale
   SSH).
3. **`AllowUsers` rechaza antes de probar la llave.** Una llave correcta con
   permisos correctos igual da `Permission denied (publickey)` si el usuario no
   está en el `AllowUsers` del `sshd_config` que está corriendo. Una config vieja
   puede listar solo `ansible`; volver a aplicar la actual lo arregla.
4. **Correr como `homelab` con `-K`.** `ansible-playbook` no está en el `$PATH`
   (está en `~/homelab/.venv/bin`), y `homelab` tiene `sudo` con contraseña, así
   que cada corrida necesita `-K`. La cuenta `ansible` no pide contraseña pero no
   puede leer el repositorio en el home de `homelab`.
5. **El vault se movió.** Ahora está por entorno en
   `inventories/production/group_vars/all/vault.yml`. Después de un `git pull` en
   un clon viejo, movelo una vez (§5.2).
6. **Lo hecho a mano es provisorio.** Cuando algo se levanta a mano en el servidor
   (pasó con el broker del aula), hay que pasarlo al repositorio y verificar que
   coincidan: si no, la próxima corrida de Ansible lo deshace (*drift*, ver el
   capítulo 4 del manual).

Notas que no bloquean:

- `DEPRECATION WARNING: INJECT_FACTS_AS_VARS` sale en cada corrida: es inofensivo
  (ansible-core deja de recomendar `ansible_distribution` suelto). Limpiar algún día.
- "connection is not using a post-quantum key exchange" es un aviso del cliente
  OpenSSH, no un error.

---

## 8. Operación del día a día

Todo pasa por los tags de `site.yml`. Como usuario `homelab`, con la ruta del venv
y `-K`:

| Tarea | Comando |
|---|---|
| Ver qué cambiaría | `ansible-playbook site.yml -i inventories/production --check --diff -K` |
| Solo el plano de seguridad | `... --tags security -K` |
| Solo el firewall | `... --tags firewall -K` |
| Redesplegar monitoreo + proxy | `... --tags "services,docker" -K` |
| Todo el aula (alumnos, broker, Grafana del aula) | `... --tags classroom -K` |
| Solo la capa de Grafana del aula | `... --tags aula-iot -K` |
| El pañol | `... --tags panol -K` |
| Volver a aplicar SSH (arranque + cierre) | `... --tags ssh -K` |
| Editar secretos | `ansible-vault edit inventories/production/group_vars/all/vault.yml` |
| Probar idempotencia | correr todo dos veces; la segunda = `changed=0` |

Tags disponibles: `base, bootstrap, ssh, ssh-lockdown, users, network, tailscale,
dns, ddns, security, firewall, fail2ban, apparmor, hardening, cis, updates, audit,
docker, services, auth, monitoring, backups, panol, iot, classroom,
shared-services, aula-iot, labctl, publish`.

---

## 9. Copias de seguridad

Las copias están **postergadas** hasta que haya un disco dedicado montado. El rol
`backups` **se niega a correr** si `/mnt/backup` no es un filesystem montado
propio (`borg_require_mounted: true`): así no se escriben "copias" en el mismo
disco del sistema sin una copia real fuera de él.

> ⚠️ Hoy (octubre 2026) **no hay copias de seguridad**. Es lo más urgente de la
> hoja de ruta (capítulo 15 del manual).

Para activarlas:

1. Conectar el disco externo / NAS y montarlo en `/mnt/backup` (con una entrada en
   `/etc/fstab` para que sobreviva a los reinicios).
2. Confirmar: `mountpoint -q /mnt/backup && echo OK`.
3. Correr solo el rol de copias:
   ```bash
   ~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production --tags backups -K
   ```
4. `borgmatic` inicializa el repositorio e instala un timer de systemd.
   **Guardá `vault_borg_passphrase` en un gestor de contraseñas: perderla es
   perder las copias.**

---

## 10. Verificación y chequeos de salud

```bash
# Chequeos de postura de Ansible + pruebas testinfra
make verify
make test

# Revisiones a mano
sudo ufw status verbose                    # activo, deny entrante, tu red permitida
sudo grep -E '^AllowUsers|^Match' /etc/ssh/sshd_config
docker ps --format '{{.Names}}'            # caddy, prometheus, grafana, mqtt-aula, grafana-aula…
sudo fail2ban-client status sshd
sudo aa-status | tail -1                   # perfiles en modo enforce
tailscale status
sudo tailscale funnel status               # :8443 (pañol) y :10000 (broker del aula)
```

testinfra también verifica que **el atajo Docker/UFW esté cerrado** (bloque de
`ufw-docker` presente, puertos internos solo en loopback, ningún contenedor en
`0.0.0.0` salvo Caddy).

---

## 11. Diagnóstico de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ssh usuario@ip-lan` da **timeout** | UFW bloquea tu red (`lan_cidr` mal o viejo) | Corregir `lan_cidr`, `--tags firewall -K` |
| `Permission denied (publickey)` pero aparece el cartel | el usuario no está en el `AllowUsers` vivo | `--tags ssh -K` |
| `sudo: a password is required` en medio de la corrida | se corrió como `homelab` sin `-K` | agregar `-K` |
| `Command 'ansible-playbook' not found` | el venv no está en el `$PATH` | usar `~/homelab/.venv/bin/ansible-playbook` |
| `Ansible could not initialize the preferred locale` | SSH pasa el idioma de tu compu y el server no lo tiene | anteponer `env LC_ALL=C.UTF-8 LANG=C.UTF-8` |
| El play corta en "Safety gate … usable admin key" | queda un `REPLACE_ME` en una llave | poner la llave real en group_vars |
| El play corta en "backup target must be … mounted" | `/mnt/backup` no está montado | montar el disco, o `--skip-tags backups` |
| `Error … vault password file … not found` | falta `~/.vault_pass` | `echo <clave> > ~/.vault_pass && chmod 600 ~/.vault_pass` |
| El vault no se descifra | `~/.vault_pass` equivocada, o vault en la ruta vieja | corregir la clave; vault en la ruta por entorno |
| El servidor no aparece en Tailscale (`rx 0`) | se cayó la red del servidor (WiFi USB) | consola física: `nmcli device status`; ver `make uplink` |

---

## 12. Recuperación de emergencia

Si en algún momento no podés entrar por SSH de ninguna forma:

1. **Consola.** Sentate frente a la máquina. El login de escritorio de `homelab`
   siempre funciona: el endurecimiento de OpenSSH nunca lo afecta.
2. **Tailscale SSH.** Desde cualquier equipo del tailnet: `ssh ansible@homelab-01`
   (o la IP `100.x`). No lo afecta el endurecimiento de `sshd` mientras
   `tailscaled` esté arriba.
3. Desde cualquiera de las dos, deshacer un cambio de SSH malo:
   ```bash
   sudo cp /etc/ssh/sshd_config /root/sshd_config.bak
   sudo sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
   sudo sshd -t && sudo systemctl restart ssh
   ```
   o volver a correr el playbook con `-e ssh_lockdown_enabled=false` para sacar el
   endurecimiento prolijamente, y aplicar de nuevo cuando esté arreglado.
4. Si el problema es Tailscale: `sudo tailscale up --ssh --accept-routes`.
5. Si el problema es la **red** del servidor (cambió de WiFi o se colgó el
   adaptador): desde la consola, `nmcli device status`, y para sumar una red sin
   perder la anterior, `sudo ~/homelab/scripts/agregar-wifi.sh "Nombre-de-la-red"`.

6. **Si el servidor se congela**, el watchdog de hardware lo reinicia solo en
   30 s; si pierde la red, el guardián la repara por escalones (ver
   [vigia-red.md](vigia-red.md)). Si igual no vuelve, el informe de
   `scripts/diagnosticar-caida.sh` (en tu notebook) dice por qué.

> El objetivo del diseño es que **ningún cambio solo te deje afuera**: consola,
> Tailscale SSH y OpenSSH con llave son tres puertas independientes.

---

## 13. Cómo se llega a los servicios

Todo está detrás del proxy Caddy en `https://*.<dominio>`, con una página de
inicio (**Homepage**) en la raíz que enlaza a todo:

| Servicio | URL | Quién entra (Authelia) |
|---|---|---|
| Página de inicio (Homepage) | `https://<dominio>` | operadores y alumnos |
| Grafana de operación | `https://grafana.<dominio>` | **solo operadores** (tiene la auditoría del pañol) |
| Grafana del aula | `https://grafana-aula.<dominio>` | operadores y alumnos (cada uno, su equipo) |
| Tablero del pañol | `https://panol.<dominio>` | solo operadores |
| Prometheus | `https://prometheus.<dominio>` | solo operadores |
| cAdvisor | `https://cadvisor.<dominio>` | solo operadores |
| App de ejemplo | `https://demo.<dominio>` | pública (sin login) |

### Por el tailnet (como se usa hoy)

El rol `dns` levanta un **dnsmasq** en la IP de Tailscale del servidor que
responde **todos** los `*.<dominio>` con esa IP, y Tailscale lo usa como DNS para
el dominio (**Split DNS**). Resultado: desde cualquier equipo del tailnet, los
nombres llevan a Caddy por Tailscale, con HTTPS válido (el certificado se emite
por DNS-01, así que es confiable en cualquier red) y **sin redirección de
puertos**.

Cuando la notebook y el servidor están en la misma red, Tailscale arma una
**conexión directa por la LAN** (sin relé), así que en casa anda a velocidad de LAN
y sigue funcionando igual afuera. Lo único que hace falta es tener Tailscale
prendido.

> Si un equipo no toma el Split DNS (pasa en algunos teléfonos), se puede apuntar
> a mano en `/etc/hosts`:
> ```bash
> echo "<IP-tailnet-del-server>  <dominio> grafana.<dominio> grafana-aula.<dominio>" \
>   | sudo tee -a /etc/hosts
> ```

### Desde internet (hoy no está configurado)

Habría que redirigir **TCP 443** (y 80) en el router a la IP LAN del servidor;
DuckDNS mantiene el registro público al día. Todo lo protegido sigue pidiendo login
(Authelia), así que Prometheus y cAdvisor quedan solo para operadores aunque se
expongan.

> Un filtro por IP en Caddy (`remote_ip`) **no** sirve acá: Docker reemplaza la IP
> del cliente por la del gateway del bridge, y Caddy ve `172.x` en vez del origen
> real (comprobado en el log de acceso de Caddy: `"client_ip":"172.18.0.1"`). Un
> filtro por IP rechazaría a todos, incluidos los clientes legítimos del tailnet.
> Por eso la protección es **por login**, no por IP.

### Placas y nodos (Tailscale Funnel)

Los dispositivos no usan Caddy: entran por **Funnel** (`sudo tailscale funnel
status`):

- `:10000` → broker MQTT del aula (`mqtt-aula`), TLS + usuario por equipo + ACL.
- `:8443` → API del pañol, con token.

### Prender / apagar

La página de inicio se controla con `dashboard_enabled` (por defecto `true`) en el
rol `monitoring`. Para redesplegar después de un cambio:

```bash
ansible-playbook site.yml -i inventories/production --tags "services,docker" -K
```
