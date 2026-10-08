# Runbook para el agente de Alan: montar su espacio en `vm-alan`

> **Para quién es este documento:** para el asistente de IA (Claude u otro agente)
> que trabaja con **Alan** (equipo-02) en su computadora. Está escrito para que el
> agente lo lea y lo ejecute paso a paso. Alan también puede seguirlo a mano.
>
> **Dueño del servidor:** Lucas (operador de homelab-01). Lo que dice
> "**pedírselo a Lucas**" no lo puede hacer ni Alan ni su agente.

## 0. Contexto (leer antes de ejecutar nada)

- **homelab-01** es el servidor del aula. Es compartido y en producción: corre los
  servicios de todos los equipos. Alan tiene ahí un usuario común (`alan`, **sin**
  sudo), que entra con **contraseña** y solo desde el tailnet (Tailscale) o la LAN.
- **vm-alan** es una máquina virtual (Ubuntu 24.04) que corre adentro de
  homelab-01 y es **de Alan**: ahí es root (`sudo` sin contraseña). 2 CPU, 2 GiB
  de RAM, 20 GiB de disco, IP `10.90.0.10`. Entra **solo con llave SSH**.
- A la VM se llega **saltando** por homelab-01 (`ProxyJump`): primero se entra a
  homelab-01 con la contraseña del aula y desde ahí SSH sigue hasta la VM.
- **La VM solo sale a internet.** El firewall le bloquea la LAN de la casa, las
  redes de Docker de homelab-01, el tailnet y el propio servidor. Es a propósito.
- El proyecto de Alan y Gabi (el "higroterm") es una ESP32 que publica a MQTT en
  el broker del aula **`mqtt-aula`**, con el usuario del equipo `equipo_02` y los
  topics `equipo-02/...`. Desde afuera (la ESP32 o la VM) el broker se alcanza en
  `homelab-01.tail4eda13.ts.net:10000` con **TLS**.

Detalle del diseño (para el operador): `docs/vms-alumnos.md` en este repo.

## 1. Reglas para el agente (obligatorias)

1. **En homelab-01, solo leer.** Lo único que se hace ahí es saltar a la VM y
   copiar el archivo de credenciales del paso 6. Nada de instalar, editar, correr
   contenedores ni intentar `sudo`. Es un servidor compartido.
2. **Todo lo demás pasa dentro de `vm-alan`.** Ahí sí: instalar, configurar,
   romper y volver a armar.
3. **No intentes saltar el aislamiento.** Si desde la VM no se llega a una IP
   privada (`10.x`, `172.16–31.x`, `192.168.x`, `100.64–127.x`), es por diseño.
   No es un error que haya que arreglar.
4. **Las contraseñas no se escriben ni se muestran.** La contraseña del aula la
   tipea Alan. La de MQTT se copia de archivo a archivo, sin imprimirla en la
   terminal ni en el chat, y nunca va a git (`.env` en `.gitignore`).
5. **No publiques nada a internet** (ngrok, cloudflared, Tailscale Funnel, abrir
   puertos) sin que Lucas lo apruebe. Para ver una web de la VM se usa un túnel
   SSH (paso 8).
6. **En MQTT solo `equipo-02/...`.** El broker igual rechaza otros topics.
7. **Si algo necesita al operador** (la VM no existe, no arranca, cambiar la
   llave, más recursos, reinstalarla), **frená y decile a Alan que se lo pida a
   Lucas.** No hay otra vía.

## 2. Prerrequisitos (verificar con Alan)

| # | Qué | Cómo se verifica | Si falta |
|---|-----|------------------|----------|
| a | Tailscale instalado y conectado en la PC de Alan | `tailscale status` lista `homelab-01` | Alan sigue la guía del aula (`docs/student-guide.md`) o se lo pide a Lucas |
| b | Usuario `alan` del aula con contraseña | Alan puede hacer `ssh alan@homelab-01.tail4eda13.ts.net` y entrar | pedírselo a Lucas |
| c | Llave SSH de Alan cargada en la VM | se prueba en el paso 5 | pasos 3 y 4 |

Detectá el sistema operativo de Alan. Linux, macOS y **WSL** sirven para todo
este runbook. En **Windows sin WSL** mirá la nota del paso 5.

## 3. Crear la llave SSH (en la PC de Alan)

