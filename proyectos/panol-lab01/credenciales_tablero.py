#!/usr/bin/env python3
"""Tablero "Pañol · Credenciales" en ThingsBoard: ver y gestionar las tarjetas.

    TB_URL=http://127.0.0.1:18080 TB_USUARIO=admin@... TB_CLAVE_ARCHIVO=/ruta \\
        python3 credenciales_tablero.py [--crear] [--reemplazar]

La base del pañol es la fuente de verdad. ThingsBoard es la pantalla: el
sincronizador del pañol (server/adapters/sync_tb.py, repo panol-iot) publica
un asset "tarjeta-panol" por tarjeta y aplica lo que se pide con los botones:

- Aprobar (pendientes): abre un diálogo con la lista de personas y asigna la tarjeta.
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


def _accion(nombre, icono, cuerpo, html=None):
    a = {"name": nombre, "icon": icono, "id": "a-" + icono, "customFunction": cuerpo,
         "useShowWidgetActionFunction": False}
    if html:
        a.update({"type": "customPretty", "customHtml": html, "customCss": "", "customResources": []})
    else:
        a["type"] = "custom"
    return a


# Cada botón solo deja un PEDIDO en el asset; el sincronizador lo aplica en
# unos segundos con las reglas de la base y responde en "Último resultado".
JS_PEDIR = """
function refrescar() {
  // El sincronizador aplica el pedido en segundos: se vuelven a consultar las
  // tablas para que la tarjeta pase a su sección sin recargar la página.
  [6000, 15000].forEach(function (ms) { setTimeout(function () { widgetContext.updateAliases(); }, ms); });
}
function pedir(attrs, aviso) {
  widgetContext.attributeService.saveEntityAttributes(entityId, 'SERVER_SCOPE', attrs).subscribe(function () {
    widgetContext.showSuccessToast(aviso, 4000, 'bottom');
    refrescar();
  });
}
"""
HTML_APROBAR = """
<form [formGroup]="form" (ngSubmit)="save()" style="min-width:420px">
  <mat-toolbar color="primary"><h2>Aprobar la tarjeta {{ uid }}</h2><span fxFlex></span>
    <button mat-icon-button (click)="cancel()" type="button"><mat-icon>close</mat-icon></button></mat-toolbar>
  <div mat-dialog-content style="padding-top:16px">
    <p style="margin:0 0 12px;font-size:14px;line-height:1.5">¿De quién es esta tarjeta? Va a poder abrir la puerta del pañol
      en el próximo refresco del nodo (hasta 15 min).</p>
    <mat-form-field appearance="outline" style="width:100%">
      <mat-label>Persona</mat-label>
      <mat-select formControlName="persona" required>
        <mat-option *ngFor="let p of personas" [value]="p.email || p.nombre">
          {{ p.nombre }} <span style="opacity:.6">· {{ p.rol }} · {{ p.email || 'sin email' }}</span>
        </mat-option>
      </mat-select>
      <mat-error>Elegí una persona</mat-error>
    </mat-form-field>
    <div *ngIf="!personas.length" style="opacity:.7">Cargando personas…</div>
  </div>
  <div mat-dialog-actions fxLayoutAlign="end center">
    <button mat-button type="button" (click)="cancel()">Cancelar</button>
    <button mat-raised-button color="primary" type="submit" [disabled]="form.invalid">Aprobar</button>
  </div>
</form>
"""
JS_APROBAR_DIALOGO = """
var $injector = widgetContext.$scope.$injector;
var customDialog = $injector.get(widgetContext.servicesMap.get('customDialog'));
var http = widgetContext.http;
customDialog.customDialog(htmlTemplate, function (vm) {
  vm.uid = entityName;
  vm.personas = [];
  vm.form = vm.fb.group({persona: [null, [vm.validators.required]]});
  http.get('/api/tenant/assets?assetName=panol-personas').subscribe(function (a) {
    http.get('/api/plugins/telemetry/ASSET/' + a.id.id + '/values/attributes/SERVER_SCOPE?keys=personas')
      .subscribe(function (attrs) {
        try { vm.personas = JSON.parse((attrs[0] || {}).value || '[]'); } catch (e) { vm.personas = []; }
      });
  });
  vm.cancel = function () { vm.dialogRef.close(null); };
  vm.save = function () {
    if (vm.form.invalid) { return; }
    widgetContext.attributeService.saveEntityAttributes(entityId, 'SERVER_SCOPE', [
      {key: 'accion', value: 'aprobar'}, {key: 'aprobar_para', value: vm.form.value.persona}
    ]).subscribe(function () {
      widgetContext.showSuccessToast('Aprobación enviada: se aplica en unos segundos', 4000, 'bottom');
      vm.dialogRef.close(null);
      [6000, 15000].forEach(function (ms) { setTimeout(function () { widgetContext.updateAliases(); }, ms); });
    });
  };
}).subscribe();
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
.res {{ display:flex; flex-wrap:wrap; gap:12px; height:100%; align-items:stretch; padding:4px;
        font-family:Inter,Roboto,sans-serif; box-sizing:border-box; }}
