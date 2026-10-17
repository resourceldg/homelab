#!/usr/bin/env python3
"""Simulador del pañol IoT (LAB01) para ThingsBoard — SOLO para pruebas.

Imita lo que publicaría el servidor de sesiones del pañol (ver
Documents/panol-iot/docs/DISENO.md): accesos concedidos, denegados y "sin
ingreso", puerta, PIR, armarios, sesiones (con relevo, ausencia y cierre) y
alguna alarma. Primero carga 24 h de historia (para que el tablero tenga
datos) y después sigue en vivo.

    TB_URL=http://127.0.0.1:18080 TB_USUARIO=admin@... TB_CLAVE_ARCHIVO=/ruta \\
        python3 simulador.py [--dispositivo panol/LAB01_simulado] [--sin-historia] [--rapido]

Crea el dispositivo (perfil "panol") si no existe y publica por MQTT con el
token del dispositivo (v1/devices/me/telemetry), el mismo camino que un nodo
real. ThingsBoard tiene el transporte HTTP apagado y su MQTT solo se ve dentro
de la red de Docker: correrlo en un contenedor de esa red (ver README). Por defecto el dispositivo se
llama "panol/LAB01_simulado" para no mezclar datos falsos con los reales.
Los nombres de las personas son inventados.
"""
import argparse
import json
import os
import random
import time
import urllib.parse

from tablero import TB, PERFIL

PERSONAS = [("Martina Ríos", "Alumna"), ("Tomás Ledesma", "Alumno"), ("Valentina Sosa", "Alumna"),
            ("Joaquín Ferreyra", "Alumno"), ("Prof. Herrera", "Docente"), ("Lucía Benítez", "Pañolera")]
DESCONOCIDAS = ["04:A3:1F:7C", "9B:22:E0:41", "13:5D:8A:C6"]


class Pañol:
    """Estado y publicación. `ts` permite cargar historia con horas pasadas."""

    def __init__(self, mqtt_cliente, rapido):
        self.mqtt = mqtt_cliente
        self.rapido = rapido
        self.lote = []
        self.sesion = None

    def pub(self, ts, **valores):
        self.lote.append({"ts": int(ts * 1000), "values": valores})
        if len(self.lote) >= 200:
            self.enviar()

    def dormir(self, seg):
        """Espera en vivo sin que el nodo parezca caído: latido cada 20 s."""
        fin = time.time() + seg / (6 if self.rapido else 1)
        while time.time() < fin:
            time.sleep(min(20, max(0, fin - time.time())))
            self.pub(time.time(), latido=1)
            self.enviar()

    def enviar(self):
        if not self.lote:
            return
        self.mqtt.publish("v1/devices/me/telemetry", json.dumps(self.lote), qos=1).wait_for_publish(30)
        self.lote = []

    # Un ciclo completo: alguien pasa la tarjeta, entra, trabaja, sale (o no).
    def ciclo(self, t, vivo):
        def paso(seg):
            nonlocal t
            if vivo:
                self.enviar()
                self.dormir(seg)
                t = time.time()
            else:
                t += seg
            return t
        r = random.random()
        if r < 0.12:                                   # tarjeta desconocida
            self.pub(t, acceso="DENEGADO", acceso_usuario=random.choice(DESCONOCIDAS), acceso_denegado=1)
            return paso(random.uniform(60, 400))
        nombre, rol = random.choice(PERSONAS)
        if r < 0.20:                                   # liberó la puerta pero no entró
            self.pub(t, acceso="SIN_INGRESO", acceso_usuario=nombre, acceso_sin_ingreso=1)
            return paso(random.uniform(60, 400))
        self.pub(t, acceso="CONCEDIDO", acceso_usuario=nombre, acceso_concedido=1)
        paso(2)
        self.pub(t, puerta=1)
        if self.sesion:                                # relevo: cierra la anterior
            self.pub(t, fin_sesion="RELEVO")
        self.sesion = nombre
        self.pub(t, sesion=1, sesion_nueva=1, sesion_usuario=nombre, sesion_rol=rol, sesion_inicio=int(t * 1000))
        paso(4)
        self.pub(t, pir=1, pir_evento=1)
        paso(5)
        self.pub(t, puerta=0)
        for _ in range(random.randint(1, 3)):          # trabaja: armarios y movimiento
            paso(random.uniform(15, 90))
            n = random.randint(1, 4)
            self.pub(t, **{f"armario{n}": 1, "pir": 1, "pir_evento": 1})
            paso(random.uniform(8, 30))
            self.pub(t, **{f"armario{n}": 0})
        paso(random.uniform(30, 240))
        if random.random() < 0.85:                     # sale y se cierra por ausencia
            self.pub(t, puerta=1)
            paso(4)
            self.pub(t, puerta=0)
            paso(random.uniform(40, 120))
            self.pub(t, sesion=0, fin_sesion="AUSENCIA")
            self.sesion = None
        return paso(random.uniform(60, 600))

    def alarma(self, t, codigo, vivo):
        clave = "alarma_" + codigo.lower()
        if codigo == "APERTURA_SIN_CREDENCIAL":
            self.pub(t, puerta=1)
        if codigo == "PRESENCIA_SIN_SESION":
            self.pub(t, pir=1, pir_evento=1)
        self.pub(t, alarma=codigo, alarma_evento=1, **{clave: 1})
        if vivo:
            self.enviar()
            self.dormir(20)
            t = time.time()
        else:
            t += random.uniform(60, 300)
        self.pub(t, alarma="OK", puerta=0, **{clave: 0})
        return t