Si ya existe `~/.ssh/id_ed25519.pub`, usala y saltá al paso 4. Si no:

```bash
ssh-keygen -t ed25519 -C "alan@vm-alan" -f ~/.ssh/id_ed25519
```

Que Alan elija si le pone frase (passphrase). Si le pone, la tipea él.
**Nunca** muestres ni copies `~/.ssh/id_ed25519`, que es el archivo privado.

## 4. Mandar la llave pública a Lucas (lo hace Alan)

```bash
cat ~/.ssh/id_ed25519.pub
```

Alan le manda **esa línea** a Lucas (por WhatsApp está bien, es pública). Lucas
la carga y crea la VM. **Esperá a que Lucas confirme** "vm-alan creada" antes de
seguir.

## 5. Configurar SSH (en la PC de Alan)

Agregá esto a `~/.ssh/config` (crealo con permisos `600` si no existe). No
dupliques los bloques si ya están:

```
Host homelab-01
    HostName homelab-01.tail4eda13.ts.net
    User alan
    ControlMaster auto
    ControlPath ~/.ssh/cm-%r@%h-%p
    ControlPersist 4h

Host vm-alan
    HostName 10.90.0.10
    User alan
    IdentityFile ~/.ssh/id_ed25519
    ProxyJump homelab-01
```

**Por qué `ControlMaster`:** homelab-01 pide contraseña y el agente no puede
tipearla. Alan abre **una** conexión maestra, que queda viva 4 horas, y todos los
`ssh vm-alan` del agente la reusan sin volver a preguntar.

Alan, en **su propia terminal** (no la del agente), corre esto. Si su máquina
entró al tailnet con la auth key de Lucas, **Tailscale SSH lo deja pasar sin
contraseña**. Si la pide, la tipea Alan:

```bash
ssh -fN homelab-01
```

Después el agente verifica:

```bash
ssh -O check homelab-01        # "Master running"
ssh vm-alan 'hostname; whoami; sudo -n true && echo SUDO_OK'
```

Tiene que responder `vm-alan`, `alan`, `SUDO_OK`. Si dice `Permission denied
(publickey,...)`, o la llave no está cargada (volver al paso 4) o la cuenta de la
VM quedó bloqueada: hay que pedírselo a Lucas. Lo que diga el comentario de la
llave (`alan@...`) no importa. Si dice `tailnet policy does not permit`, la
máquina de Alan no está en el tailnet de Lucas: pedirle una auth key. Si da *timeout* hacia
`10.90.0.10`, la VM no está arriba: hay que pedírselo a Lucas.

Cuando la maestra vence (4 h), Alan repite `ssh -fN homelab-01`.

> **Windows sin WSL:** el OpenSSH de Windows no soporta `ControlMaster`. Hay dos
> opciones. (1) Instalar WSL y seguir desde ahí. (2) Que Alan entre a mano con
> `ssh -J alan@homelab-01.tail4eda13.ts.net alan@10.90.0.10`, instale el agente
> **dentro de la VM** y siga este runbook desde ahí (los pasos 6 a 8 corren
> igual; "en la VM" pasa a ser local).

Desde acá, "**en la VM**" significa `ssh vm-alan '<comando>'`, o una sesión
abierta con `ssh vm-alan`.

## 6. Preparar la VM

### 6.1 DNS público

**Por qué:** el DNS que la VM recibe por defecto pasa por homelab-01, que
resuelve `*.ts.net` a la IP del tailnet (`100.x`), y esa red está bloqueada para
la VM. Con un DNS público, `homelab-01.tail4eda13.ts.net` resuelve a la dirección
pública de Funnel, que sí se alcanza.

En la VM:

```bash
sudo mkdir -p /etc/systemd/resolved.conf.d
printf '[Resolve]\nDNS=1.1.1.1 9.9.9.9\nDomains=~.\n' | sudo tee /etc/systemd/resolved.conf.d/publico.conf
sudo systemctl restart systemd-resolved
getent hosts homelab-01.tail4eda13.ts.net    # NO debe empezar con 100.
```

### 6.2 Paquetes base y Docker

En la VM:

```bash
sudo apt-get update && sudo apt-get -y upgrade
sudo apt-get install -y git curl ca-certificates mosquitto-clients docker.io docker-compose-v2
sudo usermod -aG docker alan
```

