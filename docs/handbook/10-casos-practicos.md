# 10. Casos prácticos

🎯 **Objetivo:** aprender a **diagnosticar y resolver** problemas reales, con
recorridos paso a paso. Es el capítulo "de taller".

🧩 **Prerequisitos:** todos los anteriores (se usan como referencia).

> 📝 **Capítulo en crecimiento.** Tiene nueve casos reales: tres del servidor y
> seis de las placas de los equipos. Se suman más a medida que pasan.

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

## Casos de la ESP32 y la red (septiembre–octubre 2026)

Los casos que siguen **pasaron en clase**, con las placas de los equipos. Para
cada uno: qué se vio, cómo se encontró la causa (casi siempre **mirando del otro
lado**: los registros del servidor) y qué nos llevamos.

> **Herramienta clave de todos estos casos:** el **registro** (*log*) del broker.
> Es un cuaderno donde el broker anota cada conexión: quién entró, con qué
> usuario y si lo rechazó. Leerlo es como preguntarle al portero "¿vino alguien?".
> Lo lee el operador en el servidor con `docker logs mqtt-aula`.

---

## Caso 4 — `Wifi Internal State Error` después de reiniciar

**Síntoma** (placa de Mijael, en Thonny):

```
E (912940) wifi:sta is connecting, cannot set config
OSError: Wifi Internal State Error
```

**Diagnóstico:** apareció después de un **soft reboot** (reinicio "suave": Ctrl+D
o el botón Run de Thonny, que reinicia el programa pero **no** apaga el chip). El
WiFi había quedado **a mitad de conectarse** del intento anterior, y el código
volvió a pedirle `connect()`. El chip contestó "estoy ocupado conectando, no
puedo cambiar la configuración".

**Solución:** antes de conectar, **apagar y prender** el WiFi para empezar de cero:

```python
wlan.active(False)
time.sleep(0.5)
wlan.active(True)
wlan.disconnect()
wlan.connect(WIFI_SSID, WIFI_PASS)
```

**Lección:** no asumas que el aparato arranca "limpio". Llevalo vos a un estado
conocido antes de usarlo.

---

## Caso 5 — El error `5` o `not authorised`: claves mezcladas

**Síntoma:** en la placa, `Error, reintento en 5 s: 5` cada pocos segundos. En el
registro del broker:

```
New connection from 172.21.0.1 on port 1883.
Client esp32-equipo-03 disconnected, not authorised.
```

**Diagnóstico:** la placa **sí llegaba** al servidor (la conexión aparece en el
registro), pero el broker la **rechazaba**. El `5` es el código de MQTT para "no
autorizado". En `MQTT_PASS` estaba la contraseña de **entrar al servidor por
SSH**, no la del **broker**. Con Jessi pasó parecido: tenía la clave de otro
equipo.

**Las claves de un alumno, para no confundirlas:**

| Para qué | Usuario | Clave |
|---|---|---|
| Entrar al servidor (SSH) y a Grafana | tu nombre (`mijael`) | la del aula |
| Que la **placa** entre al broker | el del equipo con **guion bajo** (`equipo_03`) | `MQTT_PASSWORD` de `.shared-services.env` |

**Lección:** si el servidor **ve** tu intento y lo rechaza, el problema es **quién
sos** (usuario/clave), no la red.

---

## Caso 6 — El error `4` y en el servidor no aparece nada

**Síntoma:** el enchufe de Jorge mostraba `Error 4 - Reintentando en 5 segundos`.
Pero en el registro del broker **no había ningún intento** de su placa.

**Diagnóstico:** si la placa estuviera hablando con nuestro broker, el registro lo
mostraría (aunque fuera para rechazarla, como en el caso 5). Que no aparezca nada
quiere decir que **está hablando con otro lado**. Al leer **todo** el código del
proyecto (no solo el archivo que nos pasaron), `config.h` seguía apuntando a
otro broker de su red de casa:

```cpp
constexpr char MQTT_BROKER[] = "192.168.18.17";   // otro broker
constexpr int MQTT_PORT = 1883;                    // sin cifrado
```

