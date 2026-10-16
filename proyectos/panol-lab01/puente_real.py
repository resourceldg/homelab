#!/usr/bin/env python3
"""Lleva los datos REALES del pañol a ThingsBoard, leyendo la base del server.

    TB_URL=http://127.0.0.1:18080 TB_USUARIO=admin@... TB_CLAVE_ARCHIVO=/ruta \\
        python3 puente_real.py [--host ansible@homelab-01] [--dispositivo panol/LAB01] [--horas 24]

Cada 2 s le pide a la base del pañol (Postgres en homelab-01, por SSH, SOLO
SELECT) lo que entró desde la última vuelta y lo publica como telemetría del
dispositivo, con la hora real de cada evento. Traduce las tablas al contrato
del README (sección 2). Al arrancar carga las últimas --horas.

Es un puente de MUESTRA: no reemplaza al puente MQTT del pañol. No escribe
nada en el pañol. Publica por la API REST de ThingsBoard como administrador
del tenant (ThingsBoard tiene el transporte HTTP de dispositivos apagado).
"""
import argparse
import json
import os
import subprocess
import time
import urllib.parse

from tablero import TB, PERFIL

SQL = """
select json_build_object(
 'puerta', (select coalesce(json_agg(x order by x.id), '[]') from (
   select id, estado_reed as e, (extract(epoch from timestamp) * 1000)::bigint as ts
   from eventos_puerta where id > {puerta} and timestamp > now() - interval '{horas} hours') x),
 'pir', (select coalesce(json_agg(x order by x.id), '[]') from (
   select id, (extract(epoch from timestamp) * 1000)::bigint as ts
   from eventos_pir where id > {pir} and timestamp > now() - interval '{horas} hours') x),
 'armario', (select coalesce(json_agg(x order by x.id), '[]') from (
   select id, armario_id as n, (extract(epoch from timestamp) * 1000)::bigint as ts
   from eventos_armario where id > {armario} and timestamp > now() - interval '{horas} hours') x),
 'acceso', (select coalesce(json_agg(x order by x.id), '[]') from (
   select a.id, a.resultado as r, coalesce(u.nombre || ' ' || u.apellido, a.uid_hex) as p,
          (extract(epoch from a.timestamp) * 1000)::bigint as ts
   from eventos_acceso a
   left join credenciales c on c.uid_hex = a.uid_hex and c.activa
   left join usuarios u on u.id = c.usuario_id
   where a.id > {acceso} and a.timestamp > now() - interval '{horas} hours') x),
 'alarma', (select coalesce(json_agg(x order by x.id), '[]') from (
   select id, codigo as c, (extract(epoch from timestamp) * 1000)::bigint as ts
   from alarmas where id > {alarma} and timestamp > now() - interval '{horas} hours') x),
 'sesion', (select coalesce(json_agg(x order by x.id), '[]') from (
   select s.id, s.estado, s.motivo_cierre as m, coalesce(u.nombre || ' ' || u.apellido, s.uid_hex) as p,
          coalesce(u.rol, '') as rol,
          (extract(epoch from s.hora_inicio) * 1000)::bigint as ini,
          (extract(epoch from s.hora_fin) * 1000)::bigint as fin
   from sesiones s left join usuarios u on u.id = s.usuario_id
   where s.hora_inicio > now() - interval '{horas} hours' or s.estado = 'EN_CURSO') x),
 'nodo', (select json_agg(x) from (
   select id, extract(epoch from now() - ultimo_heartbeat)::int as hace, rssi, modo_degradado as deg
   from nodos) x)
);
"""


class Base:
    """psql dentro del contenedor del pañol, por una conexión SSH reutilizada."""

    def __init__(self, host):
        ctl = os.path.expanduser("~/.ssh/panol-puente-%C")
        self.cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ControlMaster=auto", "-o", f"ControlPath={ctl}",
                    "-o", "ControlPersist=10m", host,
                    "sudo docker exec -i panol-postgres psql -U panol -d panol -At -v ON_ERROR_STOP=1"]

    def consultar(self, sql):
        r = subprocess.run(self.cmd, input=sql, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:300])
        return json.loads(r.stdout)


