#!/usr/bin/env python3
"""Genera (y opcionalmente crea) los tableros del proyecto Sony IR + relés.

    TB_URL=http://127.0.0.1:18080 TB_USUARIO=dardo@isft238.local TB_CLAVE_ARCHIVO=/ruta \\
        python3 tablero.py [--crear] [--alarmas] [--reemplazar]

- Sin opciones: arma los dos tableros y guarda el JSON en esta carpeta
  (tablero.json y tablero-exhibicion.json). No cambia nada en ThingsBoard.
- --crear: los crea en el tenant del usuario, SOLO si no existe uno con ese
  título. --reemplazar actualiza uno que este script haya creado antes (lleva
  la marca en la descripción); nunca toca un tablero hecho a mano.
- --alarmas: agrega al perfil de dispositivo "equipo-01" las dos reglas de
  alarma del proyecto (si no están) y, si falta, el nodo "Device Profile" al
  principio de la cadena raíz del tenant (ThingsBoard 4.3 no lo trae y sin él
  las reglas no se evalúan). Guarda una copia de la cadena antes de tocarla.

Las credenciales se leen de variables de entorno / un archivo: nunca van por
la línea de comandos ni al repositorio. Solo biblioteca estándar.

Todo se ata al dispositivo por NOMBRE ("equipo-01/sony_ir"): el tablero
funciona aunque el dispositivo todavía no exista (aparece cuando la placa
publique la primera vez).
"""
import argparse
import copy
import json
import os
import sys
import urllib.error
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
DISPOSITIVO = "equipo-01/sony_ir"   # el puente cambia "-" por "_" en los nombres
PERFIL = "equipo-01"
MARCA = "gestionado por proyectos/equipo-01-sony-ir/tablero.py"
TITULO = "Sony IR — Control de relés (equipo-01)"
TITULO_EXHIBICION = "Sony IR — Control de relés · Exhibición"

# Nombres de las teclas: copiados de nombre_tecla() en src/bin/main.rs.
TECLAS = {
    0x420D: "OFF", 0x4214: "ATT", 0x4246: "SOURCE", 0x4211: "SEL", 0x4247: "MODE",
    0x4233: "ARRIBA", 0x4235: "IZQ", 0x4234: "DER", 0x4232: "ABAJO", 0x4228: "DSLP",
    0x4223: "SCRL", 0x4200: "1", 0x4201: "2", 0x4202: "3", 0x4203: "4", 0x4204: "5",
    0x4205: "6", 0x4212: "MAS", 0x4213: "MENOS",
}
VERDE, GRIS, ROJO, AMBAR, AZUL = "#2E7D32", "#9E9E9E", "#C62828", "#EF6C00", "#305680"