def dispositivo(tb, nombre):
    ds = tb.req("GET", "/api/tenant/devices?pageSize=10&page=0&textSearch=" + urllib.parse.quote(nombre))["data"]
    d = next((x for x in ds if x["name"] == nombre), None)
    if d is None:
        perfiles = tb.req("GET", "/api/deviceProfiles?pageSize=100&page=0&textSearch=" + PERFIL)["data"]
        perfil = next((p for p in perfiles if p["name"] == PERFIL), None)
        cuerpo = {"name": nombre, "label": "Nodo del pañol (simulado)"}
        if perfil:
            cuerpo["deviceProfileId"] = perfil["id"]
        d = tb.req("POST", "/api/device", cuerpo)
        print("dispositivo creado:", nombre)
    did = d["id"]["id"]
    # Inactividad corta: si el nodo deja de hablar 2 min, figura "sin conexión".
    tb.req("POST", f"/api/plugins/telemetry/DEVICE/{did}/attributes/SERVER_SCOPE", {"inactivityTimeout": 120000})
    return tb.req("GET", f"/api/device/{did}/credentials")["credentialsId"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dispositivo", default="panol/LAB01_simulado")
    ap.add_argument("--sin-historia", action="store_true")
    ap.add_argument("--mqtt", default=os.environ.get("TB_MQTT", "thingsboard:1883"),
                    help="host:puerto del MQTT de ThingsBoard")
    ap.add_argument("--rapido", action="store_true", help="todo 6 veces más rápido (para mostrar)")
    args = ap.parse_args()
    clave = open(os.environ["TB_CLAVE_ARCHIVO"]).read().strip() if os.environ.get("TB_CLAVE_ARCHIVO") \
        else os.environ.get("TB_CLAVE", "")
    base = os.environ.get("TB_URL", "http://127.0.0.1:18080")
    token = dispositivo(TB(base, os.environ["TB_USUARIO"], clave), args.dispositivo)
    import paho.mqtt.client as mqtt
    host, puerto = args.mqtt.rsplit(":", 1)
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="panol-lab01-simulador")
    c.username_pw_set(token)
    c.connect(host, int(puerto))
    c.loop_start()
    p = Pañol(c, args.rapido)

    if not args.sin_historia:
        t = time.time() - 24 * 3600
        while t < time.time() - 600:
            h = time.localtime(t).tm_hour
            if 8 <= h < 22:
                t = p.ciclo(t, vivo=False) + random.uniform(120, 900)
                if random.random() < 0.04:
                    t = p.alarma(t, random.choice(["PRESENCIA_SIN_SESION", "ARMARIO_SIN_SESION"]), vivo=False)
            else:
                if p.sesion:                           # 22:00: cierre de jornada
                    p.pub(t, sesion=0, fin_sesion="CIERRE_SISTEMA")
                    p.sesion = None
                t += 1800
        p.pub(time.time() - 300, sesion=0, puerta=0, alarma="OK",
              armario1=0, armario2=0, armario3=0, armario4=0)
        p.enviar()
        print("historia de 24 h cargada")

    print("en vivo (Ctrl+C para cortar)")
    while True:
        p.pub(time.time(), latido=1)
        if random.random() < 0.08:
            p.alarma(time.time(), random.choice(["APERTURA_SIN_CREDENCIAL", "PRESENCIA_SIN_SESION",
                                                 "ARMARIO_SIN_SESION"]), vivo=True)
        else:
            p.ciclo(time.time(), vivo=True)
        p.enviar()


if __name__ == "__main__":
    main()
