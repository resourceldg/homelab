#!/usr/bin/env python3
"""Aprovisiona ThingsBoard a partir de la lista de proyectos — idempotente.

    sudo python3 tb-provision.py --config /etc/thingsboard/tableros.json

Lo corre el rol Ansible `thingsboard` después de levantar el stack; también se
puede correr a mano (no rompe nada si se repite). Solo usa la biblioteca
estándar: corre en el host sin instalar nada.

Qué hace, en orden:
  1. Sysadmin: cambia la clave por defecto ("sysadmin") por la del secreto.
  2. Crea el tenant y su administrador (o los deja como están).
  3. Fija límites del perfil de tenant (WebSocket de espectadores públicos).
  4. Crea el gateway del puente con el token del secreto.
  5. Crea/actualiza los dashboards GESTIONADOS (uno por proyecto + generales).
     Un dashboard hecho a mano en la interfaz no se toca nunca.
  6. Reconcilia lo público: dashboards y dispositivos marcados públicos se
     asignan al cliente "Public"; lo que ya no figura como público se quita.
     Así nada queda expuesto "porque alguna vez se publicó".
  7. Escribe la portada pública (index.html) con los tableros publicados.

Los dashboards se arman con la configuración por defecto de cada widget, que
se lee de la propia instancia: no se copia JSON a mano de una versión vieja.
"""
import argparse
import html
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MARCA = "gestionado por tb-provision"


