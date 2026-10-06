# Runbook (procedimientos de operación)

Procedimientos para el día a día del servidor. El recorrido completo de una
instalación, con todas las trampas, está en
[deployment-guide.md](deployment-guide.md).

> **Dónde se corre cada cosa:** salvo que se diga otra cosa, los comandos `make`
> y `ansible-playbook` se corren **en el servidor**, como usuario `homelab`, desde
> `~/homelab` (o `~/homelab/ansible` para `ansible-playbook`), y llevan `-K`
> porque `homelab` usa `sudo` con contraseña.

## Primera instalación

1. `make deps` — instala las colecciones y las herramientas de pruebas.
2. Editar `ansible/inventories/production/group_vars/all/main.yml`: llaves SSH,
   `lan_cidr` (la red **real** de la casa: `hostname -I`), `caddy_base_domain`,
   `caddy_acme_email`, `duckdns_domains`. Los ajustes propios de cada rol
   (`borg_repo`, retención, timers…) están en el `defaults/main.yml` de cada rol;
   se pisan acá solo si tienen que ser distintos. Con `ENV=staging` cualquier
   `make` actúa sobre el inventario de staging.
3. `make vault-create` y después `make vault-edit` para cargar los tokens reales.
4. Guardar la clave del vault en `~/.vault_pass` (está en `.gitignore`, `chmod 600`).
5. `make dry-run` → revisar las diferencias.
6. **SSH — fase 1 (segura, sin riesgo de quedarse afuera):** crear la cuenta e
   instalar las llaves **sin** aplicar todavía el `sshd_config` restrictivo:
   ```
   ansible-playbook site.yml --tags ssh --skip-tags ssh-lockdown
   ```
   Confirmar desde **otra** terminal que se entra con la llave:
   `ssh <admin_user>@<host>`.
7. `make apply` — todo. Ahora sí se aplica el **cierre de SSH**
   (`PasswordAuthentication no`, `AllowUsers`, reinicio de sshd). Una guarda corta
   el play si `admin_ssh_authorized_keys` está vacío o todavía dice `REPLACE_ME`,
   para que no te quedes afuera por olvidarte la llave. Con
   `ssh_lockdown_enabled: false` se posterga el cierre.
8. `sudo tailscale up --ssh --accept-routes` (autenticación por navegador, una vez).
9. Montar el disco de copias en el directorio padre de `borg_repo` y correr
   `make backups`.
10. `make verify && make test`.

### Cuentas de usuario

`extra_users` (en los group_vars del entorno) define las cuentas de personas:

- **`homelab` / operador:** tu cuenta. Está en el grupo `sudo` (pide contraseña)
  y puede entrar por SSH. Ponele una contraseña una vez para que `sudo` funcione:
  `sudo passwd homelab`. Cargá su llave real antes de `make apply` (la guarda del
  cierre de SSH no corre mientras un usuario con SSH tenga `REPLACE_ME`).
- **`familia`:** cuenta de uso diario, sin `sudo` y con `ssh: false`: entra al
  escritorio pero nunca por SSH (no queda en `AllowUsers`).
- **`ansible`** (`admin_user`): solo para la automatización: `sudo` sin
  contraseña, SSH con llave.

## Aula: alumnos, equipos y servicios

Todo se edita en `ansible/inventories/production/group_vars/all/classroom.yml`
y se aplica con `--tags classroom`. El detalle está en
[operator-guide.md](operator-guide.md) y [aula-iot.md](aula-iot.md).

**Alta de un alumno** (tres lugares; si falta uno queda a medias):

1. `classroom_teams[].members` — sumar el usuario al equipo.
2. `sso_users` — `{ username, displayname, groups: [students] }` (login web).
3. `vault_sso_passwords[<usuario>]` en el **vault del servidor** — su contraseña
   (la misma para la web y para SSH). Sin esto el usuario se crea **sin
   contraseña** y no puede entrar.

Después, en el servidor:

```
cd ~/homelab && git pull
cd ~/homelab/ansible
~/homelab/.venv/bin/ansible-playbook site.yml --tags classroom -K
```

Esto crea el usuario Linux, lo suma a su equipo, le arma su usuario en el
**Grafana del aula** dentro del equipo correcto y, si el equipo es nuevo, crea su
folder, su datasource y su tablero inicial.

