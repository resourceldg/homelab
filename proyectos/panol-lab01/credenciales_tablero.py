#!/usr/bin/env python3
"""Tablero "Pañol · Credenciales" en ThingsBoard: ver y gestionar las tarjetas.

    TB_URL=http://127.0.0.1:18080 TB_USUARIO=admin@... TB_CLAVE_ARCHIVO=/ruta \\
        python3 credenciales_tablero.py [--crear] [--reemplazar]

La base del pañol es la fuente de verdad. ThingsBoard es la pantalla: el
sincronizador del pañol (server/adapters/sync_tb.py, repo panol-iot) publica
un asset "tarjeta-panol" por tarjeta y aplica lo que se pide con los botones:

- Aprobar (pendientes): pide el email de la persona y asigna la tarjeta.
- Rechazar (pendientes).
- Dar de baja (activas): deja de abrir en el próximo refresco del nodo.

El botón solo escribe un pedido (`accion`); la base lo valida y deja el
resultado en la columna "Último resultado". Sin datos sensibles más allá de
nombres y emails: el tablero es PRIVADO (solo con login), no se publica.
"""
import argparse
import json
import os
import sys
import urllib.parse

from tablero import (AMBAR, BORDE, CIAN, ESTILO_TARJETA, FONDO, FONDO_URL, ROJO, TARJETA, TENUE,
                     TEXTO, TITULO_ESTILO, VERDE, TB, oscurecer)

AQUI = os.path.dirname(os.path.abspath(__file__))
TITULO = "Pañol · Credenciales"
MARCA = "gestionado por proyectos/panol-lab01/credenciales_tablero.py"

ESTADOS = {"activa": (VERDE, "ACTIVA"), "pendiente": (AMBAR, "PENDIENTE"),
           "rechazada": (ROJO, "RECHAZADA"), "baja": (TENUE, "DE BAJA")}

JS_ESTADO_TEXTO = ("var e = " + json.dumps({k: v[1] for k, v in ESTADOS.items()}) +
                   "; return e[value] || value || '—';")
JS_ESTADO_ESTILO = ("var c = " + json.dumps({k: v[0] for k, v in ESTADOS.items()}) +
                    "; var col = c[value] || '" + TENUE + "';"
                    " return {color: col, fontWeight: 700, letterSpacing: '0.06em'};")
JS_FECHA = ("if (!value) return '—'; var d = new Date(Number(value));"
            " return d.toLocaleDateString('es-AR') + ' ' + d.toLocaleTimeString('es-AR', {hour: '2-digit', minute: '2-digit'});")
JS_RESULTADO_ESTILO = ("var v = String(value || ''); return {color: v.indexOf('ERROR') === 0 ? '" + ROJO +
                       "' : (v.indexOf('OK') === 0 ? '" + VERDE + "' : '" + TENUE + "'), fontSize: '12px'};")


def _accion(nombre, icono, cuerpo, mostrar_si):
    return {
        "name": nombre, "icon": icono, "type": "custom", "id": "a-" + icono,
        "customFunction": cuerpo,
        "useShowWidgetActionFunction": True,
        "showWidgetActionFunction": f"var e = data && (data['Estado'] || data.estado); return e === '{mostrar_si}';",
    }


# Cada botón solo deja un PEDIDO en el asset; el sincronizador lo aplica en
# unos segundos con las reglas de la base y responde en "Último resultado".
JS_PEDIR = """
function pedir(attrs, aviso) {
  widgetContext.attributeService.saveEntityAttributes(entityId, 'SERVER_SCOPE', attrs).subscribe(function () {
    widgetContext.showSuccessToast(aviso, 4000, 'bottom');
  });
}
"""
JS_APROBAR = JS_PEDIR + """
var para = window.prompt('Aprobar la tarjeta ' + entityName +
  '\\n\\nEmail de la persona (la lista está en el panel "Personas"):', '');
if (!para || !para.trim()) { return; }
pedir([{key: 'accion', value: 'aprobar'}, {key: 'aprobar_para', value: para.trim()}],
      'Pedido enviado: se aplica en unos segundos (mirá "Último resultado")');
"""
JS_RECHAZAR = JS_PEDIR + """
if (!window.confirm('¿Rechazar la tarjeta ' + entityName + '? No va a abrir la puerta.')) { return; }
pedir([{key: 'accion', value: 'rechazar'}], 'Rechazo enviado');
"""
JS_BAJA = JS_PEDIR + """
if (!window.confirm('¿Dar de baja la tarjeta ' + entityName + '?\\n\\nDeja de abrir la puerta en el próximo refresco del nodo (hasta 15 min).')) { return; }
pedir([{key: 'accion', value: 'baja'}], 'Baja enviada: deja de abrir en hasta 15 min');
"""