Y `mqtt_manager.cpp` se conectaba sin cifrado (`WiFiClient`) y sin usuario.

**Solución:** apuntar al broker del aula (`homelab-01.tail4eda13.ts.net`, puerto
`10000`), usar el cliente cifrado (`WiFiClientSecure` + `setInsecure()`) y
mandar usuario y clave. Ver [capítulo 14](14-proyectos-de-los-equipos.md#caso-3-el-enchufe-de-jorge-equipo-04).

**Lección:** "no aparece nada del otro lado" es una pista enorme: el mensaje no
está llegando al lugar que creés. Y siempre leé **todo** el proyecto, no solo el
archivo que parece importante.

---

## Caso 7 — `MBEDTLS_ERR_SSL_CONN_EOF`: una puerta de entrada caída

**Síntoma:** la placa de Mijael, que andaba, empezó a fallar con:

```
Error, reintento en 5 s: (-29312, 'MBEDTLS_ERR_SSL_CONN_EOF')
```

**Qué significa:** **mbedTLS** es la librería que hace el cifrado (TLS) en la
ESP32. `CONN_EOF` (*End Of File*, fin del archivo) quiere decir "el otro lado
cortó la conexión mientras se armaba el cifrado".

**Diagnóstico:** el nombre `homelab-01.tail4eda13.ts.net` apunta a **dos**
servidores de entrada de Tailscale Funnel (dos "porteros"). Probando cada uno por
separado, uno andaba y **el otro cortaba siempre**, con el mismo error que la
placa. A la placa le había tocado el que fallaba, y lo recordaba.

| Puerta de entrada | Resultado |
|---|---|
| `209.177.145.97` | ✅ conecta |
| `209.177.145.192` | ❌ corta (`unexpected eof`) |

**Solución:** era una falla del servicio externo (Tailscale); al rato se
normalizó. Mientras tanto, **desenchufar y enchufar** la placa la hace preguntar
de nuevo y puede tocarle la puerta buena.

**Lección:** antes de cambiar tu código, **medí cada pieza del camino**. A veces
el problema no es tuyo, y saberlo ahorra horas.

---

## Caso 8 — `ON` y `OFF` contra `1` y `0`: el contrato sin acordar

**Síntoma:** el enchufe de Jorge conectaba bien, pero al mover el interruptor del
dashboard **no pasaba nada**.

**Diagnóstico:** el dashboard mandaba `1` y `0`; el código de Jorge esperaba
`ON` y `OFF`. Los dos tenían razón según su propia idea, pero **nunca habían
acordado** cómo se iban a hablar.

**Solución:** se adaptó el dashboard a `ON`/`OFF` (cambiar un lado es más simple
que cambiar los dos). Grafana entiende los dos formatos.

**Lección:** el formato de los mensajes es un **contrato** (ver
[capítulo 11, decisión 2](11-arquitectura-iot.md#decision-2-el-topic-es-un-contrato)).
Se acuerda **antes** de programar y se escribe, para que las dos puntas lo
respeten.

---

## Caso 9 — El servidor se mudó de red y el firewall seguía mirando la vieja

**Síntoma:** desde la red de la casa, `ssh` al servidor quedaba colgado hasta dar
`Connection timed out`. Por Tailscale, en cambio, entraba bien.

**Diagnóstico:** el servidor cambió de red varias veces
(`192.168.100.x` → `192.168.0.x` → `192.168.8.x`, al cambiar de router o de WiFi).
El **firewall** (el "patovica" que decide qué conexiones dejar entrar, en el
servidor se llama UFW) solo dejaba entrar por SSH desde la red **vieja**. Para él,
la red nueva era "un desconocido".

**Solución:** actualizar en el inventario de Ansible la red de la casa
(`lan_cidr`) y volver a aplicar el firewall. Mientras tanto, se entra por
Tailscale, que no depende de la red de la casa.

**Lección:** cuando algo **se cuelga** (no da error, solo espera) sospechá de la
**red** o del **firewall** antes que de la aplicación. Y tené siempre **una
segunda puerta** (acá, Tailscale) para no quedarte afuera.

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