class TB:
    def __init__(self, base, usuario, clave):
        self.base = base.rstrip("/")
        r = self.req("POST", "/api/auth/login", {"username": usuario, "password": clave}, auth=False)
        self.token = r["token"]

    def req(self, metodo, ruta, cuerpo=None, auth=True):
        datos = None if cuerpo is None else json.dumps(cuerpo).encode()
        r = urllib.request.Request(self.base + ruta, data=datos, method=metodo,
                                   headers={"Content-Type": "application/json", "Accept": "application/json"})
        if auth:
            r.add_header("X-Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(r, timeout=60) as x:
                t = x.read().decode()
                return json.loads(t) if t else None
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{metodo} {ruta} -> {e.code}: {e.read().decode()[:200]}") from None


# --- Piezas ------------------------------------------------------------------------

JS_TECLA = ("var n = " + json.dumps({str(k): v for k, v in TECLAS.items()}) + ";\n"
            "if (value === null || value === undefined || value === '') return '—';\n"
            "var k = String(Math.round(Number(value)));\n"
            "return n[k] || ('0x' + Number(value).toString(16).toUpperCase());")
JS_ONOFF = "if (value === null || value === undefined || value === '') return '—';\nreturn Number(value) === 1 ? 'ENCENDIDO' : 'APAGADO';"
JS_COLOR_ONOFF = (f"return (value === 'ENCENDIDO' || Number(value) === 1) ? '{VERDE}' : '{GRIS}';")
JS_ACTIVO = "return (value === true || value === 'true') ? 'CONECTADO' : 'SIN CONEXIÓN';"
JS_COLOR_ACTIVO = f"return (value === 'CONECTADO' || value === true || value === 'true') ? '{VERDE}' : '{ROJO}';"
JS_FECHA = ("if (!value) return 'sin datos';\nvar d = new Date(Number(value));\n"
            "return d.toLocaleDateString('es-AR') + ' ' + d.toLocaleTimeString('es-AR');")


class Armador:
    def __init__(self, tb):
        self.tb = tb
        self.defaults = {}
        self.widgets = {}
        self.layout = {}

    def base(self, fqn):
        if fqn not in self.defaults:
            w = self.tb.req("GET", "/api/widgetType?fqn=" + fqn)
            self.defaults[fqn] = (w["descriptor"]["type"], json.loads(w["descriptor"]["defaultConfig"] or "{}"))
        tipo, conf = self.defaults[fqn]
        return tipo, copy.deepcopy(conf)

    def poner(self, wid, fqn, titulo, claves, col, fila, ancho, alto, settings=None, conf=None,
              orden_movil=None, alto_movil=None):
        tipo, c = self.base(fqn)
        c["title"] = titulo
        c["showTitle"] = True
        c["datasources"] = [] if claves is None else [{
            "type": "entity", "entityAliasId": "a-sony", "filterId": None,
            "dataKeys": [dict({"type": "timeseries", "settings": {}, "color": AZUL}, **k) for k in claves],
        }]
        if settings:
            c.setdefault("settings", {}).update(settings)
        if conf:
            c.update(conf)
        c["mobileOrder"] = orden_movil if orden_movil is not None else len(self.widgets)
        if alto_movil:
            c["mobileHeight"] = alto_movil
        self.widgets[wid] = {"typeFullFqn": fqn, "type": tipo, "sizeX": ancho, "sizeY": alto,
                             "config": c, "id": wid}
        self.layout[wid] = {"sizeX": ancho, "sizeY": alto, "col": col, "row": fila}

    # Tarjeta de valor con texto y color calculados.
    def tarjeta(self, wid, titulo, clave, col, fila, ancho, alto, func, color, icono, unidad="",
                tipo_clave="timeseries", agregacion=None, ventana_ms=None, fecha=True):
        k = {"name": clave, "type": tipo_clave, "label": titulo,
             "usePostProcessing": func is not None, "postFuncBody": func}
        if agregacion:
            k["aggregationType"] = agregacion
        settings = {
            "layout": "horizontal" if agregacion else "square", "showLabel": True, "labelPosition": "top",
            "labelFont": {"family": "Roboto", "size": 15 if agregacion else 16, "sizeUnit": "px",
                          "style": "normal", "weight": "500"},
            "icon": icono, "showIcon": True, "showDate": fecha,
            "valueFont": {"family": "Roboto", "size": 26, "sizeUnit": "px", "style": "normal", "weight": "600"},
            "valueColor": {"type": "function" if color else "constant", "color": AZUL, "colorFunction": color or ""},
            "iconColor": {"type": "function" if color else "constant", "color": AZUL, "colorFunction": color or ""},
        }
        conf = {"units": unidad, "decimals": 0, "showTitle": False}
        if ventana_ms:
            conf["useDashboardTimewindow"] = False
            conf["displayTimewindow"] = False
            conf["timewindow"] = {"selectedTab": 0, "realtime": {"realtimeType": 0, "timewindowMs": ventana_ms,
                                                                 "interval": 60000},
                                  "aggregation": {"type": agregacion or "NONE", "limit": 50000}}
        self.poner(wid, "system.cards.value_card", titulo, [k], col, fila, ancho, alto, settings, conf)

    def estado_salida(self, wid, titulo, clave, col, fila):
        estados = [{"label": "Apagado", "value": 0, "sourceType": "constant", "sourceValue": 0},
                   {"label": "Encendido", "value": 1, "sourceType": "constant", "sourceValue": 1}]
        _, base = self.base("system.state_chart")
        ajustes_clave = copy.deepcopy(base["datasources"][0]["dataKeys"][0]["settings"])
        self.poner(wid, "system.state_chart", titulo,
                   [{"name": clave, "label": titulo, "color": VERDE, "settings": ajustes_clave}],
                   col, fila, 8, 5, settings={"states": estados, "showLegend": False},
                   conf={"useDashboardTimewindow": True})


def armar(tb, exhibicion=False):
    a = Armador(tb)
    f = 0
    # A. Cabecera -----------------------------------------------------------------------
    descripcion = (
        "### Sony IR — Control de relés\n"
        "ESP32 que recibe un **control remoto infrarrojo Sony (SIRC 15 bits)** y, con las teclas "
        "**1, 2 y 3**, alterna **dos relés y un relé de estado sólido**. "
        "Proyecto de **equipo-01** · ISFT 238.\n\n"
        f"Dispositivo: `{DISPOSITIVO}` · La placa publica por WiFi + MQTT (TLS) en el broker del aula.")
    a.poner("w-cab", "system.cards.markdown_card", "Proyecto", None, 0, f, 10, 4,
            settings={"markdownTextPattern": descripcion, "useMarkdownTextFunction": False,
                      "applyDefaultMarkdownStyle": True}, conf={"showTitle": False})
    a.tarjeta("w-enlace", "Conexión de la placa", "active", 10, f, 5, 4, JS_ACTIVO, JS_COLOR_ACTIVO, "wifi",
              tipo_clave="attribute", fecha=False)
    a.tarjeta("w-ultima", "Última comunicación", "lastActivityTime", 15, f, 5, 4, JS_FECHA, None, "schedule",
              tipo_clave="attribute", fecha=False)
    a.tarjeta("w-rssi", "Señal WiFi", "rssi", 20, f, 4, 4, None,
              f"return Number(value) >= -67 ? '{VERDE}' : (Number(value) >= -80 ? '{AMBAR}' : '{ROJO}');",
              "network_wifi", unidad="dBm")
    f += 4
    # B. Indicadores principales --------------------------------------------------------------
    a.tarjeta("w-r1", "Relé 1 · GPIO18", "rele1", 0, f, 6, 4, JS_ONOFF, JS_COLOR_ONOFF, "power")
    a.tarjeta("w-r2", "Relé 2 · GPIO23", "rele2", 6, f, 6, 4, JS_ONOFF, JS_COLOR_ONOFF, "power")
    a.tarjeta("w-ssr", "SSR · GPIO19", "ssr", 12, f, 6, 4, JS_ONOFF, JS_COLOR_ONOFF, "bolt")
    a.tarjeta("w-tecla", "Última tecla recibida", "tecla", 18, f, 6, 4, JS_TECLA, None, "settings_remote")
    f += 4
    dia = 24 * 3600 * 1000
    a.tarjeta("w-acc", "Accionamientos (24 h)", "accionamiento", 0, f, 6, 3, None, None, "toggle_on",
              agregacion="COUNT", ventana_ms=dia, fecha=False)
    a.tarjeta("w-puls", "Pulsaciones IR (24 h)", "tecla", 6, f, 6, 3, None, None, "touch_app",
              agregacion="COUNT", ventana_ms=dia, fecha=False)
    if not exhibicion:
        a.tarjeta("w-inv", "Tramas IR inválidas (24 h)", "trama_invalida", 12, f, 6, 3, None,
                  f"return Number(value) > 0 ? '{AMBAR}' : '{VERDE}';", "report",
                  agregacion="COUNT", ventana_ms=dia, fecha=False)
        a.tarjeta("w-rein", "Reinicios de la placa (24 h)", "reinicio", 18, f, 6, 3, None,
                  f"return Number(value) > 0 ? '{AMBAR}' : '{VERDE}';", "restart_alt",
                  agregacion="COUNT", ventana_ms=dia, fecha=False)
    f += 3
    # C. Tiempo real: una línea de estado por salida --------------------------------------------
    a.estado_salida("w-h1", "Relé 1", "rele1", 0, f)
    a.estado_salida("w-h2", "Relé 2", "rele2", 8, f)
    a.estado_salida("w-h3", "SSR", "ssr", 16, f)
    f += 5
    # D. Histórico: pulsaciones por hora ----------------------------------------------------------
    _, bar = a.base("system.bar_chart")
    leyenda_total = {"legendConfig": dict(bar["settings"].get("legendConfig", {}),
                                          showAvg=False, showTotal=True, showMin=False, showMax=False)}
    a.poner("w-hist", "system.bar_chart", "Pulsaciones IR por hora", [
        {"name": "tecla", "label": "Pulsaciones", "color": AZUL,
         "settings": copy.deepcopy(bar["datasources"][0]["dataKeys"][0]["settings"])},
        {"name": "accionamiento", "label": "Accionamientos", "color": VERDE,
         "settings": copy.deepcopy(bar["datasources"][0]["dataKeys"][0]["settings"])},
    ], 0, f, 24 if exhibicion else 12, 6, settings=leyenda_total, conf={
        "useDashboardTimewindow": False,
        "timewindow": {"selectedTab": 0, "realtime": {"realtimeType": 0, "timewindowMs": dia, "interval": 3600000},
                       "aggregation": {"type": "COUNT", "limit": 25000}}})
    if not exhibicion:
        # E. Calidad de recepción ----------------------------------------------------------------
        a.poner("w-cal", "system.bar_chart", "Calidad de recepción IR por hora", [
            {"name": "trama_invalida", "label": "Tramas inválidas", "color": AMBAR,
             "settings": copy.deepcopy(bar["datasources"][0]["dataKeys"][0]["settings"])},
            {"name": "error_rx", "label": "Errores RMT", "color": ROJO,
             "settings": copy.deepcopy(bar["datasources"][0]["dataKeys"][0]["settings"])},
        ], 12, f, 12, 6, settings=leyenda_total, conf={
            "useDashboardTimewindow": False,
            "timewindow": {"selectedTab": 0, "realtime": {"realtimeType": 0, "timewindowMs": dia, "interval": 3600000},
                           "aggregation": {"type": "COUNT", "limit": 25000}}})
    f += 6
    if not exhibicion:
        # E. Eventos y alarmas -------------------------------------------------------------------------
        a.poner("w-ev", "system.cards.timeseries_table", "Historial de eventos", [
            {"name": "tecla", "label": "Tecla", "usePostProcessing": True, "postFuncBody": JS_TECLA},
            {"name": "rele1", "label": "Relé 1", "usePostProcessing": True, "postFuncBody": JS_ONOFF},
            {"name": "rele2", "label": "Relé 2", "usePostProcessing": True, "postFuncBody": JS_ONOFF},
            {"name": "ssr", "label": "SSR", "usePostProcessing": True, "postFuncBody": JS_ONOFF},
            {"name": "trama_invalida", "label": "Trama inválida (símbolos)", "decimals": 0},
            {"name": "reinicio", "label": "Reinicio"},
        ], 0, f, 14, 7, settings={"hideEmptyLines": True, "showTimestamp": True,
                                   "dateFormat": {"format": "dd/MM HH:mm:ss"}, "defaultPageSize": 10},
                conf={"useDashboardTimewindow": False,
                      "timewindow": {"selectedTab": 0, "realtime": {"realtimeType": 0, "timewindowMs": dia},
                                     "aggregation": {"type": "NONE", "limit": 500}}})
        _, alb = a.base("system.alarm_widgets.alarms_table")
        al = copy.deepcopy(alb)
        al.update({"title": "Alarmas", "showTitle": True,
                   "alarmSource": {"type": "entity", "entityAliasId": "a-sony", "dataKeys":
                                   copy.deepcopy((alb.get("alarmSource") or {}).get("dataKeys", []))},
                   "alarmFilterConfig": {"statusList": ["ACTIVE"], "searchPropagatedAlarms": False}})
        al["settings"].update({"alarmsTitle": "Alarmas activas", "allowAssign": False})
        a.widgets["w-alarm"] = {"typeFullFqn": "system.alarm_widgets.alarms_table", "type": "alarm",
                                "sizeX": 10, "sizeY": 7, "config": al, "id": "w-alarm"}
        a.layout["w-alarm"] = {"sizeX": 10, "sizeY": 7, "col": 14, "row": f}
    return {
        "title": TITULO_EXHIBICION if exhibicion else TITULO,
        "configuration": {
            "description": MARCA,
            "entityAliases": {"a-sony": {"id": "a-sony", "alias": "Placa Sony IR", "filter": {
                "type": "entityName", "entityType": "DEVICE", "entityNameFilter": DISPOSITIVO,
                "resolveMultiple": False}}},
            "widgets": a.widgets,
            "states": {"default": {"name": TITULO, "root": True, "layouts": {"main": {
                "widgets": a.layout,
                "gridSettings": {"columns": 24, "margin": 10, "outerMargin": True,
                                 "backgroundColor": "#eef1f5", "mobileAutoFillHeight": False,
                                 "mobileRowHeight": 70, "autoFillHeight": False}}}}},
            "timewindow": {"selectedTab": 0, "realtime": {"realtimeType": 0, "timewindowMs": 6 * 3600 * 1000,
                                                          "interval": 30000},
                           "aggregation": {"type": "NONE", "limit": 5000}},
            "settings": {"stateControllerId": "entity", "showTitle": True,
                         "showDashboardsSelect": False, "showEntitiesSelect": False,
                         "showDashboardTimewindow": True, "showDashboardExport": not exhibicion,
                         "showDashboardLogo": False, "toolbarAlwaysOpen": True,
                         "titleColor": "rgba(0,0,0,0.87)"},
        },
    }


def alarmas(tb):
    """Dos reglas en el perfil 'equipo-01' de ESTE tenant (aditivo):
    - Placa sin conexión: el dispositivo dejó de mandar datos (inactividad de
      ThingsBoard; la placa manda 'enlace' cada 30 s). Se borra sola.
    - Error del receptor IR: la placa logueó un error de RMT."""
    perfiles = tb.req("GET", "/api/deviceProfiles?pageSize=100&page=0&textSearch=" + PERFIL)["data"]
    perfil = next((p for p in perfiles if p["name"] == PERFIL), None)
    if perfil is None:
        perfil = tb.req("POST", "/api/deviceProfile", {
            "name": PERFIL, "type": "DEFAULT", "transportType": "DEFAULT",
            "profileData": {"configuration": {"type": "DEFAULT"},
                            "transportConfiguration": {"type": "DEFAULT"},
                            "provisionConfiguration": {"type": "DISABLED"}, "alarms": []}})
        print(f"perfil '{PERFIL}' creado")
    reglas = perfil["profileData"].get("alarms") or []
    nuevas = [
        {"id": "sony-ir-sin-enlace", "alarmType": "Sony IR: placa sin conexión", "propagate": False,
         "createRules": {"MAJOR": {"condition": {"condition": [{
             "key": {"type": "ATTRIBUTE", "key": "active"}, "valueType": "BOOLEAN",
             "predicate": {"type": "BOOLEAN", "operation": "EQUAL",
                           "value": {"defaultValue": False}}}], "spec": {"type": "SIMPLE"}}}},
         "clearRule": {"condition": {"condition": [{
             "key": {"type": "ATTRIBUTE", "key": "active"}, "valueType": "BOOLEAN",
             "predicate": {"type": "BOOLEAN", "operation": "EQUAL",
                           "value": {"defaultValue": True}}}], "spec": {"type": "SIMPLE"}}}},
        {"id": "sony-ir-error-rx", "alarmType": "Sony IR: error del receptor infrarrojo", "propagate": False,
         "createRules": {"WARNING": {"condition": {"condition": [{
             "key": {"type": "TIME_SERIES", "key": "error_rx"}, "valueType": "NUMERIC",
             "predicate": {"type": "NUMERIC", "operation": "GREATER_OR_EQUAL",
                           "value": {"defaultValue": 1}}}], "spec": {"type": "SIMPLE"}}}}},
    ]
    existentes = {r.get("id") for r in reglas}
    agregar = [r for r in nuevas if r["id"] not in existentes]
    if agregar:
        perfil["profileData"]["alarms"] = reglas + agregar
        tb.req("POST", "/api/deviceProfile", perfil)
        print("alarmas agregadas:", ", ".join(r["alarmType"] for r in agregar))
    else:
        print("alarmas: ya estaban")


def nodo_perfil(tb):
    """En ThingsBoard 4.3 la cadena raíz por defecto ya NO trae el nodo "Device
    Profile", que es el que evalúa las reglas de alarma de los perfiles. Sin él,
    las reglas existen pero nadie las ejecuta. Se agrega como PRIMER nodo de la
    cadena raíz de ESTE tenant (Success -> el que era primero), guardando antes
    una copia para volver atrás. Si ya está, no se toca nada."""
    raiz = next(r for r in tb.req("GET", "/api/ruleChains?pageSize=50&page=0")["data"] if r.get("root"))
    meta = tb.req("GET", f"/api/ruleChain/{raiz['id']['id']}/metadata")
    if any(n["type"].endswith("TbDeviceProfileNode") for n in meta["nodes"]):
        print("cadena raíz: ya evalúa las alarmas de perfil")
        return
    respaldo = os.path.expanduser(f"~/tb-cadena-raiz-{raiz['id']['id']}-antes.json")
    with open(respaldo, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    anterior = meta["firstNodeIndex"]
    meta["nodes"].append({
        "type": "org.thingsboard.rule.engine.profile.TbDeviceProfileNode",
        "name": "Alarmas de perfil (equipo-01-sony-ir)", "debugMode": False,
        "configuration": {"persistAlarmRulesState": True, "fetchAlarmRulesStateOnStart": True},
        "additionalInfo": {"layoutX": 120, "layoutY": 300}})
    nuevo = len(meta["nodes"]) - 1
    meta["connections"].append({"fromIndex": nuevo, "toIndex": anterior, "type": "Success"})
    meta["firstNodeIndex"] = nuevo
    tb.req("POST", "/api/ruleChain/metadata", meta)
    print(f"cadena raíz: nodo de alarmas agregado (copia previa en {respaldo})")


def crear(tb, tablero, reemplazar):
    existentes = tb.req("GET", "/api/tenant/dashboards?pageSize=100&page=0&textSearch="
                        + urllib.request.quote(tablero["title"]))["data"]
    actual = next((d for d in existentes if d["title"] == tablero["title"]), None)
    if actual is None:
        d = tb.req("POST", "/api/dashboard", tablero)
        print(f"creado: {tablero['title']} ({d['id']['id']})")
        return d
    completo = tb.req("GET", "/api/dashboard/" + actual["id"]["id"])
    if completo["configuration"].get("description") != MARCA:
        sys.exit(f"'{tablero['title']}' existe y no lo creó este script: no lo toco")
    if not reemplazar:
        print(f"ya existe: {tablero['title']} (usar --reemplazar para actualizarlo)")
        return completo
    completo["configuration"] = tablero["configuration"]
    d = tb.req("POST", "/api/dashboard", completo)
    print(f"actualizado: {tablero['title']}")
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--crear", action="store_true")
    ap.add_argument("--reemplazar", action="store_true")
    ap.add_argument("--alarmas", action="store_true")
    args = ap.parse_args()
    clave = open(os.environ["TB_CLAVE_ARCHIVO"]).read().strip() if os.environ.get("TB_CLAVE_ARCHIVO") \
        else os.environ.get("TB_CLAVE", "")
    tb = TB(os.environ.get("TB_URL", "http://127.0.0.1:18080"), os.environ["TB_USUARIO"], clave)
    for exh, archivo in ((False, "tablero.json"), (True, "tablero-exhibicion.json")):
        t = armar(tb, exhibicion=exh)
        with open(os.path.join(AQUI, archivo), "w", encoding="utf-8") as f:
            json.dump(t, f, ensure_ascii=False, indent=1)
        print(f"guardado {archivo}")
        if args.crear:
            crear(tb, t, args.reemplazar)
    if args.alarmas:
        alarmas(tb)
        nodo_perfil(tb)


if __name__ == "__main__":
    main()
