# Capa de visualización IoT del aula (`aula-iot`)

> **Estado:** en marcha desde el 2026-10-05 (`aula_iot_enabled: true`). Se
> desplegó con `--tags docker,monitoring,auth,shared-services,aula-iot` y se
> verificó de punta a punta: los datos de equipo-03 y equipo-04 llegan a
> VictoriaMetrics.

Lo que las placas de los equipos publican en `mqtt-aula` se guarda 15 días y se
ve en un **Grafana del aula** propio, con un folder por equipo que solo ese equipo
ve y edita, y un dashboard general del operador.

Manuales para alumnos: [12 — Conectar a Grafana](handbook/12-conectar-a-grafana.md)
y [13 — Grafana paso a paso](handbook/13-usar-grafana.md).

## Arquitectura

```
 ESP32 ──TLS──► Funnel :10000 ──► mqtt-aula ──► aula-telegraf ──► aula-victoriametrics (15 d)
                                     │                                   ▲
                                     └──► aula-mosquitto-exporter ───────┘ (scrape)
                                                                          │
 navegador ──tailnet──► Caddy ──Authelia──► grafana-aula ◄────────────────┘
                          └── red grafana-aula-proxy (172.31.250.0/24)
```

| Pieza | Qué hace | Dónde |
|---|---|---|
| `aula-telegraf` | se suscribe a `<equipo>/#` de cada equipo (usuario `aula-telegraf`, solo lectura) y convierte cada mensaje en `mqtt_valor{equipo,dispositivo,magnitud}` | `compose/aula-iot/telegraf/mqtt.star` |
| `aula-victoriametrics` | guarda las series 15 días; también scrapea el exporter | `compose/aula-iot/compose.yml` |
| `aula-mosquitto-exporter` | estadísticas del broker (`$SYS`, usuario `aula-exporter`) | idem |
| `grafana-aula` | Grafana del aula; usuario = el de Authelia | idem |

### Decisiones que no se ven en el código

- **Grafana aparte del de operación.** El Grafana gratuito no puede impedir que
  quien edita un dashboard consulte cualquier datasource, y el de operación tiene
  la base de auditoría del pañol. Con dos instancias el aislamiento es real. El de
  operación (`grafana.`) quedó **solo para operadores** en Authelia.
- **Auth proxy con whitelist de red.** Grafana toma el usuario del header
  `Remote-User` que pone Caddy después de Authelia, pero **solo** si el pedido
  viene de `172.31.250.0/24` (red `grafana-aula-proxy`, solo Caddy). En `edge`
  también están `panol-api` y `panol-nodered`: si se confiara en `edge`, cualquiera
  de esos podría hacerse pasar por el operador.
- **Datasource por equipo con `extra_label`.** VictoriaMetrics filtra cada
  consulta por `equipo=<equipo>`, así los alumnos escriben `mqtt_valor` sin filtro.
  **Límite honesto:** en Grafana OSS no hay permisos por datasource, así que un
  alumno que edita puede elegir el datasource de otro equipo y *leer* sus valores.
  Los **dashboards** sí están aislados (folders con permiso solo para el equipo).
  Los datos de sensores del aula no son sensibles; si llegaran a serlo, hace falta
  una organización de Grafana por equipo.
- **Dashboard inicial por API, no por provisioning.** Lo crea Ansible una sola vez;
  después es del equipo. Provisionado sería de solo lectura o se pisaría.
- **Topes de cardinalidad** en VictoriaMetrics (`-storage.maxDailySeries=20000`,
  etc.) y en `mqtt.star` (nombres de 40 caracteres, 20 campos por JSON): una placa
  en bucle inventando topics no puede llenar el disco.

## Operación

**Aplicar** (en el server, como `homelab`):

```
cd ~/homelab && git pull
cd ~/homelab/ansible
~/homelab/.venv/bin/ansible-playbook site.yml --tags classroom -K
```

`--tags classroom` incluye `shared-services` (el broker y sus usuarios) y
`aula-iot`, en ese orden. Solo esta capa: `--tags aula-iot`.

**Primer despliegue (o un servidor nuevo):** `classroom` no alcanza, porque la
red `grafana-aula-proxy`, el sitio de Caddy y la regla de Authelia viven en otros
roles:

```
~/homelab/.venv/bin/ansible-playbook site.yml --tags docker,monitoring,auth,classroom -K
```

Lo que pasó la primera vez (2026-10-05), para no asustarse:

- **"Bring up the proxy stack" tardó ~10 min.** Caddy es una imagen propia
  (`xcaddy` con los plugins de DuckDNS y rate-limit) y se recompila cuando cambia
  su stack. No está colgado: mientras compila, el Caddy viejo sigue atendiendo.
- **Para que los alumnos entren** hace falta el Split DNS de Tailscale
  (`lucasland.duckdns.org` → `100.110.123.76`, ver `deployment-guide.md` §13).
  Sin eso el nombre va a la IP pública de la casa y el navegador dice "no se
  puede conectar".

**Alta de un equipo o alumno:** se edita el roster
(`ansible/inventories/production/group_vars/all/classroom.yml`) como siempre y se
aplica. El rol crea el usuario de Grafana, el equipo, el folder con permisos, el
datasource y el dashboard inicial. Un alumno que se cambia de equipo sale del
equipo viejo de Grafana (la membresía se sincroniza con el roster).

**Admin de Grafana:** es el usuario `operator` de Authelia. La clave de la API
(Ansible) está en `/etc/classroom/secrets/grafana-aula.adminpass`.

## Dashboard público para la muestra

1. En `grafana-aula`, abrí el dashboard → **Share** → **Share externally** →
   aceptá → copiá el link (`/public-dashboards/<token>`).
2. Ese link no pide login, pero **hoy solo se abre desde el tailnet**: el router
   no reenvía el 443. De los tres puertos que admite Funnel, dos están en uso
   (8443 API del pañol, 10000 MQTT); el 443 queda libre, pero publicarlo
   expondría Caddy entero, no solo el dashboard.
3. Para mostrarlo **en internet** falta una salida pública que solo deje pasar
   `/public-dashboards/`, `/public/` y `/api/public/` (y nada del resto de
   Grafana). Pendiente de decidir: ver "Mejoras" abajo.
4. Para cortar el acceso: **Share externally** → **Revoke**.

## Diagnóstico

```
# ¿Llegaron datos en el último día? (en el server). Ojo: sin el
# last_over_time, la consulta mira solo los últimos 5 min y con las placas
# apagadas da vacío aunque haya historia.
curl -s 'http://127.0.0.1:8428/api/v1/query?query=count(last_over_time(mqtt_valor[1d]))by(equipo)'

# ¿Qué está recibiendo Telegraf?
docker logs --tail 50 aula-telegraf

# ¿Grafana rechaza el header de usuario? (whitelist)
docker logs --tail 50 grafana-aula | grep -i proxy
```

| Síntoma | Causa |
|---|---|
| Un equipo no ve su folder | el alumno no está en `members` del roster, o no se corrió `--tags classroom` después del alta |
| Datos de un equipo no aparecen | el topic no empieza con el nombre del equipo, o el equipo no estaba en el roster cuando se renderizó `telegraf.conf` |
| Grafana responde 407/401 entrando por SSO | Caddy no está en la red `grafana-aula-proxy` (recrear el stack `proxy`) |
| `aula-telegraf` reiniciándose con `not Authorized` | el broker no tomó el `passwd` nuevo (montaje de archivo suelto). El rol reinicia `mqtt-aula` al cambiarlo; a mano: `docker restart mqtt-aula aula-telegraf` |
| "No se puede conectar" a `grafana-aula…` | falta el Split DNS en ese equipo (`getent hosts grafana-aula.<dominio>` debe dar `100.x`), o Tailscale apagado |
| Timeout a la web desde el tailnet, Caddy sano | falta la regla `ufw route` del rol `firewall` (log: `[UFW DOCKER BLOCK] … DPT=443`); `--tags firewall` |

## Mejoras pendientes

- Salida pública filtrada para los dashboards públicos (muestra).
- Alertas (p. ej. "la placa del equipo X no publica hace 15 min") con Grafana
  Alerting.
- Backups de `vm_data` y `grafana_data` cuando exista `/mnt/backup`.
