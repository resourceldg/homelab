# 10. Casos prácticos

🎯 **Objetivo:** aprender a **diagnosticar y resolver** problemas reales, con
recorridos paso a paso. Es el capítulo "de taller".

🧩 **Prerequisitos:** todos los anteriores (se usan como referencia).

> 📝 **Capítulo en desarrollo.** Ya incluye tres casos reales de este proyecto;
> se sumarán más.

## Método general de diagnóstico
1. **¿Qué síntoma veo exactamente?** (mensaje de error, código HTTP, "se cuelga").
2. **¿Dónde?** (navegador, terminal, un servicio puntual).
3. **Reproducir** de forma mínima.
4. **Aislar la capa:** ¿es red, DNS, permisos, contenedor, config?
5. **Confirmar la causa** con un comando, no con una corazonada.
6. **Arreglar y demostrar** que quedó resuelto.

---

## Caso 1 — "Grafana se queda pensando" (DNS / `/etc/hosts`)

**Síntoma:** el navegador gira infinito al abrir un servicio.

**Diagnóstico:** el `/etc/hosts` apuntaba a la **IP de LAN** (`192.168.100.48`),
inalcanzable desde otra red; y el subdominio `auth.` resolvía a la **IP pública**
(sin port-forward). El navegador redirige al login y no puede resolverlo.

**Solución:** apuntar **todos** los subdominios (incluido `auth.`) a la **IP del
tailnet** en `/etc/hosts` (o, mejor, configurar Split DNS en Tailscale para no
tocar `/etc/hosts`).

**Lección:** cuando "se cuelga" (timeout, no "error"), sospechá de **red/DNS**
antes que de la app.

## Caso 2 — Un cambio de config no tiene efecto (el inode del bind mount)

**Síntoma:** editás el Caddyfile y aplicás, pero Caddy sigue con la config vieja.

**Diagnóstico:** Ansible reemplaza el archivo de forma atómica → **nuevo inode**.
El contenedor tenía montado el archivo por el **inode viejo**, así que un `caddy
reload` leía el viejo.

**Solución:** **reiniciar el contenedor** (re-resuelve el bind mount). Se corrigió
en el rol para que reinicie Caddy solo cuando su config cambia.

**Lección:** los bind mounts de **archivos** (no carpetas) pueden quedar pegados
al inode viejo; ante dudas, **reiniciá el contenedor**.

## Caso 3 — Node-RED en bucle de reinicio (`EACCES` en un bind mount)

**Síntoma:** después de `labctl up`, `labctl ps` muestra el contenedor de
Node-RED como `Restarting` una y otra vez (mientras Mosquitto queda `Up`).

**Diagnóstico:** mirar los logs del contenedor:

```bash
docker logs equipo-01-nodered-1 --tail 20
# Error: EACCES: permission denied, copyfile ... -> '/data/settings.js'
```

Node-RED corre **como el uid 1000** adentro del contenedor, pero la carpeta que
se le montó en `/data` (el bind mount `./data/nodered`) se sembró como **`root`**.
El uid 1000 no es dueño ni del grupo → no puede escribir → se cae al arrancar.

**Solución:** hacer la carpeta escribible por el uid del contenedor y reiniciar:

```bash
sudo chown -R 1000:1000 /srv/classroom/equipo-01/data/nodered
sudo -u <alumno> labctl restart
```

Cada imagen corre con **su** uid: Node-RED usa `1000`, Mosquitto `1883`. Al
sembrar el proyecto, ajustá el dueño de cada carpeta de datos a ese uid (ver el
ejemplo [`ejemplos/nodered-mqtt/`](ejemplos/nodered-mqtt/)).

**Lección:** `EACCES` / "permission denied" ≈ **permisos**. En un bind mount, la
carpeta del host tiene que ser escribible por el **uid con el que corre el
contenedor**, no por el del alumno.

---

## Casos a documentar (próximamente)
- Un alumno **rompe** su Compose (la política lo rechaza: cómo leer el error).
- **El disco se llena** (cuota del equipo, `labctl usage`, dashboard Capacity).
- **Prometheus deja de responder** (dónde mirar, cómo reiniciar).
- **Grafana muestra un contenedor `unhealthy`** (healthchecks, logs).
- **DuckDNS deja de actualizar** (timer, token, logs).
- **La máquina pierde Internet** (qué sigue andando: consola, Tailscale directo).

## 🧠 Ideas clave

- Diagnosticar es **aislar la capa** y **confirmar** con un comando.
- "Se cuelga" ≈ red/DNS; "permission denied" ≈ permisos; "connection refused" ≈
  el servicio no está escuchando.

## 🛠️ Ejercicios

1. Ante "connection refused" a un servicio, listá 3 comandos para diagnosticar.
2. Tu app no resuelve `postgres`: ¿qué revisás primero?
