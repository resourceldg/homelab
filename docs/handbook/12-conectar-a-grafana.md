# 12. Conectar tus sensores y actuadores a Grafana

🎯 **Objetivo:** que lo que mide o hace tu ESP32 aparezca **solo** en el Grafana
del aula, en el dashboard de tu equipo, con historial de los últimos **15 días**.

> 🚧 **Estado (octubre 2026): el Grafana del aula se está poniendo en marcha.**
> Todavía no está disponible: el profe avisa cuando lo esté. Mientras tanto ya
> podés **preparar tu placa** siguiendo las reglas de este capítulo: lo que
> publiques bien desde ahora va a aparecer solo cuando se active.

🧩 **Prerequisitos:** [capítulo 11 (Arquitectura IoT)](11-arquitectura-iot.md),
para entender las piezas. Los datos de tu equipo están en la
[guía del equipo](guia-equipo.md#33-mqtt-usa-el-broker-del-aula-mqtt-aula).

> **Palabras de este capítulo** (todas explicadas en el
> [capítulo 11](11-arquitectura-iot.md) y en el [glosario](glosario.md)):
>
> - **MQTT:** el idioma con el que las placas se mandan mensajes cortos.
> - **Broker:** el programa que recibe los mensajes y los reparte (`mqtt-aula`).
> - **Topic:** el "nombre del grupo" al que mandás un mensaje, escrito como una
>   ruta: `equipo-04/enchufe/estado`.
> - **Publicar:** mandar un mensaje a un topic.
> - **Payload:** el contenido del mensaje (`23.5`, `ON`).
> - **TLS:** el cifrado del viaje; como mandar una carta en sobre cerrado.
> - **Grafana:** el programa de tableros donde se **ven** los datos.

---

## Cómo funciona (la idea en un dibujo)

```
 tu ESP32 ──publica──► mqtt-aula ──► se guarda (15 días) ──► Grafana del aula
                         (broker)                              └ dashboard de TU equipo
```

No tenés que instalar nada en el servidor ni tocar Grafana para que aparezca:
**si publicás respetando las 3 reglas de abajo, tus datos se guardan y se ven
solos.** Grafana es para **ver**; para **mandar órdenes** (prender un LED) seguís
usando Node-RED o tu página.

---

## Las 3 reglas

### Regla 1 — El topic tiene 3 partes (o más)

```
equipo-NN / dispositivo / magnitud
```

| Parte | Qué es | Ejemplos |
|---|---|---|
| `equipo-NN` | tu equipo, **con guion** | `equipo-04` |
| `dispositivo` | qué placa o aparato | `enchufe`, `puerta`, `sala`, `invernadero` |
| `magnitud` | qué medís o qué estado es | `temperatura`, `humedad`, `estado`, `reed` |

Ejemplos que **sí** funcionan:

```
equipo-04/enchufe/estado
equipo-03/sala/temperatura
equipo-01/puerta/reed
equipo-02/invernadero/suelo/humedad      (más de 3 partes: se juntan como "suelo_humedad")
```

Ejemplos que **no** se guardan:

```
equipo-04/temperatura          (faltan partes: ¿de qué dispositivo?)
casa/sala/temperatura          (no empieza con tu equipo: el broker lo descarta)
equipo_04/sala/temperatura     (guion bajo: ese es el USUARIO, no el topic)
```

> **Por qué así:** Grafana arma los gráficos agrupando por dispositivo y
> magnitud. Si el topic no los trae, no hay cómo ordenarlos.

### Regla 2 — El mensaje es un número, una palabra de estado o un JSON

**Un número** (con punto decimal, no coma):

```
23.5
-4
1013
```

**Una palabra de estado** (mayúsculas o minúsculas da igual). Se guardan como
1 o 0 para poder graficarlas:

| Se guarda como **1** | Se guarda como **0** |
|---|---|
| `ON` `on` `true` | `OFF` `off` `false` |
| `encendido` `prendido` `activo` | `apagado` `inactivo` |
| `abierto` | `cerrado` |
| `online` | `offline` |
| `alto` `si` `sí` `detectado` | `bajo` `no` `libre` |

**Un JSON plano** con varios valores a la vez. **JSON** (*JavaScript Object
Notation*) es una forma de escribir datos con **nombre: valor** entre llaves,
que entienden casi todos los programas. "Plano" quiere decir sin cajas adentro
de cajas. Es útil para sensores que miden dos cosas a la vez, como el **DHT**
(un sensor barato de temperatura y humedad):

```json
{"temp": 22.1, "hum": 61}
```

Publicado en `equipo-03/sala/clima`, aparece como dos magnitudes: `clima_temp` y
`clima_hum`.

**Lo que NO se guarda:** texto libre (`"hola"`, `"temperatura alta"`), números
con coma (`23,5`) o con unidades pegadas (`23.5C`). Si necesitás mandar texto,
mandalo a Node-RED: Grafana grafica números.

### Regla 3 — Publicá seguido y con mesura

- **Sensores:** cada **5 a 60 segundos** está bien. Más rápido que 1 por
  segundo no sirve para ver y llena la base.
- **Actuadores:** publicá el **estado confirmado** cada vez que cambia (como
  `equipo-04/enchufe/estado`).
- **Nunca** publiques dentro de un `while True` sin `sleep`: son miles de
  mensajes por segundo y el sistema te frena.

---

## Datos de conexión

Están en el servidor, en el archivo de tu equipo (solo lectura). Para leerlo
tenés que entrar al servidor por **SSH** (la conexión segura por terminal; ver
[guía del equipo, paso 1.2](guia-equipo.md#12-el-tunel-ssh-traer-tus-servicios-a-tu-compu)):

```
/srv/classroom/equipo-NN/.shared-services.env
```

Para verlos, **entrá por SSH al servidor** y corré (cambiá `NN` por tu número):

```
grep MQTT_ /srv/classroom/equipo-NN/.shared-services.env
```

| Dato | Valor |
|---|---|
| Servidor (host) | `homelab-01.tail4eda13.ts.net` |
| Puerto | `10000` (con **TLS**) |
| Usuario | `equipo_NN` (con **guion bajo**) |
| Clave | la de `MQTT_PASSWORD=` |

---

## Bonus profesional: que Grafana sepa si tu placa está conectada

Usá el **"último deseo"** (*Last Will*) de MQTT, que es como dejarle dicho a un
amigo "si no te contesto, avisale a los demás que me quedé sin batería": al conectarte le decís al broker
*"si me desconecto de golpe, publicá `offline` por mí"*. Y apenas conectás,
publicás `online`. Así Grafana muestra si la placa está viva aunque no esté
mandando datos.

Topic: `equipo-NN/<dispositivo>/conexion` con `online` / `offline` (retenido).

Está incluido en los dos ejemplos de abajo.

---

## Ejemplo A — MicroPython (sensor + actuador)

Mide un valor cada 10 segundos (acá simulado con el sensor de temperatura
interno; cambialo por el tuyo), y maneja un LED que se ordena desde Node-RED.

Archivo `main.py` en la ESP32:

```python
from machine import Pin
import time, network, ssl, esp32
from umqtt.simple import MQTTClient

WIFI_SSID = "NOMBRE_WIFI"
WIFI_PASS = "CLAVE_WIFI"

EQUIPO = "equipo-NN"
DISPOSITIVO = "placa1"
MQTT_HOST = "homelab-01.tail4eda13.ts.net"
MQTT_PORT = 10000
MQTT_USER = "equipo_NN"
MQTT_PASS = "CLAVE_MQTT"

T_CONEXION = EQUIPO + "/" + DISPOSITIVO + "/conexion"
T_TEMP = EQUIPO + "/" + DISPOSITIVO + "/temperatura"
T_LED_CMD = EQUIPO + "/" + DISPOSITIVO + "/led/cmd"
T_LED_ESTADO = EQUIPO + "/" + DISPOSITIVO + "/led/estado"

led = Pin(2, Pin.OUT)
wlan = network.WLAN(network.STA_IF)


def conectar_wifi():
    wlan.active(False)
    time.sleep(0.5)
    wlan.active(True)
    wlan.disconnect()
    wlan.connect(WIFI_SSID, WIFI_PASS)
    for _ in range(40):
        if wlan.isconnected():
            print("WiFi OK", wlan.ifconfig()[0])
            return
        time.sleep(0.5)
    raise OSError("No conecta al WiFi")


def al_recibir(topic, msg):
    led.value(1 if msg in (b"ON", b"1") else 0)
    cliente.publish(T_LED_ESTADO, "ON" if led.value() else "OFF", retain=True)


def conectar_mqtt():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.verify_mode = ssl.CERT_NONE
    c = MQTTClient(EQUIPO + "-" + DISPOSITIVO, MQTT_HOST, port=MQTT_PORT,
                   user=MQTT_USER, password=MQTT_PASS, keepalive=60, ssl=ctx)
    c.set_last_will(T_CONEXION, "offline", retain=True)
    c.set_callback(al_recibir)
    c.connect()
    c.publish(T_CONEXION, "online", retain=True)
    c.subscribe(T_LED_CMD)
    print("MQTT OK")
    return c


while True:
    try:
        if not wlan.isconnected():
            conectar_wifi()
        cliente = conectar_mqtt()
        ultimo = 0
        while True:
            cliente.check_msg()
            if time.ticks_diff(time.ticks_ms(), ultimo) > 10000:
                ultimo = time.ticks_ms()
                temp_c = (esp32.raw_temperature() - 32) / 1.8
                cliente.publish(T_TEMP, "{:.1f}".format(temp_c))
            time.sleep_ms(50)
    except Exception as e:
        print("Error, reintento en 5 s:", e)
        time.sleep(5)
```

Primera vez: la placa necesita la librería **umqtt.simple** (el código que sabe
hablar MQTT). Se instala con **mip**, el instalador de paquetes de MicroPython.
En la consola de **Thonny** (el programa con el que cargás código a la placa),
con la placa ya conectada al WiFi, escribí:

```
import mip; mip.install("umqtt.simple")
```

---

## Ejemplo B — Arduino (sensor + actuador)

Necesita la librería **PubSubClient** (el código que sabe hablar MQTT en
Arduino). En el IDE de Arduino (el programa donde escribís y cargás el código):
**Herramientas → Administrar bibliotecas** → buscar `PubSubClient` → Instalar.

Dos piezas del código que conviene entender:

- **`WiFiClientSecure` + `setInsecure()`:** la conexión va **cifrada** (TLS),
  pero sin comprobar el certificado del servidor (el "documento de identidad"
  del servidor). Para el aula alcanza; en un producto real se verificaría.
- **`mqtt.connect(id, usuario, clave, topicDeseo, 0, true, "offline")`:** entra
  al broker con usuario y clave, y deja registrado el último deseo.

```cpp
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

const char* WIFI_SSID = "NOMBRE_WIFI";
const char* WIFI_PASS = "CLAVE_WIFI";

const char* MQTT_HOST = "homelab-01.tail4eda13.ts.net";
const int   MQTT_PORT = 10000;
const char* MQTT_USER = "equipo_NN";
const char* MQTT_PASS = "CLAVE_MQTT";
const char* CLIENT_ID = "equipo-NN-placa1";

const char* T_CONEXION   = "equipo-NN/placa1/conexion";
const char* T_TEMP       = "equipo-NN/placa1/temperatura";
const char* T_LED_CMD    = "equipo-NN/placa1/led/cmd";
const char* T_LED_ESTADO = "equipo-NN/placa1/led/estado";

const int LED_PIN = 5;

WiFiClientSecure red;
PubSubClient mqtt(red);
unsigned long ultimo = 0;

void alRecibir(char* topic, byte* payload, unsigned int largo) {
  String msg;
  for (unsigned int i = 0; i < largo; i++) msg += (char)payload[i];
  bool on = (msg == "ON" || msg == "1");
  digitalWrite(LED_PIN, on ? HIGH : LOW);
  mqtt.publish(T_LED_ESTADO, on ? "ON" : "OFF", true);
}

void conectar() {
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  while (!mqtt.connected()) {
    // usuario, clave y "último deseo": si se corta, el broker publica offline
    if (mqtt.connect(CLIENT_ID, MQTT_USER, MQTT_PASS, T_CONEXION, 0, true, "offline")) {
      mqtt.publish(T_CONEXION, "online", true);
      mqtt.subscribe(T_LED_CMD);
      Serial.println("MQTT OK");
    } else {
      Serial.printf("MQTT falló (estado %d), reintento en 5 s\n", mqtt.state());
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  red.setInsecure();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(alRecibir);
  mqtt.setKeepAlive(60);
}

void loop() {
  if (!mqtt.connected()) conectar();
  mqtt.loop();
  if (millis() - ultimo > 10000) {
    ultimo = millis();
    float temp = temperatureRead();          // cambialo por tu sensor
    mqtt.publish(T_TEMP, String(temp, 1).c_str());
  }
}
```

---

## Comprobar que llega (en dos pasos)

### 1. ¿Llegó al broker? → MQTT Explorer

Antes de mirar Grafana, confirmá que tu mensaje **entró al servidor**. Con
**MQTT Explorer** te conectás al broker desde tu compu, con la clave de tu equipo,
y ves tus topics en vivo. Cómo configurarlo:
[la herramienta clave del diagnóstico](diagnostico.md#la-herramienta-clave-escuchar-el-broker-desde-tu-compu).

Si tu topic aparece ahí con el valor correcto, **la placa y la red están bien**:
cualquier problema está del broker para adelante.

### 2. ¿Se guardó? → Grafana

> 🚧 Mientras el Grafana del aula se pone en marcha, el paso 1 es la comprobación
> que sí podés hacer.

1. Entrá a **https://grafana-aula.lucasland.duckdns.org** con **Tailscale**
   conectado (la red privada del aula) y tu usuario y contraseña del aula. Cómo
   usarlo: [capítulo 13](13-usar-grafana.md).
2. Menú → **Dashboards** → carpeta **equipo-NN** → **equipo-NN — sensores y actuadores**.
3. En la tabla **Estado actual** tiene que aparecer tu `dispositivo` y tu
   `magnitud`, con el **último valor** y **hace cuántos segundos** llegó.

Llega en unos **15 segundos** desde que la placa publica
([por qué ese tiempo](11-arquitectura-iot.md#paso-a-paso)).

---

## Si no aparece

Los errores más comunes, en una línea (el recorrido completo, paso a paso, está en
el **[Diagnóstico](diagnostico.md#mi-esp32-mide-pero-no-veo-los-datos)**):

| Síntoma | Causa más probable | Ir a… |
|---|---|---|
| MQTT Explorer **no** ve tu topic | el topic no empieza con `equipo-NN/` (guion) o la placa no llegó | [Regla 1](#regla-1-el-topic-tiene-3-partes-o-mas) · [diagnóstico, pasos 3 a 6](diagnostico.md#paso-3-llega-al-broker) |
| MQTT Explorer lo ve, Grafana **no** | el mensaje no es número ni palabra de estado, o tiene menos de 3 partes | [Regla 2](#regla-2-el-mensaje-es-un-numero-una-palabra-de-estado-o-un-json) |
| La placa da error `5` o `4` | usuario o clave MQTT mal | [tabla de credenciales](red-y-accesos.md#tus-credenciales-en-una-tabla) |
| La placa da error `-2` o `-4` | no llega, o falta el cifrado | [diagnóstico, paso 3](diagnostico.md#paso-3-llega-al-broker) |
| "Hace" crece en la tabla y no baja | la placa dejó de publicar | mirá Thonny / el Monitor Serie |
| Picos raros en los gráficos | publicás muy rápido o mezclás unidades | [Regla 3](#regla-3-publica-seguido-y-con-mesura) |

---

## Ahora deberías entender

- Que **el topic es un contrato**: `equipo-NN/dispositivo/magnitud`, y el mensaje
  un número, una palabra de estado o un JSON.
- Que tu placa **solo conoce al broker**: lo que pasa después (guardar, mostrar) lo
  hacen otros ([quién conoce a quién](11-arquitectura-iot.md#quien-conoce-a-quien)).
- Cómo comprobar que llegó: primero **MQTT Explorer**, después **Grafana**.

**Seguí por acá:**

- Si querés **armar tus gráficos** → [capítulo 13](13-usar-grafana.md).
- Si necesitás **calcular algo o reaccionar** a tus datos → [¿Node-RED, Grafana o ambos?](node-red-o-grafana.md).
- Si **no aparece** → [Diagnóstico](diagnostico.md).