def dispositivo(tb, nombre):
    ds = tb.req("GET", "/api/tenant/devices?pageSize=10&page=0&textSearch=" + urllib.parse.quote(nombre))["data"]
    d = next((x for x in ds if x["name"] == nombre), None)
    if d is None:
        perfiles = tb.req("GET", "/api/deviceProfiles?pageSize=100&page=0&textSearch=" + PERFIL)["data"]
        perfil = next((p for p in perfiles if p["name"] == PERFIL), None)
        cuerpo = {"name": nombre, "label": "Nodo del pañol (datos reales)"}
        if perfil:
            cuerpo["deviceProfileId"] = perfil["id"]
        d = tb.req("POST", "/api/device", cuerpo)
        print("dispositivo creado:", nombre)
    return d["id"]["id"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="ansible@homelab-01")
    ap.add_argument("--dispositivo", default="panol/LAB01")
    ap.add_argument("--horas", type=int, default=24)
    args = ap.parse_args()
    clave = open(os.environ["TB_CLAVE_ARCHIVO"]).read().strip() if os.environ.get("TB_CLAVE_ARCHIVO") \
        else os.environ.get("TB_CLAVE", "")
    base_tb = os.environ.get("TB_URL", "http://127.0.0.1:18080")
    tb = TB(base_tb, os.environ["TB_USUARIO"], clave)
    did = dispositivo(tb, args.dispositivo)
    url = f"/api/plugins/telemetry/DEVICE/{did}/timeseries/ANY"
    db = Base(args.host)

    ultimo = dict.fromkeys(["puerta", "pir", "armario", "acceso", "alarma"], 0)
    sesiones = {}            # id -> estado ya publicado ("EN_CURSO" / "CERRADA")
    limpiar = []             # (cuando, clave) alarmas a dar por resueltas
    abiertos = {}            # armario -> ts de apertura (para cerrarlo en el tablero)
    login = time.time()
    print("leyendo la base del pañol en", args.host)
    while True:
        lote = []
        try:
            d = db.consultar(SQL.format(horas=args.horas, **ultimo))
        except Exception as e:  # la red o el server: reintentar sin morir
            print("no pude leer la base:", e)
            time.sleep(5)
            continue
        for x in d["puerta"]:
            lote.append({"ts": x["ts"], "values": {"puerta": 1 if x["e"] == "ABIERTO" else 0}})
        for x in d["pir"]:
            lote.append({"ts": x["ts"], "values": {"pir": 1, "pir_evento": 1}})
        for x in d["armario"]:
            lote.append({"ts": x["ts"], "values": {f"armario{x['n']}": 1}})
            abiertos[x["n"]] = x["ts"]
        for x in d["acceso"]:
            r = x["r"]
            lote.append({"ts": x["ts"], "values": {"acceso": r, "acceso_usuario": x["p"],
                                                   "acceso_" + r.lower(): 1}})
        for x in d["alarma"]:
            clave_al = "alarma_" + x["c"].lower()
            lote.append({"ts": x["ts"], "values": {"alarma": x["c"], "alarma_evento": 1, clave_al: 1}})
            limpiar.append((x["ts"] / 1000 + 60, clave_al))
        for s in d["sesion"]:
            previo = sesiones.get(s["id"])
            if previo is None:
                lote.append({"ts": s["ini"], "values": {"sesion": 1, "sesion_nueva": 1, "sesion_usuario": s["p"],
                                                        "sesion_rol": s["rol"].capitalize(),
                                                        "sesion_inicio": s["ini"]}})
                sesiones[s["id"]] = "EN_CURSO"
            if s["fin"] and sesiones.get(s["id"]) != "CERRADA":
                lote.append({"ts": s["fin"], "values": {"sesion": 0, "fin_sesion": s["m"] or ""}})
                sesiones[s["id"]] = "CERRADA"
        for k in ultimo:
            if d[k]:
                ultimo[k] = d[k][-1]["id"]
        ahora = time.time()
        # Alarmas: la base no registra cuándo se resuelven; se dan por
        # resueltas en el tablero al minuto. Armarios: se marcan cerrados a los 20 s.
        for cuando, clave_al in [x for x in limpiar if x[0] <= ahora]:
            lote.append({"ts": int(ahora * 1000), "values": {clave_al: 0, "alarma": "OK"}})
            limpiar.remove((cuando, clave_al))
        for n, ts in list(abiertos.items()):
            if ahora - ts / 1000 > 20:
                lote.append({"ts": int(ahora * 1000), "values": {f"armario{n}": 0}})
                del abiertos[n]
        for n in d["nodo"] or []:
            lote.append({"ts": int(ahora * 1000), "values": {
                "nodo_en_linea": 1 if n["hace"] is not None and n["hace"] < 150 else 0,
                "rssi": n["rssi"], "modo_degradado": 1 if n["deg"] else 0}})
        if lote:
            lote.sort(key=lambda x: x["ts"])
            for i in range(0, len(lote), 500):
                tb.req("POST", url, lote[i:i + 500])
            eventos = sum(1 for x in lote if "nodo_en_linea" not in x["values"])
            if eventos:
                print(time.strftime("%H:%M:%S"), f"{eventos} eventos publicados")
        if time.time() - login > 1800:      # el token de ThingsBoard vence: renovar
            tb = TB(base_tb, os.environ["TB_USUARIO"], clave)
            login = time.time()
        time.sleep(2)


if __name__ == "__main__":
    main()