JS_VALORES_MULTI = """
var porEntidad = {};
(ctx.data || []).forEach(function (d) {
  var n = d.datasource && d.datasource.entityName, k = d.dataKey && d.dataKey.name;
  if (!n || !k || !d.data || !d.data.length) return;
  (porEntidad[n] = porEntidad[n] || {})[k] = d.data[d.data.length - 1][1];
});
"""

JS_RESUMEN = JS_VALORES_MULTI + """
var c = {activa: 0, pendiente: 0, rechazada: 0, baja: 0};
Object.keys(porEntidad).forEach(function (n) { var e = porEntidad[n].estado; if (e in c) c[e]++; });
function caja(n, txt, color) {
  return '<div class="caja" style="--c:' + color + '"><b>' + n + '</b><span>' + txt + '</span></div>';
}
return '<div class="res">' + caja(c.activa, 'activas', '%(VERDE)s') +
  caja(c.pendiente, 'pendientes de aprobar', '%(AMBAR)s') +
  caja(c.rechazada, 'rechazadas (30 días)', '%(ROJO)s') + caja(c.baja, 'dadas de baja (30 días)', '%(TENUE)s') +
  '</div>';
""" % {"VERDE": VERDE, "AMBAR": AMBAR, "ROJO": ROJO, "TENUE": TENUE}

CSS_RESUMEN = f"""
.res {{ display:flex; gap:12px; height:100%; align-items:stretch; padding:4px; font-family:Inter,Roboto,sans-serif; }}
.caja {{ flex:1; border:1px solid var(--c); border-radius:14px; display:flex; flex-direction:column;
        justify-content:center; padding:10px 18px; background:rgba(0,0,0,.2); box-shadow:0 0 18px -8px var(--c); }}
.caja b {{ font-size:34px; color:var(--c); line-height:1.1; }}
.caja span {{ font-size:12px; color:{TENUE}; letter-spacing:.06em; text-transform:uppercase; }}
"""

JS_PERSONAS = JS_VALORES_MULTI + """
var lista = [];
Object.keys(porEntidad).forEach(function (n) {
  try { lista = JSON.parse(porEntidad[n].personas || '[]'); } catch (e) {}
});
function esc(s) { return String(s || '').replace(/[&<>"]/g, function (c) {
  return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
if (!lista.length) return '<div class="vac">Sin datos todavía (el sincronizador publica cada 10 s).</div>';
return '<table class="per"><tr><th>Persona</th><th>Email (para aprobar)</th><th>Rol</th></tr>' +
  lista.map(function (p) { return '<tr><td>' + esc(p.nombre) + '</td><td class="em">' + esc(p.email || '— sin email') +
    '</td><td>' + esc(p.rol) + '</td></tr>'; }).join('') + '</table>';
"""
CSS_PERSONAS = f"""
.per {{ width:100%; border-collapse:collapse; font-family:Inter,Roboto,sans-serif; font-size:13px; color:{TEXTO}; }}
.per th {{ text-align:left; color:{TENUE}; font-weight:600; font-size:11px; letter-spacing:.08em; text-transform:uppercase;
          padding:6px 8px; border-bottom:1px solid {BORDE}; }}
.per td {{ padding:6px 8px; border-bottom:1px solid rgba(148,163,184,.08); }}
.per .em {{ color:{CIAN}; user-select:all; }}
.vac {{ color:{TENUE}; padding:12px; font-family:Inter,Roboto,sans-serif; }}
"""

CABECERA = f"""<div style="display:flex;align-items:center;height:100%;padding:0 22px;gap:24px;
font-family:Inter,Roboto,sans-serif;color:{TEXTO};flex-wrap:wrap">
<div><div style="font-size:26px;letter-spacing:.16em;font-weight:300">PAÑOL <b style="color:{CIAN};
font-weight:700;text-shadow:0 0 18px {CIAN}">CREDENCIALES</b></div>
<div style="color:{TENUE};font-size:13px;margin-top:2px">Quién puede abrir la puerta del pañol · LAB01</div></div>
<div style="color:{TENUE};font-size:12.5px;max-width:720px;line-height:1.5">
Las tarjetas grabadas con el botón del nodo llegan como <b style="color:{AMBAR}">PENDIENTES</b> y
<b>no abren</b> hasta aprobarlas. Aprobar pide el email de la persona. Los cambios llegan al nodo en
el próximo refresco (hasta 15 min). La base del pañol valida cada pedido: el resultado aparece en
<i>Último resultado</i>.</div></div>"""


