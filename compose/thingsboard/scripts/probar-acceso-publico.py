#!/usr/bin/env python3
"""Prueba la superficie PÚBLICA de los tableros — sale con error si algo falla.

    python3 probar-acceso-publico.py https://tableros.<tailnet>.ts.net \\
        --dashboard 'https://tableros.<tailnet>.ts.net/dashboard/<id>?publicId=<id>' \\
        [--privado <id de un dashboard NO público>]

Corre desde cualquier máquina (no necesita credenciales): es lo que puede hacer
un desconocido con un link público. Dos listas:

  DEBE ANDAR    lo que usa la vista pública (portada, dashboard, login público,
                lectura del dashboard, WebSocket con datos en vivo).
  DEBE FALLAR   todo lo que, probado contra ThingsBoard CE 4.3.1.6 DIRECTO,
                el token público sí podía hacer (escribir telemetría y
                atributos, RPC, leer credenciales) + la administración, las
                métricas y la documentación de la API.

Correrlo después de cada actualización de ThingsBoard o de cambiar el
Caddyfile público. Solo usa la biblioteca estándar.
"""
import argparse
import base64
import json
import os
import socket
import ssl
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

FALSO_ID = "00000000-0000-0000-0000-000000000000"


def pedir(base, metodo, ruta, cuerpo=None, token=None):
    datos = None if cuerpo is None else json.dumps(cuerpo).encode()
    req = urllib.request.Request(base + ruta, data=datos, method=metodo)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/plain, */*")
    if token:
        req.add_header("X-Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def ws_datos(base, token, dashboard_id, segundos=25):
    """Abre /api/ws como el navegador, se suscribe a los dispositivos del
    dashboard y devuelve cuántas actualizaciones con datos llegaron."""
    u = urllib.parse.urlparse(base)
    puerto = u.port or (443 if u.scheme == "https" else 80)
    crudo = socket.create_connection((u.hostname, puerto), timeout=10)
    s = ssl.create_default_context().wrap_socket(crudo, server_hostname=u.hostname) if u.scheme == "https" else crudo
    clave = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET /api/ws HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {clave}\r\n"
               f"Sec-WebSocket-Version: 13\r\n\r\n").encode())
    cabecera = b""
    while b"\r\n\r\n" not in cabecera:
        cabecera += s.recv(1)
    if b" 101 " not in cabecera.split(b"\r\n")[0]:
        return -1

    def enviar(obj):
        p = json.dumps(obj).encode()
        mascara = os.urandom(4)
        n = len(p)
        h = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n))
        s.sendall(h + mascara + bytes(b ^ mascara[i % 4] for i, b in enumerate(p)))

    def recibir():
        def leer(n):
            b = b""
            while len(b) < n:
                b += s.recv(n - len(b))
            return b
        b0, b1 = leer(2)
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack(">H", leer(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", leer(8))[0]
        return b0 & 0x0F, leer(n)

    # Mismo protocolo que la interfaz 4.x: primero autenticación, después
    # una consulta de entidades con suscripción a los últimos valores.
    st, cuerpo = pedir(base, "GET", f"/api/dashboard/{dashboard_id}", token=token)
    conf = json.loads(cuerpo)["configuration"]
    alias = next(iter(conf["entityAliases"].values()))
    # Las magnitudes que muestra el dashboard (de sus widgets).
    claves = sorted({k["name"] for w in conf["widgets"].values()
                     for ds in w["config"].get("datasources", [])
                     for k in ds.get("dataKeys", []) if k.get("type") == "timeseries"})[:20]
    keys = [{"type": "TIME_SERIES", "key": k} for k in claves]
    enviar({"authCmd": {"cmdId": 0, "token": token}, "cmds": [{
        "type": "ENTITY_DATA", "cmdId": 1,
        "query": {"entityFilter": alias["filter"], "pageLink": {"pageSize": 50, "page": 0},
                  "entityFields": [{"type": "ENTITY_FIELD", "key": "name"}],
                  "latestValues": keys},
        "latestCmd": {"keys": keys},
    }]})
    s.settimeout(segundos)
    llegaron = 0
    fin = time.time() + segundos
    try:
        while time.time() < fin:
            op, datos = recibir()
            if op != 1:
                continue
            msg = json.loads(datos)
            if msg.get("errorCode"):
                print(f"       WebSocket: error {msg['errorCode']}: {msg.get('errorMsg')}")
                return -2
            # Cuenta solo mensajes con VALORES (la primera página o una actualización).
            filas = (msg.get("data") or {}).get("data") or msg.get("update") or []
            if any(f.get("latest", {}).get("TIME_SERIES") for f in filas):
                llegaron += 1
    except (socket.timeout, OSError):
        pass
    s.close()
    return llegaron


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("base", help="URL pública, p. ej. https://tableros.<tailnet>.ts.net")
    ap.add_argument("--dashboard", required=True, help="link público de un dashboard")
    ap.add_argument("--privado", help="id de un dashboard que NO es público")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    q = urllib.parse.urlparse(a.dashboard)
    dash_id = q.path.rsplit("/", 1)[-1]
    public_id = urllib.parse.parse_qs(q.query)["publicId"][0]

    fallas = []

    def chequear(nombre, ok, detalle=""):
        print(f"  {'OK ' if ok else 'MAL'}  {nombre}" + (f"  ({detalle})" if detalle and not ok else ""))
        if not ok:
            fallas.append(nombre)

    print("DEBE ANDAR")
    st, _ = pedir(base, "GET", "/")
    chequear("portada", st == 200, st)
    st, _ = pedir(base, "GET", f"/dashboard/{dash_id}?publicId={public_id}")
    chequear("página del dashboard", st == 200, st)
    st, cuerpo = pedir(base, "POST", "/api/auth/login/public", {"publicId": public_id})
    chequear("login público", st == 200, st)
    token = json.loads(cuerpo)["token"] if st == 200 else None
    st, _ = pedir(base, "GET", f"/api/dashboard/{dash_id}", token=token)
    chequear("leer el dashboard", st == 200, st)
    st, _ = pedir(base, "GET", "/api/system/params", token=token)
    chequear("parámetros del sistema", st == 200, st)
    n = ws_datos(base, token, dash_id) if token else -1
    chequear("WebSocket con datos en vivo", n > 0, f"{n} mensajes")

    print("DEBE FALLAR (404 del proxy, o 401/403 de ThingsBoard)")
    rechazo = (401, 403, 404)
    sondas = [
        ("login de administración", "POST", "/api/auth/login", {"username": "sysadmin@thingsboard.org", "password": "x"}),
        ("escribir telemetría", "POST", f"/api/plugins/telemetry/DEVICE/{FALSO_ID}/timeseries/ANY", {"t": 1}),
        ("escribir atributos", "POST", f"/api/plugins/telemetry/DEVICE/{FALSO_ID}/SHARED_SCOPE", {"x": 1}),
        ("leer telemetría por REST", "GET", f"/api/plugins/telemetry/DEVICE/{FALSO_ID}/values/timeseries", None),
        ("RPC a un dispositivo", "POST", f"/api/rpc/oneway/{FALSO_ID}", {"method": "abrir", "params": {}}),
        ("leer credenciales", "GET", f"/api/device/{FALSO_ID}/credentials", None),
        ("listar dispositivos del cliente público", "GET", f"/api/customer/{public_id}/devices?pageSize=10&page=0", None),
        ("listar dispositivos del tenant", "GET", "/api/tenant/devices?pageSize=10&page=0", None),
        ("consulta de entidades por REST", "POST", "/api/entitiesQuery/find", {"entityFilter": {"type": "entityType", "entityType": "DEVICE"}, "pageLink": {"pageSize": 10, "page": 0}}),
        ("métricas internas", "GET", "/actuator/prometheus", None),
        ("documentación de la API", "GET", "/swagger-ui/index.html", None),
        ("config de administración", "GET", "/api/admin/settings/general", None),
        ("transporte HTTP de dispositivos", "POST", "/api/v1/cualquiera/telemetry", {"t": 1}),
        ("dashboard sin publicId (login de admin)", "GET", f"/dashboard/{dash_id}", None),
        ("pantalla de login", "GET", "/login", None),
        ("lista interna de tableros", "GET", "/.tableros.json", None),
        ("cuerpo grande", "POST", "/api/auth/login/public", {"publicId": "x" * 20000}),
    ]
    for nombre, metodo, ruta, cuerpo in sondas:
        st, _ = pedir(base, metodo, ruta, cuerpo, token=token)
        chequear(nombre, st in rechazo or st == 413, st)
    if a.privado:
        st, _ = pedir(base, "GET", f"/api/dashboard/{a.privado}", token=token)
        chequear("leer un dashboard PRIVADO", st in rechazo, st)

    print()
    if fallas:
        print(f"FALLARON {len(fallas)}: " + ", ".join(fallas))
        sys.exit(1)
    print("Todo en orden.")


if __name__ == "__main__":
    main()
