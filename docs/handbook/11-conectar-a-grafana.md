# 11. Conectar tus sensores y actuadores a Grafana

🎯 **Objetivo:** que lo que mide o hace tu ESP32 aparezca **solo** en el Grafana
del aula, en el dashboard de tu equipo, con historial de los últimos **15 días**.

🧩 **Prerequisitos:** tu placa ya se conecta al broker del aula (`mqtt-aula`).
Si todavía no, empezá por la [guía del equipo](guia-equipo.md#331-broker-del-aula-mqtt-aula-para-conectar-una-esp32).

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

**Un JSON plano** con varios valores a la vez (útil para sensores tipo DHT):

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

Están en el servidor, en el archivo de tu equipo (solo lectura):

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

Usá el **"último deseo"** (Last Will) de MQTT: al conectarte le decís al broker
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

Primera vez, en la consola de Thonny y con WiFi: `import mip; mip.install("umqtt.simple")`.

---

## Ejemplo B — Arduino (sensor + actuador)

Librería **PubSubClient** (Herramientas → Administrar bibliotecas).

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

## Comprobar que llega a Grafana

1. Entrá a **https://grafana-aula.lucasland.duckdns.org** (con Tailscale
   conectado; usuario y clave del aula). Cómo usarlo: [manual 12](12-usar-grafana.md).
2. Menú → **Dashboards** → carpeta **equipo-NN** → **equipo-NN — sensores y actuadores**.
3. En la tabla **Estado actual** tiene que aparecer tu `dispositivo` y tu
   `magnitud`, con el **último valor** y **hace cuántos segundos** llegó.

Llega en menos de **15 segundos** desde que la placa publica.

---

## Si no aparece

| Síntoma | Causa más probable | Qué hacer |
|---|---|---|
| La placa dice `MQTT OK` pero en Grafana no hay nada | el topic no empieza con `equipo-NN/` (con guion) o tiene menos de 3 partes | revisá la Regla 1 |
| Aparece el dispositivo pero no la magnitud | el mensaje no es número ni palabra de la tabla | revisá la Regla 2 (¿coma decimal? ¿unidades pegadas?) |
| La placa da error `5` o `4` | usuario o clave mal | usuario con guion bajo, clave de `MQTT_PASSWORD=` |
| La placa da error `-2` o `-4` | no llega o falta TLS | puerto `10000`, `WiFiClientSecure` + `setInsecure()` |
| "Hace" crece en la tabla y no baja | la placa dejó de publicar | mirá el monitor serie / Thonny |
| Tus gráficos tienen picos raros cada tanto | publicás muy rápido o mezclás unidades | Regla 3 |
