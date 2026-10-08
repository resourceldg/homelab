# VMs propias para alumnos

Algunos alumnos quieren **ser root**: instalar lo que quieran, romper y volver a
armar su propio servidor. En homelab-01 eso no se puede dar: quien es root en el
server ve las claves de todos los equipos, el vault y el firewall. La solución es
darle **una máquina virtual (VM) propia**: una computadora "de mentira" que corre
adentro de homelab-01, con su propio Ubuntu, donde el alumno sí es root.

Primer caso: **Alan** (equipo-02), `vm-alan`.

## Cómo funciona

- **KVM** es la parte del kernel de Linux que permite correr VMs aprovechando el
  procesador (homelab-01 lo tiene: `/dev/kvm`).
- **Incus** es el programa que crea y administra esas VMs (`incus list`,
  `incus start`, …). Lo instala el rol `vms_alumnos`.
- **cloud-init** configura la VM en su primer arranque: crea el usuario del alumno,
  le carga su llave SSH y le da `sudo`. Corre **una sola vez**.

Cada VM tiene **2 CPU, 2 GiB de RAM y 20 GiB de disco** (se cambia por VM en
`classroom.yml`) y una IP fija en una red privada: `10.90.0.0/24`.

```
 casa del alumno ──Tailscale──► homelab-01 ──puente incusbr0──► vm-alan (10.90.0.10)
                                 (salto SSH)                     └─► internet ✔
                                                                 └─► LAN / Docker / tailnet ✘
```

### Por qué la VM no ve nada más

El firewall de homelab-01 (UFW) deja que la VM pida IP (DHCP) y nombres (DNS) al
propio Incus, y **salga a internet**. Todo lo demás está negado: la LAN de la casa,
las redes de Docker (servicios del aula, pañol, Grafana), el tailnet y el propio
server. Así, aunque el alumno sea root adentro de su VM, no puede tocar nada de
afuera. Las reglas están en `ansible/roles/vms_alumnos/tasks/main.yml`, parte 2.

### Por qué se entra "saltando" por homelab-01

La VM no está en internet ni en el tailnet. El alumno ya puede entrar por SSH a
homelab-01 con su usuario del aula; SSH puede usar esa conexión como **trampolín**
(`-J`, "jump") para llegar a la VM. No hace falta abrir nada nuevo.

## Dar una VM a un alumno (operador)

1. **Pedirle su llave pública SSH** (ver la guía del alumno, paso 1). Es un texto
   de una línea que empieza con `ssh-ed25519`. Es *pública*: se puede mandar por
   WhatsApp sin problema.
2. **Agregarla** — en tu notebook, en el repo:
   `ansible/inventories/production/group_vars/all/classroom.yml`, lista
   `vms_alumnos`:
   ```yaml
   vms_alumnos:
     - name: vm-alan
       owner: alan
       ip: 10.90.0.10
       ssh_pubkeys:
         - ssh-ed25519 AAAA... alan@su-pc
   ```
   Para otro alumno: otra entrada con `name`, `owner` y una `ip` libre
   (`10.90.0.11`, `.12`, …). **Por qué la llave:** la VM no tiene contraseña; sin
   llave el rol no la crea (avisa y sigue).
3. **PR → merge → aplicar** — en homelab-01, como `homelab`:
   ```
   cd ~/homelab && git pull
   cd ~/homelab/ansible
   ~/homelab/.venv/bin/ansible-playbook site.yml --tags vms -K
   ```
   El tag es `vms` (no `classroom`) a propósito: instala paquetes y toca el
   firewall, así que se corre cuando uno quiere, no de rebote.
4. **Verificar** — en homelab-01: `sudo incus list` tiene que mostrar `vm-alan`
   `RUNNING` con IP `10.90.0.10`. La primera vez tarda 1–2 minutos (descarga la
   imagen de Ubuntu).

El alumno además necesita su **usuario del aula andando** (contraseña en el vault,
ver `docs/classroom-architecture.md`) y **Tailscale** si entra desde casa: el
salto pasa por su usuario de homelab-01.

### Tareas comunes (en homelab-01)

| Qué | Comando |
|-----|---------|
| Ver las VMs | `sudo incus list` |
| Consola de la VM (si el alumno se quedó afuera) | `sudo incus exec vm-alan -- bash` |
| Apagar / prender | `sudo incus stop vm-alan` / `sudo incus start vm-alan` |
| Rehacerla de cero | `sudo incus delete --force vm-alan` y volver a correr `--tags vms` |
| Cuánto usa | `sudo incus info vm-alan` |

**Ojo:** cambiar `ssh_pubkeys`, CPU o RAM en `classroom.yml` **no** modifica una
VM ya creada (cloud-init corre una vez). Para eso: rehacerla, o
`sudo incus config set vm-alan limits.memory=4GiB` y reiniciarla.

**Backups:** las VMs no entran en el backup del server. Es un espacio para
experimentar; lo que valga la pena, el alumno lo guarda en git.

## Guía del alumno

> Si el alumno trabaja con un asistente de IA (Claude, etc.), hay un runbook
> pensado para que el agente lo ejecute solo: `docs/agentes/vm-alan.md`.

### 1. Crear tu llave SSH (una sola vez, en TU computadora)

Una llave SSH son dos archivos: uno **privado** (no se comparte nunca) y uno
**público** (se lo das al profe). Abrí una terminal (en Windows: *PowerShell*) y
escribí:

```
ssh-keygen -t ed25519
```

Apretá Enter a todo. Después mostrá la pública:

```
cat ~/.ssh/id_ed25519.pub
```

En Windows:

```
type $env:USERPROFILE\.ssh\id_ed25519.pub
```

Copiá esa línea entera (empieza con `ssh-ed25519`) y mandásela al profe.

### 2. Entrar a tu VM

Con Tailscale conectado (si estás fuera de la escuela/casa del server):

```
ssh -J alan@homelab-01 alan@10.90.0.10
```

Primero te pide la **contraseña del aula** (la de homelab-01, el trampolín).
Después entra a la VM con tu llave, sin contraseña. Si `homelab-01` no se
encuentra, usá la IP de Tailscale:

```
ssh -J alan@100.110.123.76 alan@10.90.0.10
```

### 3. Adentro sos root

```
sudo apt update
sudo apt install docker.io
```

Podés instalar lo que quieras. La VM sale a internet, pero no ve el resto del
server ni la red de la casa. Si la rompés, el profe la rehace en un minuto, así
que guardá tu trabajo en git.

### Ver una web que corre en tu VM

Si levantás algo en la VM (por ejemplo, en el puerto 8080), traelo a tu
computadora con un túnel y abrí `http://localhost:8080`:

```
ssh -J alan@homelab-01 -L 8080:localhost:8080 alan@10.90.0.10
```