class Armador:
    def __init__(self, tb):
        self.tb = tb
        self.widgets, self.layout, self.base_cache = {}, {}, {}

    def base(self, fqn):
        if fqn not in self.base_cache:
            w = self.tb.req("GET", "/api/widgetType?fqn=" + fqn)
            self.base_cache[fqn] = (w["descriptor"]["type"], json.loads(w["descriptor"]["defaultConfig"] or "{}"))
        tipo, conf = self.base_cache[fqn]
        return tipo, json.loads(json.dumps(conf))

    def poner(self, wid, fqn, titulo, alias, claves, col, fila, ancho, alto, settings=None, conf=None,
              titulo_visible=True, alto_movil=None):
        tipo, c = self.base(fqn)
        c.update({"title": titulo, "showTitle": titulo_visible, "backgroundColor": TARJETA, "color": TEXTO,
                  "padding": "8px", "widgetStyle": dict(ESTILO_TARJETA), "titleStyle": dict(TITULO_ESTILO),
                  "titleColor": TENUE, "dropShadow": False, "enableFullscreen": False, "displayTimewindow": False,
                  "titleFont": {"size": 13, "sizeUnit": "px", "family": "Inter", "weight": "600",
                                "style": "normal", "lineHeight": "20px"}})
        c["datasources"] = [] if alias is None else [{
            "type": "entity", "entityAliasId": alias, "filterId": None,
            "dataKeys": [dict({"type": "attribute", "settings": {}, "color": CIAN}, **k) for k in claves]}]
        if settings:
            c.setdefault("settings", {}).update(settings)
        c["settings"] = oscurecer(c.get("settings", {}))
        if conf:
            c.update(conf)
        c["mobileOrder"] = len(self.widgets)
        if alto_movil:
            c["mobileHeight"] = alto_movil
        self.widgets[wid] = {"typeFullFqn": fqn, "type": tipo, "sizeX": ancho, "sizeY": alto, "config": c, "id": wid}
        self.layout[wid] = {"sizeX": ancho, "sizeY": alto, "col": col, "row": fila}

    def html(self, wid, titulo, alias, claves, js, css, col, fila, ancho, alto, alto_movil=None):
        self.poner(wid, "system.cards.markdown_card", titulo, alias, [{"name": k, "label": k} for k in claves],
                   col, fila, ancho, alto, titulo_visible=bool(titulo), alto_movil=alto_movil,
                   settings={"useMarkdownTextFunction": True, "markdownTextFunction": js,
                             "markdownCss": css, "applyDefaultMarkdownStyle": False})


def columna(nombre, etiqueta, contenido=None, estilo=None, ancho="0px"):
    k = {"name": nombre, "label": etiqueta, "settings": {"columnWidth": ancho}}
    if contenido:
        k["settings"].update({"useCellContentFunction": True, "cellContentFunction": contenido})
    if estilo:
        k["settings"].update({"useCellStyleFunction": True, "cellStyleFunction": estilo})
    return k


def armar(tb):
    a = Armador(tb)
    a.poner("w-cab", "system.cards.markdown_card", "", None, None, 0, 0, 24, 3, titulo_visible=False,
            settings={"markdownTextPattern": CABECERA, "useMarkdownTextFunction": False,
                      "applyDefaultMarkdownStyle": False}, conf={"padding": "0px"}, alto_movil=4)
    a.html("w-res", "", "a-tarjetas", ["estado"], JS_RESUMEN, CSS_RESUMEN, 0, 3, 24, 3, alto_movil=5)
    claves = [
        columna("estado", "Estado", JS_ESTADO_TEXTO, JS_ESTADO_ESTILO, "120px"),
        columna("persona", "Persona"),
        columna("desde", "Desde", JS_FECHA, None, "150px"),
        columna("nodo", "Nodo que la leyó"),
        columna("veces", "Veces leída", None, None, "90px"),
        columna("resultado", "Último resultado", None, JS_RESULTADO_ESTILO, "320px"),
    ]
    a.poner("w-tabla", "system.cards.entities_table", "Tarjetas", "a-tarjetas", claves, 0, 6, 24, 10,
            settings={"entitiesTitle": "Tarjetas", "enableSearch": True, "displayEntityName": True,
                      "entityNameColumnTitle": "Tarjeta (UID)", "displayEntityLabel": False,
                      "displayEntityType": False, "displayPagination": True, "defaultPageSize": 15,
                      "defaultSortOrder": "Estado", "enableSelectColumnDisplay": False},
            conf={"actions": {"actionCellButton": [
                _accion("Aprobar", "how_to_reg", JS_APROBAR, "pendiente"),
                _accion("Rechazar", "block", JS_RECHAZAR, "pendiente"),
                _accion("Dar de baja", "person_remove", JS_BAJA, "activa"),
            ]}})
    a.html("w-per", "Personas (email para aprobar)", "a-personas", ["personas"], JS_PERSONAS, CSS_PERSONAS,
           0, 16, 24, 7)
    return a