class TB:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.token = None

    def _req(self, metodo, ruta, cuerpo=None, auth=True, esperado=(200,)):
        datos = None if cuerpo is None else json.dumps(cuerpo).encode()
        req = urllib.request.Request(self.base + ruta, data=datos, method=metodo)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/plain, */*")
        if auth and self.token:
            req.add_header("X-Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                texto = r.read().decode()
                if not texto:
                    return None
                try:
                    return json.loads(texto)
                except ValueError:
                    return texto  # p. ej. el link de activación viene como texto
        except urllib.error.HTTPError as e:
            if e.code in esperado:
                return None
            detalle = e.read().decode(errors="replace")[:300]
            raise RuntimeError(f"{metodo} {ruta} -> {e.code}: {detalle}") from None

    def get(self, ruta, **kw):
        return self._req("GET", ruta, **kw)

    def post(self, ruta, cuerpo=None, **kw):
        return self._req("POST", ruta, cuerpo, **kw)

    def delete(self, ruta, **kw):
        return self._req("DELETE", ruta, **kw)

    def login(self, usuario, clave):
        try:
            r = self.post("/api/auth/login", {"username": usuario, "password": clave}, auth=False)
        except RuntimeError:
            return False
        self.token = r["token"]
        return True

    def paginas(self, ruta, **params):
        """Todas las páginas de un listado paginado de ThingsBoard."""
        pagina = 0
        while True:
            q = dict(params, pageSize=100, page=pagina)
            r = self.get(f"{ruta}?{urllib.parse.urlencode(q)}")
            yield from r["data"]
            if not r.get("hasNext"):
                return
            pagina += 1


def leer(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read().strip()


def esperar(tb, intentos=60):
    for _ in range(intentos):
        try:
            tb.get("/api/noauth/oauth2Clients", auth=False, esperado=(200, 404, 405))
            return
        except Exception:
            time.sleep(5)
    sys.exit("ThingsBoard no responde")


# --- 1-2. Sysadmin, tenant y administrador ------------------------------------------

def sysadmin(tb, clave):
    usuario = "sysadmin@thingsboard.org"
    if tb.login(usuario, clave):
        return
    # Primera vez: todavía tiene la clave de fábrica. Se cambia acá y no vuelve.
    if not tb.login(usuario, "sysadmin"):
        sys.exit("No entra ni con la clave del secreto ni con la de fábrica")
    tb.post("/api/auth/changePassword", {"currentPassword": "sysadmin", "newPassword": clave})
    print("sysadmin: clave de fábrica reemplazada")
    if not tb.login(usuario, clave):
        sys.exit("Cambié la clave del sysadmin y no entra: revisar a mano")


def tenant(tb, titulo):
    for t in tb.paginas("/api/tenants", textSearch=titulo):
        if t["title"] == titulo:
            return t
    print(f"tenant: creo '{titulo}'")
    return tb.post("/api/tenant", {"title": titulo})


def admin_tenant(tb, ten, email, clave):
    tid = ten["id"]["id"]
    u = next((x for x in tb.paginas(f"/api/tenant/{tid}/users") if x["email"] == email), None)
    if u is None:
        print(f"admin: creo {email}")
        u = tb.post("/api/user?sendActivationMail=false", {
            "email": email, "authority": "TENANT_ADMIN", "firstName": "Admin",
            "lastName": "Tableros", "tenantId": {"id": tid, "entityType": "TENANT"},
        })
    elif TB(tb.base).login(email, clave):
        return
    # Creado pero sin activar (p. ej. una corrida que se cortó): se activa con
    # la clave del secreto. Si ya estaba activo con OTRA clave, no hay link y
    # se avisa: no se pisa una clave que alguien cambió a mano.
    try:
        link = tb.get(f"/api/user/{u['id']['id']}/activationLink")
    except RuntimeError:
        sys.exit(f"{email} existe y no entra con la clave del secreto: revisar a mano")
    if isinstance(link, dict):
        link = link.get("value", "")
    token = urllib.parse.parse_qs(urllib.parse.urlparse(str(link)).query)["activateToken"][0]
    tb.post("/api/noauth/activate?sendActivationMail=false",
            {"activateToken": token, "password": clave}, auth=False)
    print(f"admin: {email} activado")


# --- 3. Límites del perfil de tenant --------------------------------------------------

def limites(tb, ten, lim):
    """Los espectadores públicos comparten UNA identidad ("Public"): el tope de
    sesiones por usuario público es, en la práctica, el tope de espectadores
    simultáneos. Se fija explícito para que no lo decida el default."""
    pid = ten["tenantProfileId"]["id"]
    perfil = tb.get(f"/api/tenantProfile/{pid}")
    conf = perfil["profileData"]["configuration"]
    cambios = {k: v for k, v in lim.items() if conf.get(k) != v}
    if cambios:
        conf.update(cambios)
        tb.post("/api/tenantProfile", perfil)
        print(f"perfil de tenant: {cambios}")


# --- 4. Gateway del puente ------------------------------------------------------------

def gateway(tb, nombre, token):
    disp = tb.get(f"/api/tenant/devices?{urllib.parse.urlencode({'deviceName': nombre})}", esperado=(404,))
    if disp is None:
        print(f"gateway: creo {nombre}")
        disp = tb.post("/api/device", {"name": nombre, "additionalInfo": {"gateway": True}})
    cred = tb.get(f"/api/device/{disp['id']['id']}/credentials")
    if cred["credentialsType"] != "ACCESS_TOKEN" or cred["credentialsId"] != token:
        cred["credentialsType"] = "ACCESS_TOKEN"
        cred["credentialsId"] = token
        tb.post("/api/device/credentials", cred)
        print("gateway: token actualizado")
    return disp


# --- 5. Dashboards --------------------------------------------------------------------

def widget_base(tb, fqn):
    """Tipo de widget + su configuración por defecto, leídos de la instancia."""
    w = tb.get(f"/api/widgetType?{urllib.parse.urlencode({'fqn': fqn})}")
    desc = w["descriptor"]
    conf = json.loads(desc.get("defaultConfig") or "{}")
    return w, desc, conf


COLORES = ["#2196f3", "#4caf50", "#f44336", "#ff9800", "#9c27b0", "#00bcd4",
           "#795548", "#607d8b", "#e91e63", "#cddc39", "#3f51b5", "#009688"]


def un_widget(tb, wid, fqn, titulo, alias_id, claves, cols, filas, ajustes=None,
              acciones=None, etiqueta="${entityName}", columna=0, fila=0):
    _, desc, conf = widget_base(tb, fqn)
    conf["title"] = titulo
    conf["showTitle"] = True
    conf["useDashboardTimewindow"] = True
    conf["datasources"] = [{
        "type": "entity",
        "entityAliasId": alias_id,
        "dataKeys": [{"name": k, "type": "timeseries",
                      "label": etiqueta.replace("{clave}", k),
                      "color": COLORES[i % len(COLORES)], "settings": {}}
                     for i, k in enumerate(claves)],
    }]
    if ajustes:
        conf.setdefault("settings", {}).update(ajustes)
    if acciones:
        conf["actions"] = acciones
    widget = {"typeFullFqn": fqn, "type": desc["type"], "sizeX": cols, "sizeY": filas,
              "config": conf, "id": wid}
    return widget, {"sizeX": cols, "sizeY": filas, "row": fila, "col": columna}


def claves_de(tb, tipos):
    """Magnitudes que ya publicó algún dispositivo de esos proyectos."""
    claves = set()
    for tipo in tipos:
        for d in tb.paginas("/api/tenant/devices", type=tipo):
            ks = tb.get(f"/api/plugins/telemetry/DEVICE/{d['id']['id']}/keys/timeseries") or []
            claves.update(ks)
    return sorted(claves)[:12] or ["valor"]


def armar_dashboard(tb, titulo, tipos, fqn_tabla, fqn_serie, publico):
    """Estado "default": tabla con el último valor de cada dispositivo + un
    gráfico por magnitud de cada proyecto (cada dispositivo es una serie).
    Una magnitud por gráfico: si no, la presión (~1013) aplasta a la
    temperatura (~20) en la misma escala. Y un filtro por proyecto: así un
    gráfico solo lista placas que miden esa magnitud.

    Dashboards de UN proyecto: un clic en una fila abre el estado
    "dispositivo" (los mismos gráficos, solo de esa placa)."""
    alias = {"a-todos": {"id": "a-todos", "alias": "Dispositivos",
                         "filter": {"type": "deviceType", "deviceTypes": tipos,
                                    "deviceNameFilter": "", "resolveMultiple": True}}}
    for tipo in tipos:
        alias[f"a-{tipo}"] = {"id": f"a-{tipo}", "alias": tipo,
                              "filter": {"type": "deviceType", "deviceTypes": [tipo],
                                         "deviceNameFilter": "", "resolveMultiple": True}}
    por_dispositivo = len(tipos) == 1
    if por_dispositivo:
        alias["a-uno"] = {"id": "a-uno", "alias": "Dispositivo elegido",
                          "filter": {"type": "stateEntity", "resolveMultiple": False,
                                     "stateEntityParamName": None, "defaultStateEntity": None}}
    claves = {tipo: claves_de(tb, [tipo]) for tipo in tipos}
    todas = sorted({k for ks in claves.values() for k in ks})[:20]
    widgets = {}

    def graficos(layout, fila, alias_de, prefijo):
        i = 0
        for tipo in tipos:
            for k in claves[tipo]:
                wid = f"w-{prefijo}-{tipo}-{k}"
                nombre = k if len(tipos) == 1 else f"{tipo} · {k}"
                w, pos = un_widget(tb, wid, fqn_serie, nombre, alias_de(tipo), [k], 12, 6,
                                   columna=(i % 2) * 12, fila=fila + (i // 2) * 6)
                widgets[wid] = w
                layout[wid] = pos
                i += 1

    principal = {}
    accion = None
    if por_dispositivo:
        accion = {"rowClick": [{
            "id": "ver-dispositivo", "name": "Ver dispositivo", "icon": "insert_chart",
            "type": "openDashboardState", "targetDashboardStateId": "dispositivo",
            "setEntityId": True, "stateEntityParamName": None,
            "openInSeparateDialog": False, "openRightLayout": False}]}
    w, pos = un_widget(
        tb, "w-tabla", fqn_tabla, "Últimos valores", "a-todos", todas, 24, 7,
        ajustes={"entitiesTitle": "Últimos valores", "displayEntityName": True,
                 "entityNameColumnTitle": "Dispositivo", "displayEntityLabel": False,
                 "enableSelectColumnDisplay": False, "defaultSortOrder": "entityName"},
        acciones=accion, etiqueta="{clave}")
    widgets["w-tabla"] = w
    principal["w-tabla"] = pos
    graficos(principal, 7, lambda tipo: f"a-{tipo}", "todos")

    grilla = {"columns": 24, "margin": 10, "backgroundColor": "#eeeeee"}
    estados = {"default": {"name": titulo, "root": True,
                           "layouts": {"main": {"widgets": principal, "gridSettings": grilla}}}}
    if por_dispositivo:
        uno = {}
        graficos(uno, 0, lambda tipo: "a-uno", "uno")
        estados["dispositivo"] = {"name": "${entityName}", "root": False,
                                  "layouts": {"main": {"widgets": uno, "gridSettings": grilla}}}
    return {
        "title": titulo,
        "configuration": {
            "description": MARCA,
            "entityAliases": alias,
            "widgets": widgets,
            "states": estados,
            "timewindow": {"selectedTab": 0,
                           "realtime": {"realtimeType": 0, "timewindowMs": 3600000, "interval": 10000},
                           "aggregation": {"type": "AVG", "limit": 2000}},
            "settings": {
                "stateControllerId": "entity",
                "showTitle": True, "showDashboardsSelect": False,
                "showEntitiesSelect": False, "showDashboardTimewindow": not publico,
                "showDashboardExport": not publico, "showDashboardLogo": False,
                "toolbarAlwaysOpen": False, "hideToolbar": False,
            },
        },
    }


def dashboards(tb, cfg):
    existentes = {d["title"]: d for d in tb.paginas("/api/tenant/dashboards")}
    fqn_tabla = cfg["widgets"]["tabla"]
    fqn_serie = cfg["widgets"]["serie"]
    resultado = []
    for dash in cfg["dashboards"]:
        titulo = dash["titulo"]
        nuevo = armar_dashboard(tb, titulo, dash["tipos"], fqn_tabla, fqn_serie, dash["publico"])
        actual = existentes.get(titulo)
        if actual is None:
            d = tb.post("/api/dashboard", nuevo)
            print(f"dashboard: creo '{titulo}'")
        else:
            d = tb.get(f"/api/dashboard/{actual['id']['id']}")
            if d["configuration"].get("description") != MARCA:
                print(f"dashboard: '{titulo}' existe y lo hizo una persona: no lo toco")
                resultado.append((dash, d))
                continue
            # Se rehace solo si cambió algo (proyectos o magnitudes nuevas).
            if json.dumps(d["configuration"], sort_keys=True) != json.dumps(nuevo["configuration"], sort_keys=True):
                d["configuration"] = nuevo["configuration"]
                d = tb.post("/api/dashboard", d)
                print(f"dashboard: actualizo '{titulo}'")
        resultado.append((dash, d))
    return resultado


# --- 6. Reconciliación de lo público --------------------------------------------------

def cliente_publico(tb):
    for c in tb.paginas("/api/customers"):
        if (c.get("additionalInfo") or {}).get("isPublic"):
            return c["id"]["id"]
    return None


def publicar(tb, dashes, cfg):
    tipos_publicos = set()
    for dash, d in dashes:
        did = d["id"]["id"]
        es_publico = any((c.get("public") for c in d.get("assignedCustomers") or []))
        if dash["publico"] and not es_publico:
            tb.post(f"/api/customer/public/dashboard/{did}")
            print(f"público: publico '{dash['titulo']}'")
        elif not dash["publico"] and es_publico:
            tb.delete(f"/api/customer/public/dashboard/{did}")
            print(f"público: despublico '{dash['titulo']}'")
        if dash["publico"]:
            tipos_publicos.update(dash["tipos"])

    pub = cliente_publico(tb)
    if pub is None:  # se crea solo al publicar el primer dashboard
        return None
    for d in tb.paginas("/api/tenant/devices"):
        if (d.get("additionalInfo") or {}).get("gateway"):
            continue  # el gateway del puente NUNCA es público
        asignado = d.get("customerId", {}).get("id") == pub
        quiere = d["type"] in tipos_publicos
        if quiere and not asignado:
            tb.post(f"/api/customer/public/device/{d['id']['id']}")
            print(f"público: dispositivo {d['name']}")
        elif asignado and not quiere:
            tb.delete(f"/api/customer/device/{d['id']['id']}")
            print(f"público: retiro dispositivo {d['name']}")
    return pub


# --- 7. Portada -----------------------------------------------------------------------

def portada(dashes, pub, cfg, destino):
    base = cfg["base_publica"].rstrip("/")
    items = []
    for dash, d in dashes:
        if dash["publico"] and pub:
            url = f"{base}/dashboard/{d['id']['id']}?publicId={pub}"
            items.append(f'<li><a href="{html.escape(url)}">{html.escape(dash["titulo"])}</a></li>')
    cuerpo = "\n".join(items) or "<li>Todavía no hay tableros publicados.</li>"
    pagina = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tableros IoT — {html.escape(cfg['institucion'])}</title>
<style>
 :root {{ color-scheme: light dark; --fg:#1b1f24; --bg:#f6f7f9; --acc:#0b62a4; }}
 @media (prefers-color-scheme: dark) {{ :root {{ --fg:#e6e8eb; --bg:#14171a; --acc:#6cb6ff; }} }}
 body {{ font-family: system-ui, sans-serif; margin: 0; padding: 24px 16px; background: var(--bg); color: var(--fg); }}
 main {{ max-width: 720px; margin: 0 auto; }}
 h1 {{ font-size: 1.6rem; margin: 0 0 4px; }}
 p {{ opacity: .8; margin: 0 0 24px; }}
 ul {{ list-style: none; padding: 0; margin: 0; }}
 li a {{ display: block; padding: 14px 16px; margin-bottom: 10px; border-radius: 8px;
        background: color-mix(in srgb, var(--acc) 12%, transparent); color: var(--acc);
        text-decoration: none; font-weight: 600; }}
 li a:hover {{ background: color-mix(in srgb, var(--acc) 22%, transparent); }}
</style></head>
<body><main>
<h1>Tableros IoT</h1>
<p>{html.escape(cfg['institucion'])} — proyectos de los equipos, en vivo. Solo lectura.</p>
<ul>
{cuerpo}
</ul>
</main></body></html>
"""
    os.makedirs(destino, exist_ok=True)
    tmp = os.path.join(destino, ".index.html.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(pagina)
    os.chmod(tmp, 0o644)
    os.replace(tmp, os.path.join(destino, "index.html"))
    # Lista legible por máquinas (verificación y monitores).
    with open(os.path.join(destino, ".tableros.json"), "w", encoding="utf-8") as f:
        json.dump([{"titulo": dash["titulo"], "id": d["id"]["id"], "publico": dash["publico"],
                    "url": f"{base}/dashboard/{d['id']['id']}?publicId={pub}" if dash["publico"] and pub else None}
                   for dash, d in dashes], f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = json.load(open(args.config, encoding="utf-8"))
    sec = cfg["secretos"]

    tb = TB(cfg["url"])
    esperar(tb)
    sysadmin(tb, leer(sec["sysadmin"]))
    ten = tenant(tb, cfg["tenant"])
    admin_tenant(tb, ten, cfg["admin_email"], leer(sec["admin"]))
    limites(tb, ten, cfg["limites"])

    if not tb.login(cfg["admin_email"], leer(sec["admin"])):
        sys.exit("El administrador del tenant no entra")
    gateway(tb, cfg["gateway"], leer(sec["gateway_token"]))
    dashes = dashboards(tb, cfg)
    pub = publicar(tb, dashes, cfg)
    portada(dashes, pub, cfg, cfg["portada_dir"])
    print("listo")


if __name__ == "__main__":
    main()