Para que tome el grupo `docker`, cerrá la conexión SSH y volvé a entrar. Después
verificá con `docker run --rm hello-world`.

## 7. Credenciales MQTT del equipo

homelab-01 ya tiene las credenciales de equipo-02 en
`/srv/classroom/equipo-02/.shared-services.env`, legible por el grupo del equipo.
Se copian **sin mostrarlas** a la VM, al archivo `~/higroterm/.env`.

Desde la PC de Alan:

```bash
ssh vm-alan 'mkdir -p ~/higroterm && umask 077 && touch ~/higroterm/.env'
ssh homelab-01 'grep -E "^MQTT_(USER|PASSWORD|TOPIC_PREFIX|DEVICE_HOST|DEVICE_PORT)=" /srv/classroom/equipo-02/.shared-services.env' \
  | ssh vm-alan 'cat > ~/higroterm/.env && chmod 600 ~/higroterm/.env'
ssh vm-alan 'cut -d= -f1 ~/higroterm/.env'   # muestra SOLO los nombres
```

Tienen que aparecer `MQTT_USER`, `MQTT_PASSWORD`, `MQTT_TOPIC_PREFIX`,
`MQTT_DEVICE_HOST` y `MQTT_DEVICE_PORT`. Si el archivo no existe o da *Permission
denied*, Alan no está en el grupo del equipo: hay que pedírselo a Lucas.

**Prueba**, en la VM, con la ESP32 prendida y publicando:

```bash
cd ~/higroterm && set -a && . ./.env && set +a
mosquitto_sub -h "$MQTT_DEVICE_HOST" -p "$MQTT_DEVICE_PORT" \
  --capath /etc/ssl/certs -u "$MQTT_USER" -P "$MQTT_PASSWORD" \
  -t "${MQTT_TOPIC_PREFIX}#" -v -C 5 -W 60
```

Tienen que llegar mensajes `equipo-02/...`. Si llega `not authorised`, es un
error de credenciales. Si da *timeout*, revisá 6.1 (DNS) o confirmá que la ESP32
esté publicando.

## 8. El espacio de Alan

Desde acá **el proyecto es de Alan**: preguntale qué quiere montar. Convenciones
para que todo siga siendo fácil de mantener:

- Todo el proyecto en `~/higroterm`, versionado con git, y `.env` en
  `.gitignore` **antes** del primer commit:
  ```bash
  cd ~/higroterm && git init && printf '.env\n' > .gitignore
  ```
- Servicios con **Docker Compose** (`~/higroterm/compose.yaml`), leyendo
  `env_file: .env`. Para conectarse al broker, usar
  `MQTT_DEVICE_HOST`/`MQTT_DEVICE_PORT` con TLS (no `mqtt-aula:1883`, que solo
  existe dentro de homelab-01).
- Publicar los puertos en **`127.0.0.1`** (`"127.0.0.1:1880:1880"`), no en
  `0.0.0.0`.
- Para abrirlos desde la PC de Alan, usar un túnel. Por ejemplo, un Node-RED en
  el puerto 1880:
  ```bash
  ssh -N -L 1880:localhost:1880 vm-alan
  ```
  y después abrir `http://localhost:1880` en el navegador.
- Cuidar los recursos (2 CPU / 2 GiB / 20 GiB): `docker system df` y
  `docker image prune` de vez en cuando.
- Respaldar empujando el repo a GitHub. **La VM no tiene backup**: si se rompe,
  Lucas la rehace vacía.

Ideas que encajan con el higroterm: Node-RED con un tablero propio, una base de
datos de series temporales (InfluxDB o VictoriaMetrics) que guarde
`equipo-02/#`, o una web propia que muestre la humedad del suelo.

## 9. Checklist final (para reportarle a Alan)

- [ ] `ssh vm-alan` entra con llave, y `sudo` funciona
- [ ] `homelab-01.tail4eda13.ts.net` resuelve a una IP pública desde la VM
- [ ] Docker funciona sin `sudo`
- [ ] `~/higroterm/.env` existe, con permisos `600`, y está fuera de git
- [ ] `mosquitto_sub` recibe mensajes de `equipo-02/...`
- [ ] Nada publicado a internet y nada tocado en homelab-01