def tablero(a):
    return {
        "title": TITULO,
        "configuration": {
            "description": MARCA,
            "entityAliases": {
                "a-tarjetas": {"id": "a-tarjetas", "alias": "Tarjetas del pañol", "filter": {
                    "type": "assetType", "assetTypes": ["tarjeta-panol"], "assetNameFilter": "",
                    "resolveMultiple": True}},
                "a-personas": {"id": "a-personas", "alias": "Personas", "filter": {
                    "type": "entityName", "entityType": "ASSET", "entityNameFilter": "panol-personas",
                    "resolveMultiple": False}},
            },
            "widgets": a.widgets,
            "states": {"default": {"name": TITULO, "root": True, "layouts": {"main": {
                "widgets": a.layout,
                "gridSettings": {"columns": 24, "margin": 12, "outerMargin": True, "backgroundColor": FONDO,
                                 "backgroundImageUrl": FONDO_URL, "backgroundSizeMode": "cover", "color": TEXTO,
                                 "mobileAutoFillHeight": False, "mobileRowHeight": 70, "autoFillHeight": False}}}}},
            "timewindow": {"selectedTab": 0, "realtime": {"realtimeType": 0, "timewindowMs": 86400000,
                                                          "interval": 30000},
                           "aggregation": {"type": "NONE", "limit": 5000}},
            "settings": {"stateControllerId": "entity", "showTitle": False, "showDashboardsSelect": False,
                         "showEntitiesSelect": False, "showDashboardTimewindow": False,
                         "showDashboardExport": False, "showDashboardLogo": False, "toolbarAlwaysOpen": False,
                         "titleColor": TEXTO},
        },
    }


def crear(tb, t, reemplazar):
    existentes = tb.req("GET", "/api/tenant/dashboards?pageSize=100&page=0&textSearch="
                        + urllib.parse.quote(t["title"]))["data"]
    actual = next((d for d in existentes if d["title"] == t["title"]), None)
    if actual is None:
        d = tb.req("POST", "/api/dashboard", t)
        print(f"creado: {t['title']} ({d['id']['id']})")
        return d
    completo = tb.req("GET", "/api/dashboard/" + actual["id"]["id"])
    if completo["configuration"].get("description") != MARCA:
        sys.exit(f"'{t['title']}' existe y no lo creó este script: no lo toco")
    if not reemplazar:
        print(f"ya existe: {t['title']} (usar --reemplazar para actualizarlo)")
        return completo
    completo["configuration"] = t["configuration"]
    d = tb.req("POST", "/api/dashboard", completo)
    print(f"actualizado: {t['title']} ({d['id']['id']})")
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--crear", action="store_true")
    ap.add_argument("--reemplazar", action="store_true")
    args = ap.parse_args()
    clave = open(os.environ["TB_CLAVE_ARCHIVO"]).read().strip() if os.environ.get("TB_CLAVE_ARCHIVO") \
        else os.environ.get("TB_CLAVE", "")
    tb = TB(os.environ.get("TB_URL", "http://127.0.0.1:18080"), os.environ["TB_USUARIO"], clave)
    t = tablero(armar(tb))
    with open(os.path.join(AQUI, "credenciales_tablero.json"), "w", encoding="utf-8") as f:
        json.dump(t, f, ensure_ascii=False, indent=1)
    print("guardado credenciales_tablero.json")
    if args.crear:
        crear(tb, t, args.reemplazar)


if __name__ == "__main__":
    main()