**Sumar a un alumno a Tailscale:** generar una *auth key* con **Pre-approved**
(<https://login.tailscale.com/admin/settings/keys>) y que el alumno corra
`tailscale logout` y después `tailscale up --auth-key=…`. El `logout` evita que
quede en una red propia (pasa cuando entró antes con su Google).

**Ver la clave MQTT de un equipo** (para su placa):

```
sudo grep MQTT_ /srv/classroom/equipo-NN/.shared-services.env
```

## Agregar un proyecto educativo propio

1. Copiar `compose/apps/` a `compose/apps-<nombre>/` y renombrar el servicio.
2. Agregar un bloque en `compose/proxy/Caddyfile`:
   ```
   <nombre>.{$CADDY_BASE_DOMAIN} {
       reverse_proxy <servicio>:<puerto>
   }
   ```
3. Conectar el servicio a la red externa `edge` (sin puertos publicados).
4. `make monitoring` (sincroniza y reinicia el proxy y los stacks).
5. Queda en `https://<nombre>.<tu-dominio>`.

## Cambiar (rotar) un secreto

```bash
make vault-edit          # cambiar el valor
make apply               # vuelve a armar los .env y reinicia lo afectado
```

Las claves generadas en el host (`/etc/classroom/secrets/*.mqttpass`, etc.) se
rotan borrando el archivo y aplicando `--tags classroom`: se genera una nueva y se
reparte sola. **Ojo:** las placas del equipo dejan de conectarse hasta que les
cargues la clave nueva.

## Replicar todo en otra máquina

```bash
make new-site NAME=<sitio>   # clona la plantilla de inventario; completar los REPLACE_
```

Flujo completo (un inventario = un sitio, varios servidores por sitio con
host_vars) en [replicar-y-escalar.md](replicar-y-escalar.md).

## Pañol IoT (control de acceso)

El rol `panol` maneja el broker, la base de auditoría y Node-RED; el "cerebro"
(API, puente, planificador) se despliega desde el repo `panol-iot`. Todo
(credenciales, rotación, firewall, el reset de prueba, el recorrido de punta a
punta) está en [panol-iot.md](panol-iot.md). Lo rápido:

```bash
make panol                                      # redesplegar el plano
sudo cat /etc/panol/secrets/nodos.txt           # credenciales de los nodos para grabar el firmware
systemctl status panol-reset-prueba.timer       # reset del modo prueba (temporal)
```

## Copias de seguridad

> ⚠️ Hoy **no están activas** (falta el disco en `/mnt/backup`).

- Correr una ya: `sudo borgmatic --verbosity 1`
- Listar copias: `sudo borgmatic list`
- Restaurar un archivo:
  ```bash
  sudo borgmatic extract --archive latest --path etc/ssh/sshd_config
  ```
- Chequear integridad: `sudo borgmatic check`
- Estado del timer: `systemctl status borgmatic.timer`

## Revisión de auditoría

- Puntaje de Lynis: `journalctl -t lynis` o `/var/log/lynis/lynis-report.dat`
  (`grep hardening_index`).
- Cambios detectados por AIDE: `journalctl -t aide`; investigar cualquier
  "INTEGRITY CHANGES".
- Después de un cambio intencional, renovar la línea de base de AIDE:
  ```bash
  sudo aideinit -y -f && sudo systemctl restart aide-check.timer
  ```

## Red y conectividad

- `make como-conectar` (en **tu** compu) — prueba todos los caminos al servidor y
  te dice cuál anda y por qué los otros no. Con `USUARIO=jessi EQUIPO=01` arma el
  comando `ssh` completo, con el túnel a Node-RED (y a la web) de ese equipo.
- `make uplink` — mide la calidad real de cada conexión del servidor (WiFi,
  cable) y muestra cuál conviene. No cambia nada.
- **Robustez ante caídas** (rol `vigia_red`): watchdog de hardware, guardián de
  red cada minuto, latido y resumen al arrancar. Qué hizo:
  `sudo tail /var/log/homelab/vigia-red.log`; por qué se reinició la última vez:
  `sudo sh -c 'cat $(ls -1t /var/log/homelab/arranques/*.txt | head -1)'`. Detalle
  en [vigia-red.md](vigia-red.md).
- **Si el servidor se cae y no estás cerca:** `scripts/diagnosticar-caida.sh`
  corre en **tu** compu (por cron, cada 5 minutos). Cuando el servidor vuelve, lee
  sus registros y deja un informe con la causa más probable en
  `~/homelab-reportes/caida-<fecha>.md`, con una notificación en el escritorio.
  Instalación: `crontab -e` y agregar
  `*/5 * * * * /home/zen/homelab/scripts/diagnosticar-caida.sh --cron`.
- `sudo ufw status verbose` — reglas actuales del firewall.
- ¿Te quedaste afuera del SSH? Usá la consola física o Tailscale SSH
  (`ssh ansible@homelab-01`, que no pasa por el sshd endurecido).
- **El servidor cambió de red** (pasa: ya fueron tres): actualizar `lan_cidr` y
  aplicar `--tags firewall,ssh -K` (lo usan el firewall y el `Match Address` de
  `sshd`). Mientras tanto se entra por Tailscale.
- **Sumar una red WiFi sin perder la anterior:**
  `sudo ~/homelab/scripts/agregar-wifi.sh "Nombre-de-la-red"` (pide la clave;
  si la nueva no levanta, vuelve a la anterior).
- Un puerto de un contenedor quedó público sin querer → confirmar que
  `ufw-docker` está instalado y que el servicio publica solo en `127.0.0.1`.

## Actualizaciones

- Los parches de seguridad del host se aplican solos (`unattended-upgrades`) y,
  si hace falta, el servidor se reinicia a la hora `autoupdate_reboot_time`
  (04:30). Revisar con `journalctl -u unattended-upgrades`.
- Imágenes de contenedores:
  `cd /opt/homelab/stacks/<stack> && docker compose pull && docker compose up -d`.
  Es manual **a propósito**: una imagen nueva rota nunca tiene que tumbar una
  clase en vivo.

## Recuperación ante un desastre (esquema)

1. Reinstalar Ubuntu LTS, crear el usuario con `sudo` y cargar tu llave SSH.
2. Clonar el repo y recuperar `.vault_pass` y el vault desde tu gestor de
   contraseñas.
3. `make apply`.
4. Montar el disco de copias y restaurar con `borgmatic extract` los volúmenes de
   Docker y `/opt/homelab`.
5. `make monitoring` para levantar los servicios.