.caja {{ flex:1 1 140px; min-height:70px; box-sizing:border-box; border:1px solid var(--c); border-radius:14px; display:flex; flex-direction:column;
        justify-content:center; padding:10px 18px; background:rgba(0,0,0,.2); box-shadow:0 0 18px -8px var(--c); }}
.caja b {{ font-size:34px; color:var(--c); line-height:1.1; }}
.caja span {{ font-size:12px; color:{TENUE}; letter-spacing:.06em; text-transform:uppercase; }}
"""


CABECERA = f"""<div style="display:flex;align-items:center;height:100%;padding:0 22px;gap:24px;
font-family:Inter,Roboto,sans-serif;color:{TEXTO};flex-wrap:wrap">
<div><div style="font-size:26px;letter-spacing:.16em;font-weight:300">PAÑOL <b style="color:{CIAN};
font-weight:700;text-shadow:0 0 18px {CIAN}">CREDENCIALES</b></div>
<div style="color:{TENUE};font-size:13px;margin-top:2px">Quién puede abrir la puerta del pañol · LAB01</div></div>
<div style="color:{TENUE};font-size:12.5px;max-width:720px;line-height:1.5">
Las tarjetas grabadas con el botón del nodo llegan como <b style="color:{AMBAR}">PENDIENTES</b> y
<b>no abren</b> hasta aprobarlas: en <b>Aprobar</b> elegís de quién es. Los cambios llegan al nodo en
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
    a.html("w-res", "", "a-tarjetas", ["estado"], JS_RESUMEN, CSS_RESUMEN, 0, 3, 24, 3, alto_movil=3)

    def tabla(wid, titulo, filtro, claves, acciones, fila, alto, vacio, orden):
        a.poner(wid, "system.cards.entities_table", titulo, "a-tarjetas", claves, 0, fila, 24, alto,
                settings={"entitiesTitle": titulo, "enableSearch": True, "displayEntityName": True,
                          "entityNameColumnTitle": "Tarjeta (UID)", "displayEntityLabel": False,
                          "displayEntityType": False, "displayPagination": True, "defaultPageSize": 10,
                          "defaultSortOrder": orden, "enableSelectColumnDisplay": False,
                          "enableStickyAction": False},
                conf={"actions": {"actionCellButton": acciones}, "noDataDisplayMessage": vacio})
        a.widgets[wid]["config"]["datasources"][0]["filterId"] = filtro

    tabla("w-pend", "Pendientes de aprobar", "f-pendiente", [
        columna("desde", "Leída por primera vez", JS_FECHA, None, "190px"),
        columna("nodo", "Nodo", None, None, "200px"),
        columna("veces", "Veces que se pasó", None, None, "150px"),
        columna("resultado", "Último resultado", None, JS_RESULTADO_ESTILO),
    ], [_accion("Aprobar", "how_to_reg", JS_APROBAR_DIALOGO, HTML_APROBAR),
        _accion("Rechazar", "block", JS_RECHAZAR)], 6, 8,
        "No hay tarjetas pendientes. Una tarjeta grabada con el botón del nodo aparece acá.",
        "-Leída por primera vez")
    tabla("w-act", "Tarjetas activas (abren la puerta)", "f-activa", [
        columna("persona", "Persona"),
        columna("email", "Email"),
        columna("desde", "Alta", JS_FECHA, None, "170px"),
        columna("resultado", "Último resultado", None, JS_RESULTADO_ESTILO),
    ], [_accion("Dar de baja", "person_remove", JS_BAJA)], 14, 9, "No hay tarjetas activas.",
        "Persona")
    tabla("w-hist", "Historial · rechazadas y dadas de baja (30 días)", "f-historial", [
        columna("estado", "Estado", JS_ESTADO_TEXTO, JS_ESTADO_ESTILO, "130px"),
        columna("persona", "Persona"),
        columna("desde", "Cuándo", JS_FECHA, None, "170px"),
        columna("resultado", "Último resultado", None, JS_RESULTADO_ESTILO),
    ], [], 23, 6, "Sin rechazos ni bajas en los últimos 30 días.", "-Cuándo")
    return a


def _filtro(fid, nombre, igual=None, distinto=()):
    """Filtro por el atributo `estado`. Las condiciones se combinan con AND."""
    def cond(op, v, i):
        return {"key": {"type": "ATTRIBUTE", "key": "estado"}, "valueType": "STRING", "predicates": [{
            "keyFilterPredicate": {"type": "STRING", "operation": op, "ignoreCase": True,
                                   "value": {"defaultValue": v}},
            "userInfo": {"editable": False, "label": "", "autogeneratedLabel": True, "order": i}}]}
    claves = ([cond("EQUAL", igual, 0)] if igual else []) + \
        [cond("NOT_EQUAL", v, i + 1) for i, v in enumerate(distinto)]
    return {"id": fid, "filter": nombre, "editable": False, "keyFilters": claves}


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
            "filters": {
                "f-pendiente": _filtro("f-pendiente", "Pendientes", igual="pendiente"),
                "f-activa": _filtro("f-activa", "Activas", igual="activa"),
                "f-historial": _filtro("f-historial", "Rechazadas y bajas",
                                       distinto=("activa", "pendiente")),
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
