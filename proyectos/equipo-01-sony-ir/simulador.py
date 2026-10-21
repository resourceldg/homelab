#!/usr/bin/env python3
"""Simulador del proyecto "Sony IR + relés" (equipo-01) — SOLO para pruebas.

Publica en el broker exactamente el CONTRATO MQTT que tiene que cumplir el
firmware (ver README.md, "Contrato MQTT"), imitando su comportamiento real:
teclas 1/2/3 que alternan Relé 1, Relé 2 y el SSR, otras teclas que no
accionan nada, alguna trama inválida y el latido de conexión.

Sirve para probar el tablero sin la placa. NO lo uses contra el dispositivo
real: escribiría datos falsos en su historia. Por defecto publica con el
nombre "equipo-01/sony_ir_simulado" para que no se mezcle; --como-real solo
en un entorno de prueba (por ejemplo la réplica local).

    MQTT_PASSWORD=... python3 simulador.py --broker 127.0.0.1 --puerto 1883 --sin-tls
Requiere: pip install paho-mqtt
"""
import argparse
import os
import random
import ssl
import sys
import time

TECLAS = {"1": 0x4200, "2": 0x4201, "3": 0x4202, "MAS": 0x4212, "MENOS": 0x4213,
          "ARRIBA": 0x4233, "ABAJO": 0x4232, "MODE": 0x4247}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--broker", default="homelab-01.tail4eda13.ts.net")
    ap.add_argument("--puerto", type=int, default=10000)
    ap.add_argument("--sin-tls", action="store_true")
    ap.add_argument("--usuario", default="equipo_01")
    ap.add_argument("--como-real", action="store_true",
                    help="publicar como equipo-01/sony_ir (solo en entornos de prueba)")
    ap.add_argument("--duracion", type=int, default=0, help="segundos (0 = sin fin)")
    args = ap.parse_args()
    clave = os.environ.get("MQTT_PASSWORD") or sys.exit("Falta MQTT_PASSWORD")
    pre = "equipo-01/sony_ir" if args.como_real else "equipo-01/sony_ir_simulado"

    import paho.mqtt.client as mqtt
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="equipo-01-sony-ir-simulador")
    c.username_pw_set(args.usuario, clave)
    if not args.sin_tls:
        c.tls_set(cert_reqs=ssl.CERT_NONE)
        c.tls_insecure_set(True)
    c.connect(args.broker, args.puerto)
    c.loop_start()

    def pub(k, v):
        c.publish(f"{pre}/{k}", str(v), qos=1)
        print(f"[SIMULADO] {pre}/{k} = {v}")

    estado = {"rele1": 0, "rele2": 0, "ssr": 0}
    pub("reinicio", 1)                       # arranque: todo apagado
    pub("rssi", random.randint(-78, -52))
    for k in estado:
        pub(k, 0)
    inicio = ultimo_enlace = time.time()
    while not args.duracion or time.time() - inicio < args.duracion:
        if time.time() - ultimo_enlace >= 30:
            pub("enlace", 1)
            pub("rssi", random.randint(-78, -52))
            ultimo_enlace = time.time()
        nombre = random.choice(list(TECLAS))
        pub("tecla", TECLAS[nombre])
        salida = {"1": ("rele1", 1), "2": ("rele2", 2), "3": ("ssr", 3)}.get(nombre)
        if salida:
            clave_salida, n = salida
            estado[clave_salida] ^= 1
            pub(clave_salida, estado[clave_salida])
            pub("accionamiento", n)
        if random.random() < 0.15:
            pub("trama_invalida", random.choice([13, 14]))
        time.sleep(random.uniform(4, 12))
    c.loop_stop()
    c.disconnect()


if __name__ == "__main__":
    main()
