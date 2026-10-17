"""Simulador de ESP32 para la demo y las pruebas (tb-simulador).

Publica en mqtt-aula EXACTAMENTE como una placa de un equipo: mismo broker,
mismo contrato de topics (<equipo>/<dispositivo>/<magnitud>), mismos tipos de
payload (número, palabra de estado y JSON plano). Así la prueba de extremo a
extremo recorre el camino real: broker -> puente -> ThingsBoard -> tablero.

Proyectos de demostración (cuenta MQTT `tb-demo`, ACL solo sobre estos árboles):
    demo-meteo      estación meteorológica
    demo-seguridad  puerta + sensor de movimiento
    demo-ambiente   calidad de aire y ruido
"""
import json
import math
import os
import random
import signal
import threading
import time

import paho.mqtt.client as mqtt

PERIODO = float(os.environ.get("PERIODO_SEGUNDOS", "10"))


def lecturas(t):
    dia = math.sin(t / 600.0)   # "día" de 1 hora, para que se vea moverse
    yield "demo-meteo/estacion/temperatura", f"{21 + 6 * dia + random.uniform(-.3, .3):.1f}"
    yield "demo-meteo/estacion/humedad", f"{55 - 15 * dia + random.uniform(-1, 1):.0f}"
    yield "demo-meteo/estacion/presion", f"{1013 + 4 * math.sin(t / 1800.0):.1f}"
    yield "demo-meteo/estacion/viento", json.dumps(
        {"velocidad": round(abs(12 * math.sin(t / 300.0)) + random.uniform(0, 3), 1),
         "rafaga": round(abs(18 * math.sin(t / 300.0)) + random.uniform(0, 5), 1)})
    yield "demo-seguridad/puerta/estado", random.choice(["cerrado"] * 9 + ["abierto"])
    yield "demo-seguridad/pir/movimiento", random.choice(["libre"] * 4 + ["detectado"])
    yield "demo-seguridad/nodo/bateria", f"{max(0, 100 - (t % 86400) / 864):.0f}"
    yield "demo-ambiente/aula1/aire", json.dumps(
        {"co2": int(450 + 350 * max(0, dia) + random.uniform(-20, 20)),
         "pm25": round(8 + random.uniform(0, 6), 1)})
    yield "demo-ambiente/aula1/ruido", f"{45 + 20 * max(0, dia) + random.uniform(-3, 3):.0f}"


def main():
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="tb-simulador")
    clave = os.environ.get("MQTT_PASS") or open(os.environ["MQTT_PASS_FILE"]).read().strip()
    c.username_pw_set(os.environ.get("MQTT_USER", "tb-demo"), clave)
    c.reconnect_delay_set(1, 30)
    c.connect_async(os.environ.get("MQTT_HOST", "mqtt-aula"), int(os.environ.get("MQTT_PORT", "1883")))
    c.loop_start()

    parar = threading.Event()
    signal.signal(signal.SIGTERM, lambda *a: parar.set())
    signal.signal(signal.SIGINT, lambda *a: parar.set())
    while not parar.is_set():
        if c.is_connected():
            for topic, valor in lecturas(time.time()):
                c.publish(topic, valor, qos=1)
        parar.wait(PERIODO)
    c.loop_stop()
    c.disconnect()


if __name__ == "__main__":
    main()
