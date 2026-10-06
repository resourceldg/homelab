#!/usr/bin/env python3
"""Sincroniza el Grafana del aula con el roster: una ORGANIZACIÓN por equipo.

Por qué organizaciones y no carpetas: Grafana OSS no tiene permisos por fuente de
datos. Con todo en una sola organización, cualquier alumno podía consultar la
fuente de otro equipo (o la general) aunque no viera su carpeta. Una organización
es un Grafana aparte dentro del mismo Grafana: lo que no está en la tuya, no
existe para vos. Lo comprobamos el 2026-10-05.

Qué deja armado (idempotente, se puede correr las veces que haga falta):
- Org 1 → "Aula — operador": tablero general y fuente "Aula (todos)", solo el
  operador (las dos van por provisioning, no por acá).
- Org "equipo-NN" por equipo: su fuente "MQTT — equipo-NN" (filtrada y
  PREDETERMINADA: un panel nuevo ya arranca con ella), su tablero inicial, y sus
  integrantes como Editor. El operador es Admin de todas (la crea él).
- Alumnos fuera de la org 1, y con su equipo como org de entrada.
- Migración desde el diseño anterior (carpetas en la org 1): copia el tablero del
  equipo TAL CUAL ESTÉ (con lo que hayan editado) y recién después borra la
  carpeta y el equipo de Grafana viejos.

Lo corre Ansible (rol aula_iot) con la configuración en JSON por stdin. Imprime
un JSON con la lista de cambios; si está vacía, no cambió nada.
"""
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request


class Grafana:
    def __init__(self, api, usuario, clave):
        self.api = api.rstrip("/")
        cred = f"{usuario}:{clave}".encode()
        import base64
        self.auth = "Basic " + base64.b64encode(cred).decode()

    def pedir(self, metodo, ruta, cuerpo=None, org=None, ok=(200,)):
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(self.api + ruta, data=datos, method=metodo)
        req.add_header("Authorization", self.auth)
        req.add_header("Content-Type", "application/json")
        if org is not None:
            req.add_header("X-Grafana-Org-Id", str(org))
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                texto = r.read().decode() or "null"
                return r.status, json.loads(texto)
        except urllib.error.HTTPError as e:
            texto = e.read().decode()
            if e.code in ok:
                return e.code, (json.loads(texto) if texto.startswith(("{", "[")) else texto)
            raise SystemExit(f"Grafana {metodo} {ruta} → {e.code}: {texto[:300]}")


def q(texto):
    return urllib.parse.quote(texto, safe="")


def datasource(equipo, vm_url):
    return {
        "name": f"MQTT — {equipo}",
        "uid": f"mqtt-{equipo}",
        "type": "prometheus",
        "access": "proxy",
        "url": vm_url,
        "isDefault": True,
        # VictoriaMetrics filtra SIEMPRE por equipo: aunque alguien escriba otra
        # etiqueta en la consulta, solo vuelven datos de este equipo.
        "jsonData": {"timeInterval": "10s", "customQueryParameters": f"extra_label=equipo={equipo}"},
    }


def roster(cfg):
    """[{nombre, miembros: [{login, nombre}]}] desde classroom_teams + sso_users."""
    nombres = cfg.get("nombres", {})
    return [{"nombre": t["name"],
             "miembros": [{"login": m, "nombre": nombres.get(m, m)} for m in t.get("members", [])]}
            for t in cfg["equipos"]]


def sincronizar(cfg, g):
    cambios = []
    equipos = roster(cfg)
    operador = cfg["operador"]
    org_operador = 1

    # --- org 1: la del operador ------------------------------------------------
    _, org1 = g.pedir("GET", f"/api/orgs/{org_operador}")
    if org1["name"] != cfg["nombre_org_operador"]:
        g.pedir("PUT", f"/api/orgs/{org_operador}", {"name": cfg["nombre_org_operador"]})
        cambios.append(f"org 1 renombrada a «{cfg['nombre_org_operador']}»")

    # --- usuarios (entran por Authelia; la clave de acá nunca se usa) ------------
    ids = {}
    for equipo in equipos:
        for m in equipo["miembros"]:
            st, u = g.pedir("GET", f"/api/users/lookup?loginOrEmail={q(m['login'])}", ok=(200, 404))
            if st == 404:
                _, u = g.pedir("POST", "/api/admin/users", {
                    "login": m["login"], "name": m["nombre"], "password": secrets.token_urlsafe(24)})
                cambios.append(f"usuario {m['login']} creado")
                ids[m["login"]] = u["id"]
            else:
                ids[m["login"]] = u["id"]

    for equipo in equipos:
        nombre = equipo["nombre"]
        logins = {m["login"] for m in equipo["miembros"]}

        # --- la organización del equipo ------------------------------------------
        st, org = g.pedir("GET", f"/api/orgs/name/{q(nombre)}", ok=(200, 404))
        if st == 404:
            _, creada = g.pedir("POST", "/api/orgs", {"name": nombre})
            org_id = creada["orgId"]
            cambios.append(f"org {nombre} creada")
        else:
            org_id = org["id"]

        # --- su fuente de datos (única, filtrada y predeterminada) -----------------
        ds = datasource(nombre, cfg["vm_url"])
        st, actual = g.pedir("GET", f"/api/datasources/uid/{ds['uid']}", org=org_id, ok=(200, 404))
        if st == 404:
            g.pedir("POST", "/api/datasources", ds, org=org_id)
            cambios.append(f"{nombre}: fuente de datos creada")
        elif any(actual.get(k) != v for k, v in ds.items() if k != "jsonData") or \
                any(actual.get("jsonData", {}).get(k) != v for k, v in ds["jsonData"].items()):
            g.pedir("PUT", f"/api/datasources/uid/{ds['uid']}", {**ds, "id": actual["id"]}, org=org_id)
            cambios.append(f"{nombre}: fuente de datos corregida")

        # --- integrantes: Editor; fuera quien ya no está en el roster ------------
        _, miembros = g.pedir("GET", f"/api/orgs/{org_id}/users")
        presentes = {m["login"]: m for m in miembros}
        for login in sorted(logins):
            if login not in presentes:
                g.pedir("POST", f"/api/orgs/{org_id}/users", {"loginOrEmail": login, "role": "Editor"})
                cambios.append(f"{nombre}: {login} agregado (Editor)")
            elif presentes[login]["role"] != "Editor":
                g.pedir("PATCH", f"/api/orgs/{org_id}/users/{ids[login]}", {"role": "Editor"})
                cambios.append(f"{nombre}: {login} pasa a Editor")
        for login, m in presentes.items():
            if login not in logins and login != operador:
                g.pedir("DELETE", f"/api/orgs/{org_id}/users/{m['userId']}")
                cambios.append(f"{nombre}: {login} quitado (ya no está en el equipo)")

        # --- tablero inicial (y migración desde la carpeta vieja de la org 1) ------
        uid = f"{nombre}-mqtt"
        st, _ = g.pedir("GET", f"/api/dashboards/uid/{uid}", org=org_id, ok=(200, 404))
        st_viejo, viejo = g.pedir("GET", f"/api/dashboards/uid/{uid}", org=org_operador, ok=(200, 404))
        if st == 404:
            if st_viejo == 200:
                tablero = {k: v for k, v in viejo["dashboard"].items() if k not in ("id", "version")}
                origen = "copiado de la org del operador (con sus cambios)"
            else:
                plantilla = cfg["tablero_inicial"]
                if not isinstance(plantilla, str):  # Ansible a veces ya lo pasa como objeto
                    plantilla = json.dumps(plantilla, ensure_ascii=False)
                tablero = json.loads(plantilla.replace("__EQUIPO__", nombre))["dashboard"]
                origen = "creado"
            g.pedir("POST", "/api/dashboards/db",
                    {"dashboard": tablero, "overwrite": False, "message": "Ansible: tablero inicial"}, org=org_id)
            cambios.append(f"{nombre}: tablero {origen}")

        # La carpeta y el equipo viejos (diseño anterior) se van recién cuando el
        # tablero ya está a salvo en la org del equipo.
        st, _ = g.pedir("GET", f"/api/folders/{q(nombre)}", org=org_operador, ok=(200, 404))
        if st == 200:
            g.pedir("DELETE", f"/api/folders/{q(nombre)}", org=org_operador)
            cambios.append(f"{nombre}: carpeta vieja borrada de la org del operador")
        _, equipos_viejos = g.pedir("GET", f"/api/teams/search?name={q(nombre)}", org=org_operador)
        for t in equipos_viejos.get("teams", []):
            if t["name"] == nombre:
                g.pedir("DELETE", f"/api/teams/{t['id']}", org=org_operador)
                cambios.append(f"{nombre}: equipo de Grafana viejo borrado")

        # Entra directo a la org de su equipo.
        for login in sorted(logins):
            g.pedir("POST", f"/api/users/{ids[login]}/using/{org_id}")

    # --- alumnos fuera de la org del operador (ya están en la de su equipo) -------
    alumnos = set(ids)
    _, en_org1 = g.pedir("GET", f"/api/orgs/{org_operador}/users")
    for m in en_org1:
        if m["login"] in alumnos:
            g.pedir("DELETE", f"/api/orgs/{org_operador}/users/{m['userId']}")
            cambios.append(f"{m['login']} quitado de la org del operador")

    return cambios


def main():
    cfg = json.load(sys.stdin)
    g = Grafana(cfg["api"], cfg["operador"], cfg["clave_operador"])
    cambios = sincronizar(cfg, g)
    print(json.dumps({"changed": bool(cambios), "cambios": cambios}, ensure_ascii=False))


if __name__ == "__main__":
    main()
