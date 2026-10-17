#!/usr/bin/env python3
"""Genera (y opcionalmente crea) el tablero de ThingsBoard del pañol IoT (LAB01).

    TB_URL=http://127.0.0.1:18080 TB_USUARIO=admin@... TB_CLAVE_ARCHIVO=/ruta \\
        python3 tablero.py [--crear] [--reemplazar] [--alarmas] [--dispositivo NOMBRE]

- Sin opciones: arma el tablero y lo guarda en tablero.json. No cambia nada.
- --crear: lo crea en el tenant del usuario, SOLO si no existe uno con ese
  título. --reemplazar actualiza uno que haya creado este script (lleva la
  marca en la descripción); nunca toca un tablero hecho a mano.
- --alarmas: agrega al perfil de dispositivo "panol" las reglas de alarma del
  pañol (las mismas que define el motor de sesiones) y, si falta, el nodo
  "Device Profile" en la cadena raíz (ThingsBoard 4.3 no lo trae).

Estilo oscuro: el plano del pañol y las tarjetas de sesión son tarjetas
Markdown con una función que arma HTML/SVG con los datos en vivo. El resto son
widgets estándar de la instancia con colores oscuros.

Credenciales por variables de entorno o archivo, nunca por línea de comandos
ni en el repositorio. Solo biblioteca estándar.
"""
import argparse
import base64
import copy
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
PERFIL = "panol"
MARCA = "gestionado por proyectos/panol-lab01/tablero.py"
TITULO = "Pañol IoT · LAB01"

# Paleta (fondo azul noche, acentos neón).
FONDO = "#070b14"
TARJETA = "rgba(15, 23, 42, 0.78)"
BORDE = "rgba(56, 189, 248, 0.18)"
TEXTO = "#e2e8f0"
TENUE = "#94a3b8"
CIAN, VERDE, AMBAR, ROJO, VIOLETA = "#22d3ee", "#22c55e", "#f59e0b", "#ef4444", "#a78bfa"

ESTILO_TARJETA = {
    "border": f"1px solid {BORDE}", "borderRadius": "16px",
    "boxShadow": "0 0 0 1px rgba(34,211,238,0.04), 0 10px 30px rgba(0,0,0,0.45)",
    "backdropFilter": "blur(6px)",
}
TITULO_ESTILO = {"color": TENUE, "fontSize": "13px", "fontWeight": "500", "letterSpacing": "0.08em",
                 "textTransform": "uppercase"}

# Fondo del tablero: grilla fina + dos resplandores. Un SVG en data URI.
_FONDO_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='1600' height='1000'>"
    "<defs><radialGradient id='a' cx='15%' cy='10%' r='60%'><stop offset='0' stop-color='#0e7490' stop-opacity='.35'/>"
    "<stop offset='1' stop-color='#070b14' stop-opacity='0'/></radialGradient>"
    "<radialGradient id='b' cx='90%' cy='90%' r='60%'><stop offset='0' stop-color='#6d28d9' stop-opacity='.25'/>"
    "<stop offset='1' stop-color='#070b14' stop-opacity='0'/></radialGradient>"
    "<pattern id='g' width='40' height='40' patternUnits='userSpaceOnUse'>"
    "<path d='M40 0H0V40' fill='none' stroke='#1e293b' stroke-width='.6'/></pattern></defs>"
    "<rect width='100%' height='100%' fill='#070b14'/><rect width='100%' height='100%' fill='url(#g)'/>"
    "<rect width='100%' height='100%' fill='url(#a)'/><rect width='100%' height='100%' fill='url(#b)'/></svg>")
FONDO_URL = "data:image/svg+xml;base64," + base64.b64encode(_FONDO_SVG.encode()).decode()

# --- JavaScript que corre en el navegador -------------------------------------------
# ctx.data: una entrada por clave con data = [[ts, valor], ...]. Se arma un mapa
# clave -> {v, ts} con el último valor. Común a las tarjetas con función.
JS_VALORES = """
var V = {};
(ctx.data || []).forEach(function (d) {
  var k = d.dataKey && d.dataKey.name;
  if (k && d.data && d.data.length) { var u = d.data[d.data.length - 1]; V[k] = {v: u[1], ts: u[0]}; }
});
function val(k, def) { return (V[k] && V[k].v !== undefined && V[k].v !== null && V[k].v !== '') ? V[k].v : def; }
function num(k) { return Number(val(k, 0)) || 0; }
function hace(k) { return V[k] ? (Date.now() - V[k].ts) / 1000 : 1e9; }
function hora(ms) { if (!ms) return '—'; var d = new Date(Number(ms));
  return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2); }
function esc(s) { return String(s).replace(/[&<>"]/g, function (c) {
  return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
var enLinea = String(val('active', 'false')) === 'true' ||
  (num('nodo_en_linea') === 1 && hace('nodo_en_linea') < 180);
var segPir = num('pir') === 1 ? hace('pir') : 1e9;   // segundos desde el último movimiento
var pirActivo = segPir < 15;
var sesion = num('sesion') === 1;
"""

JS_CABECERA = JS_VALORES + f"""
var alarma = String(val('alarma', 'OK'));
var hayAlarma = alarma !== 'OK' && hace('alarma') < 3600;
function chip(txt, color, pulso) {{
  return '<span class="chip' + (pulso ? ' pulso' : '') + '" style="--c:' + color + '"><i></i>' + txt + '</span>';
}}
return '<div class="cab"><div><div class="t">PAÑOL <b>IoT</b></div>' +
  '<div class="s">LAB01 · control de acceso y auditoría</div></div><div class="chips">' +
  chip(enLinea ? 'NODO EN LÍNEA' : 'NODO SIN CONEXIÓN', enLinea ? '{VERDE}' : '{ROJO}', !enLinea) +
  chip(sesion ? 'SESIÓN EN CURSO' : 'SIN SESIÓN', sesion ? '{CIAN}' : '{TENUE}', false) +
  chip(pirActivo ? 'MOVIMIENTO · hace ' + Math.round(segPir) + ' s' : 'SIN MOVIMIENTO', pirActivo ? '{AMBAR}' : '{TENUE}', pirActivo) +
  chip(hayAlarma ? 'ALARMA: ' + esc(alarma.replace(/_/g, ' ')) : 'SIN ALARMAS', hayAlarma ? '{ROJO}' : '{VERDE}', hayAlarma) +
  '</div></div>';
"""

CSS_CABECERA = f"""
.cab {{ display:flex; align-items:center; justify-content:space-between; height:100%; padding:0 22px;
       font-family:Inter,Roboto,sans-serif; color:{TEXTO}; gap:16px; flex-wrap:wrap; }}
.cab .t {{ font-size:28px; letter-spacing:.18em; font-weight:300; }}
.cab .t b {{ color:{CIAN}; font-weight:700; text-shadow:0 0 18px {CIAN}; }}
.cab .s {{ color:{TENUE}; font-size:13px; letter-spacing:.06em; margin-top:2px; }}
.chips {{ display:flex; gap:10px; flex-wrap:wrap; }}
.chip {{ display:inline-flex; align-items:center; gap:8px; padding:7px 14px; border-radius:999px;
        font-size:12px; font-weight:600; letter-spacing:.08em; color:var(--c);
        border:1px solid var(--c); background:rgba(0,0,0,.25); box-shadow:0 0 14px -4px var(--c); }}
.chip i {{ width:8px; height:8px; border-radius:50%; background:var(--c); box-shadow:0 0 10px var(--c); }}
.chip.pulso i {{ animation:lat 1.1s infinite; }}
@keyframes lat {{ 50% {{ opacity:.25; transform:scale(.7); }} }}
"""

# Plano del pañol: puerta (izquierda), lector RFID y cerradura, PIR (esquina),
# 4 armarios (derecha) y la persona adentro si hay sesión.
JS_PLANO = JS_VALORES + f"""
var puerta = num('puerta') === 1;
var acceso = String(val('acceso', ''));
var accReciente = hace('acceso') < 12;
var pir = pirActivo;
var alarma = String(val('alarma', 'OK'));
var hayAlarma = alarma !== 'OK' && hace('alarma') < 3600;
var cPuerta = hayAlarma && alarma.indexOf('APERTURA') === 0 ? '{ROJO}' : (puerta ? '{AMBAR}' : '{VERDE}');
var cLector = accReciente ? (acceso === 'CONCEDIDO' ? '{VERDE}' : (acceso === 'DENEGADO' ? '{ROJO}' : '{AMBAR}')) : '{CIAN}';
var arm = '';
for (var i = 1; i <= 4; i++) {{
  var ab = num('armario' + i) === 1, y = 58 + (i - 1) * 82, c = ab ? '{AMBAR}' : '{VIOLETA}';
  arm += '<g class="' + (ab ? 'brilla' : '') + '"><rect x="640" y="' + y + '" width="110" height="66" rx="8" fill="' + c +
    '" fill-opacity="' + (ab ? .28 : .12) + '" stroke="' + c + '" stroke-width="2"/>' +
    (ab ? '<line x1="640" y1="' + y + '" x2="610" y2="' + (y + 18) + '" stroke="' + c + '" stroke-width="3"/>' : '') +
    '<text x="695" y="' + (y + 30) + '" class="lb" fill="' + c + '">ARMARIO ' + i + '</text>' +
    '<text x="695" y="' + (y + 48) + '" class="lb2">' + (ab ? 'ABIERTO' : 'cerrado') + '</text></g>';
}}
var hoja = puerta
  ? '<line x1="58" y1="170" x2="128" y2="122" stroke="' + cPuerta + '" stroke-width="6" stroke-linecap="round"/>' +
    '<path d="M58 250 A80 80 0 0 0 128 122" fill="none" stroke="' + cPuerta + '" stroke-dasharray="4 6" opacity=".6"/>'
  : '<line x1="58" y1="170" x2="58" y2="250" stroke="' + cPuerta + '" stroke-width="6" stroke-linecap="round"/>';
var persona = sesion
  ? '<g class="flota"><circle cx="360" cy="215" r="60" fill="{CIAN}" fill-opacity=".07" stroke="{CIAN}" stroke-opacity=".35"/>' +
    '<circle cx="360" cy="196" r="16" fill="{CIAN}"/><path d="M330 250 Q360 212 390 250 Z" fill="{CIAN}"/>' +
    '<text x="360" y="300" class="lb" fill="{CIAN}">' + esc(val('sesion_usuario', 'en sesión')) + '</text></g>'
  : '<text x="360" y="220" class="lb2" style="font-size:15px">pañol vacío · sin sesión</text>';
// Cono de detección: se ilumina con cada movimiento y se apaga en 15 s (la
// animación arranca "adelantada" lo que ya pasó, así no depende de redibujar).
var ondas = pir
  ? '<g class="det" style="animation-delay:-' + segPir.toFixed(1) + 's">' +
    '<path d="M572 52 L250 390 L560 390 Z" fill="url(#cono)"/>' +
    '<g stroke="{AMBAR}" fill="none" stroke-width="3"><path class="onda" d="M522 62 A55 55 0 0 0 582 112"/>' +
    '<path class="onda o2" d="M498 66 A85 85 0 0 0 586 146"/><path class="onda o3" d="M472 70 A115 115 0 0 0 590 180"/></g></g>'
  : '';
return '<div class="plano"><svg viewBox="0 0 800 420" preserveAspectRatio="xMidYMid meet">' +
  '<defs><pattern id="p" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#1e293b" stroke-width=".7"/></pattern>' +
  '<linearGradient id="cono" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{AMBAR}" stop-opacity=".45"/><stop offset="1" stop-color="{AMBAR}" stop-opacity="0"/></linearGradient>' +
  '<filter id="gl"><feGaussianBlur stdDeviation="3.5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>' +
  '<rect x="58" y="30" width="720" height="360" rx="14" fill="url(#p)" stroke="{CIAN}" stroke-opacity=".55" stroke-width="2" filter="url(#gl)"/>' +
  '<rect x="50" y="170" width="16" height="80" fill="{FONDO}"/>' + hoja +
  '<text x="24" y="212" class="lb" fill="' + cPuerta + '" transform="rotate(-90 24 212)">PUERTA · ' + (puerta ? 'ABIERTA' : 'CERRADA') + '</text>' +
  '<g filter="url(#gl)"><rect x="76" y="270" width="40" height="54" rx="7" fill="' + cLector + '" fill-opacity=".18" stroke="' + cLector + '" stroke-width="2"/>' +
  '<path d="M88 288 a8 8 0 0 1 16 0 M84 296 a12 12 0 0 1 24 0" fill="none" stroke="' + cLector + '" stroke-width="2"/></g>' +
  '<text x="96" y="346" class="lb" fill="' + cLector + '">RFID</text>' +
  '<text x="96" y="362" class="lb2">' + (accReciente ? esc(acceso.replace(/_/g, ' ')) : 'en espera') + '</text>' +
  '<g transform="translate(76 108)"><rect x="0" y="14" width="30" height="24" rx="4" fill="none" stroke="' + (puerta ? '{AMBAR}' : '{VERDE}') + '" stroke-width="2"/>' +
  '<path d="M7 14 v-6 a8 8 0 0 1 16 0 v' + (puerta ? '-2' : '6') + '" fill="none" stroke="' + (puerta ? '{AMBAR}' : '{VERDE}') + '" stroke-width="2"/></g>' +
  ondas + '<g filter="url(#gl)"><circle cx="572" cy="52" r="' + (pir ? 14 : 10) + '" fill="' + (pir ? '{AMBAR}' : '{TENUE}') + '"' + (pir ? ' class="lat"' : '') + '/></g>' +
  '<text x="500" y="44" class="lb" fill="' + (pir ? '{AMBAR}' : '{TENUE}') + '" style="text-anchor:end">PIR · ' + (pir ? 'MOVIMIENTO hace ' + Math.round(segPir) + ' s' : 'quieto') + '</text>' +
  arm + persona + '</svg></div>';
"""

CSS_PLANO = f"""
.plano {{ height:100%; display:flex; align-items:center; justify-content:center; }}
.plano svg {{ width:100%; height:100%; font-family:Inter,Roboto,sans-serif; }}
.lb {{ font-size:12px; font-weight:700; letter-spacing:.12em; text-anchor:middle; }}
.lb2 {{ font-size:11px; fill:{TENUE}; text-anchor:middle; letter-spacing:.05em; }}
.onda {{ stroke-width:2.5; opacity:0; animation:onda 1.6s infinite; }}
.o2 {{ animation-delay:.3s; }} .o3 {{ animation-delay:.6s; }}
@keyframes onda {{ 0% {{ opacity:0; }} 30% {{ opacity:1; }} 100% {{ opacity:0; }} }}
.brilla {{ animation:brilla 1.4s infinite alternate; }}
@keyframes brilla {{ to {{ opacity:.55; }} }}
.flota {{ animation:flota 3s ease-in-out infinite; }}
.det {{ animation:det 15s linear forwards; }}
@keyframes det {{ 0% {{ opacity:1; }} 70% {{ opacity:.6; }} 100% {{ opacity:0; }} }}
.lat {{ animation:latpir .9s infinite; }}
@keyframes latpir {{ 50% {{ opacity:.35; }} }}
@keyframes flota {{ 50% {{ transform:translateY(-4px); }} }}
"""

# Tarjeta grande de la sesión en curso (o de la última).
JS_SESION = JS_VALORES + f"""
var nombre = String(val('sesion_usuario', '—'));
var rol = String(val('sesion_rol', ''));
var inicio = Number(val('sesion_inicio', 0));
var min = sesion && inicio ? Math.max(0, Math.round((Date.now() - inicio) / 60000)) : 0;
var ini = nombre.split(' ').map(function (p) {{ return p.charAt(0); }}).join('').slice(0, 2).toUpperCase();
var c = sesion ? '{CIAN}' : '{TENUE}';
var pct = Math.min(100, min / 120 * 100);
var fin = String(val('fin_sesion', ''));
var motivos = {{RELEVO: 'relevo (entró otra persona)', AUSENCIA: 'ausencia (sin actividad)', CIERRE_SISTEMA: 'cierre de jornada'}};
return '<div class="ses"><div class="anillo" style="--c:' + c + ';--p:' + pct + '"><div>' + (sesion ? esc(ini) : '—') + '</div></div>' +
  '<div class="dat"><div class="k">' + (sesion ? 'SESIÓN EN CURSO' : 'SIN SESIÓN') + '</div>' +
  '<div class="n">' + (sesion ? esc(nombre) : 'Pañol cerrado') + '</div>' +
  '<div class="r">' + (sesion ? esc(rol) + ' · desde las ' + hora(inicio) : (fin ? 'última: ' + esc(motivos[fin] || fin) : '')) + '</div>' +
  (sesion ? '<div class="m"><b>' + min + '</b> min adentro</div>' : '') + '</div></div>';
"""

CSS_SESION = f"""
.ses {{ height:100%; display:flex; align-items:center; gap:22px; padding:0 22px; font-family:Inter,Roboto,sans-serif; color:{TEXTO}; }}
.anillo {{ flex:0 0 116px; height:116px; border-radius:50%; display:grid; place-items:center;
          background:conic-gradient(var(--c) calc(var(--p) * 1%), rgba(148,163,184,.15) 0);
          box-shadow:0 0 28px -6px var(--c); }}
.anillo div {{ width:96px; height:96px; border-radius:50%; background:{FONDO}; display:grid; place-items:center;
              font-size:32px; font-weight:700; color:var(--c); letter-spacing:.05em; }}
.dat .k {{ font-size:11px; letter-spacing:.14em; color:{TENUE}; font-weight:600; }}
.dat .n {{ font-size:24px; font-weight:600; margin-top:4px; }}
.dat .r {{ font-size:13px; color:{TENUE}; margin-top:2px; }}
.dat .m {{ margin-top:10px; font-size:13px; color:{TENUE}; }}
.dat .m b {{ font-size:22px; color:{CIAN}; text-shadow:0 0 12px {CIAN}; }}
"""

CLAVES_EN_VIVO = ["active", "nodo_en_linea", "rssi", "sesion", "sesion_usuario", "sesion_rol", "sesion_inicio", "fin_sesion",
                  "puerta", "acceso", "pir", "alarma", "armario1", "armario2", "armario3", "armario4"]
ATRIBUTOS = {"active"}


# Los widgets estándar vienen pensados para fondo blanco: se reemplazan sus
# colores negros-transparentes por los del tema oscuro, en cualquier nivel.
_OSCUROS = {"rgba(0, 0, 0, 0.12)": "rgba(148, 163, 184, 0.12)", "rgba(0, 0, 0, 0.38)": TENUE,
            "rgba(0, 0, 0, 0.54)": TENUE, "rgba(0, 0, 0, 0.76)": TEXTO, "rgba(0, 0, 0, 0.87)": TEXTO}


def oscurecer(x):
    if isinstance(x, dict):
        r = {k: oscurecer(v) for k, v in x.items()}
        if r.get("type") == "color" and r.get("color") in ("#fff", "#ffffff", "#FFFFFF"):
            r["color"] = "rgba(0,0,0,0)"
        if "tooltipBackgroundColor" in r:
            r["tooltipBackgroundColor"] = "rgba(15, 23, 42, 0.92)"
        return r
    if isinstance(x, list):
        return [oscurecer(v) for v in x]
    return _OSCUROS.get(x, x) if isinstance(x, str) else x


class TB:
    def __init__(self, base, usuario, clave):
        self.base = base.rstrip("/")
        self.token = self.req("POST", "/api/auth/login", {"username": usuario, "password": clave}, auth=False)["token"]

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

    def poner(self, wid, fqn, titulo, claves, col, fila, ancho, alto, settings=None, conf=None, titulo_visible=True):
        tipo, c = self.base(fqn)
        c.update({"title": titulo, "showTitle": titulo_visible, "backgroundColor": TARJETA, "color": TEXTO,
                  "padding": "8px", "widgetStyle": dict(ESTILO_TARJETA), "titleStyle": dict(TITULO_ESTILO),
                  "dropShadow": False, "enableFullscreen": False, "showTitleIcon": False,
                  "titleColor": TENUE, "displayTimewindow": False,
                  "titleFont": {"size": 13, "sizeUnit": "px", "family": "Inter", "weight": "600",
                                "style": "normal", "lineHeight": "20px"}})
        c["datasources"] = [] if claves is None else [{
            "type": "entity", "entityAliasId": "a-panol", "filterId": None,
            "dataKeys": [dict({"type": "attribute" if k["name"] in ATRIBUTOS else "timeseries",
                               "settings": {}, "color": CIAN}, **k) for k in claves],
        }]
        if settings:
            c.setdefault("settings", {}).update(settings)
        c["settings"] = oscurecer(c.get("settings", {}))
        if "dataZoom" in c["settings"]:
            c["settings"]["dataZoom"] = False
        if isinstance(c["settings"].get("legendConfig"), dict):
            c["settings"]["legendConfig"].update({"direction": "row", "position": "top", "showAvg": False,
                                                  "showMin": False, "showMax": False, "showTotal": False})
        if conf:
            c.update(conf)
        c["mobileOrder"] = len(self.widgets)
        self.widgets[wid] = {"typeFullFqn": fqn, "type": tipo, "sizeX": ancho, "sizeY": alto, "config": c, "id": wid}
        self.layout[wid] = {"sizeX": ancho, "sizeY": alto, "col": col, "row": fila}

    def html(self, wid, js, css, col, fila, ancho, alto, alto_movil=None):
        self.poner(wid, "system.cards.markdown_card", "", [{"name": k, "label": k} for k in CLAVES_EN_VIVO],
                   col, fila, ancho, alto, titulo_visible=False,
                   settings={"useMarkdownTextFunction": True, "markdownTextFunction": js,
                             "markdownCss": css, "applyDefaultMarkdownStyle": False},
                   conf={"padding": "0px"})
        if alto_movil:
            self.widgets[wid]["config"]["mobileHeight"] = alto_movil

    def contador(self, wid, titulo, clave, color, icono, col, fila, ancho=6, alto=3):
        """Cuántos eventos 'clave' hubo desde las 00:00 (suma de unos)."""
        settings = {
            "layout": "horizontal", "autoScale": False, "showLabel": True, "labelPosition": "top",
            "showIcon": True, "icon": icono, "showDate": False,
            "labelFont": {"family": "Inter", "size": 14, "sizeUnit": "px", "style": "normal", "weight": "500"},
            "labelColor": {"type": "constant", "color": TENUE},
            "valueFont": {"family": "Inter", "size": 40, "sizeUnit": "px", "style": "normal", "weight": "700"},
            "iconSize": 40, "iconSizeUnit": "px",
            "valueColor": {"type": "constant", "color": color},
            "iconColor": {"type": "constant", "color": color},
            "background": {"type": "color", "color": "rgba(0,0,0,0)", "overlay": {"enabled": False}},
        }
        conf = {"units": "", "decimals": 0, "useDashboardTimewindow": False, "displayTimewindow": False,
                "timewindow": {"selectedTab": 0, "realtime": {"realtimeType": 1, "interval": 60000,
                                                              "quickInterval": "CURRENT_DAY"},
                               "aggregation": {"type": "SUM", "limit": 50000}}}
        self.poner(wid, "system.cards.value_card", titulo,
                   [{"name": clave, "label": titulo, "aggregationType": "SUM"}],
                   col, fila, ancho, alto, settings, conf, titulo_visible=False)
        self.widgets[wid]["config"]["padding"] = "12px 20px"


def armar(tb):
    a = Armador(tb)
    a.html("w-cab", JS_CABECERA, CSS_CABECERA, 0, 0, 24, 2, alto_movil=3)
    a.html("w-plano", JS_PLANO, CSS_PLANO, 0, 2, 15, 9, alto_movil=4)
    a.html("w-sesion", JS_SESION, CSS_SESION, 15, 2, 9, 4, alto_movil=3)
    a.contador("w-conc", "Accesos concedidos hoy", "acceso_concedido", VERDE, "how_to_reg", 0, 11)
    a.contador("w-den", "Accesos denegados hoy", "acceso_denegado", ROJO, "block", 6, 11)
    a.contador("w-ses", "Sesiones hoy", "sesion_nueva", CIAN, "badge", 12, 11)
    a.contador("w-alh", "Alarmas hoy", "alarma_evento", AMBAR, "notification_important", 18, 11)
    f = 14
    # Accesos por hora (barras), últimas 24 h.
    _, bar = a.base("system.bar_chart")
    ks = bar["datasources"][0]["dataKeys"][0]["settings"]
    a.poner("w-hist", "system.bar_chart", "Accesos por hora · 24 h", [
        {"name": "acceso_concedido", "label": "Concedidos", "color": VERDE, "settings": copy.deepcopy(ks)},
        {"name": "acceso_denegado", "label": "Denegados", "color": ROJO, "settings": copy.deepcopy(ks)},
        {"name": "acceso_sin_ingreso", "label": "Sin ingreso", "color": AMBAR, "settings": copy.deepcopy(ks)},
    ], 0, f, 15, 6, conf={
        "useDashboardTimewindow": False,
        "timewindow": {"selectedTab": 0, "realtime": {"realtimeType": 0, "timewindowMs": 86400000,
                                                      "interval": 3600000},
                       "aggregation": {"type": "SUM", "limit": 25000}}})
    # Puerta y sesión en el tiempo.
    _, sc = a.base("system.state_chart")
    ksc = sc["datasources"][0]["dataKeys"][0]["settings"]
    a.poner("w-estados", "system.state_chart", "Puerta y sesión · 6 h", [
        {"name": "puerta", "label": "Puerta abierta", "color": AMBAR, "settings": copy.deepcopy(ksc)},
        {"name": "sesion", "label": "Sesión en curso", "color": CIAN, "settings": copy.deepcopy(ksc)},
    ], 15, f, 9, 6, settings={"states": [
        {"label": "No", "value": 0, "sourceType": "constant", "sourceValue": 0},
        {"label": "Sí", "value": 1, "sourceType": "constant", "sourceValue": 1}]},
        conf={"useDashboardTimewindow": True})
    f += 6
    # Registro de eventos y alarmas.
    a.poner("w-ev", "system.cards.timeseries_table", "Registro de eventos", [
        {"name": "acceso", "label": "Acceso"}, {"name": "acceso_usuario", "label": "Persona / tarjeta"},
        {"name": "puerta", "label": "Puerta", "usePostProcessing": True,
         "postFuncBody": "return Number(value) === 1 ? 'abre' : 'cierra';"},
        {"name": "fin_sesion", "label": "Fin de sesión"}, {"name": "alarma", "label": "Alarma"},
    ], 0, f, 15, 7, settings={"hideEmptyLines": True, "showTimestamp": True,
                               "dateFormat": {"format": "dd/MM HH:mm:ss"}, "defaultPageSize": 10},
        conf={"useDashboardTimewindow": False,
              "timewindow": {"selectedTab": 0, "realtime": {"realtimeType": 0, "timewindowMs": 86400000},
                             "aggregation": {"type": "NONE", "limit": 500}}})
    a.poner("w-pir", "system.bar_chart", "Movimiento (PIR) por minuto · 30 min", [
        {"name": "pir_evento", "label": "Movimientos", "color": AMBAR, "settings": copy.deepcopy(ks)},
    ], 15, f, 9, 7, conf={
        "useDashboardTimewindow": False,
        "timewindow": {"selectedTab": 0, "realtime": {"realtimeType": 0, "timewindowMs": 1800000,
                                                      "interval": 60000},
                       "aggregation": {"type": "SUM", "limit": 25000}}})
    _, alb = a.base("system.alarm_widgets.alarms_table")
    al = copy.deepcopy(alb)
    columnas = {"createdTime": "Hora", "originatorDisplayName": "Origen", "type": "Alarma",
                "severity": "Severidad", "status": "Estado"}
    claves_al = [dict(k, label=columnas[k["name"]]) for k in (alb.get("alarmSource") or {}).get("dataKeys", [])
                 if k["name"] in columnas]
    al.update({"title": "Alarmas activas", "showTitle": True, "backgroundColor": TARJETA, "color": TEXTO,
               "titleColor": TENUE, "displayTimewindow": False,
               "widgetStyle": dict(ESTILO_TARJETA), "titleStyle": dict(TITULO_ESTILO), "padding": "8px",
               "alarmSource": {"type": "entity", "entityAliasId": "a-panol", "dataKeys": claves_al},
               "alarmFilterConfig": {"statusList": ["ACTIVE"], "searchPropagatedAlarms": False}})
    al["settings"].update({"alarmsTitle": "Alarmas activas", "allowAssign": False})
    a.widgets["w-alarm"] = {"typeFullFqn": "system.alarm_widgets.alarms_table", "type": "alarm",
                            "sizeX": 9, "sizeY": 5, "config": al, "id": "w-alarm"}
    a.layout["w-alarm"] = {"sizeX": 9, "sizeY": 5, "col": 15, "row": 6}
    return a


def tablero(a, dispositivo):
    return {
        "title": TITULO,
        "configuration": {
            "description": MARCA,
            "entityAliases": {"a-panol": {"id": "a-panol", "alias": "Nodo pañol", "filter": {
                "type": "entityName", "entityType": "DEVICE", "entityNameFilter": dispositivo,
                "resolveMultiple": False}}},
            "widgets": a.widgets,
            "states": {"default": {"name": TITULO, "root": True, "layouts": {"main": {
                "widgets": a.layout,
                "gridSettings": {"columns": 24, "margin": 12, "outerMargin": True, "backgroundColor": FONDO,
                                 "backgroundImageUrl": FONDO_URL, "backgroundSizeMode": "cover",
                                 "color": TEXTO, "mobileAutoFillHeight": False, "mobileRowHeight": 70,
                                 "autoFillHeight": False}}}}},
            "timewindow": {"selectedTab": 0, "realtime": {"realtimeType": 0, "timewindowMs": 6 * 3600 * 1000,
                                                          "interval": 30000},
                           "aggregation": {"type": "NONE", "limit": 5000}},
            "settings": {"stateControllerId": "entity", "showTitle": False, "showDashboardsSelect": False,
                         "showEntitiesSelect": False, "showDashboardTimewindow": True,
                         "showDashboardExport": True, "showDashboardLogo": False, "toolbarAlwaysOpen": False,
                         "titleColor": TEXTO, "hideToolbar": False},
        },
    }


# --- Alarmas (las del motor de sesiones del pañol) -------------------------------------
ALARMAS = [
    # (id, tipo, severidad, clave, se borra sola)
    ("panol-apertura", "Pañol: puerta abierta sin credencial", "CRITICAL", "alarma_apertura_sin_credencial"),
    ("panol-presencia", "Pañol: movimiento sin sesión", "MAJOR", "alarma_presencia_sin_sesion"),
    ("panol-armario", "Pañol: armario abierto sin sesión", "MAJOR", "alarma_armario_sin_sesion"),
    ("panol-sin-gente", "Pañol: puerta abierta sin gente", "WARNING", "alarma_puerta_abierta_sin_gente"),
]


def _cond(tipo, clave, op, valor, vtipo="NUMERIC"):
    return {"condition": [{"key": {"type": tipo, "key": clave}, "valueType": vtipo,
                           "predicate": {"type": vtipo, "operation": op, "value": {"defaultValue": valor}}}],
            "spec": {"type": "SIMPLE"}}


def alarmas(tb):
    """Reglas en el perfil 'panol' (aditivo): cada alarma se crea con su clave
    en 1 y se borra con la clave en 0 (el servidor del pañol avisa cuando se
    resuelve). Más 'nodo sin conexión' por inactividad."""
    perfiles = tb.req("GET", "/api/deviceProfiles?pageSize=100&page=0&textSearch=" + PERFIL)["data"]
    perfil = next((p for p in perfiles if p["name"] == PERFIL), None)
    if perfil is None:
        perfil = tb.req("POST", "/api/deviceProfile", {
            "name": PERFIL, "type": "DEFAULT", "transportType": "DEFAULT",
            "profileData": {"configuration": {"type": "DEFAULT"}, "transportConfiguration": {"type": "DEFAULT"},
                            "provisionConfiguration": {"type": "DISABLED"}, "alarms": []}})
        print(f"perfil '{PERFIL}' creado")
    reglas = perfil["profileData"].get("alarms") or []
    nuevas = [{"id": i, "alarmType": t, "propagate": False,
               "createRules": {sev: {"condition": _cond("TIME_SERIES", k, "GREATER_OR_EQUAL", 1)}},
               "clearRule": {"condition": _cond("TIME_SERIES", k, "EQUAL", 0)}} for i, t, sev, k in ALARMAS]
    nuevas.append({"id": "panol-sin-enlace", "alarmType": "Pañol: nodo sin conexión", "propagate": False,
                   "createRules": {"MAJOR": {"condition": _cond("ATTRIBUTE", "active", "EQUAL", False, "BOOLEAN")}},
                   "clearRule": {"condition": _cond("ATTRIBUTE", "active", "EQUAL", True, "BOOLEAN")}})
    existentes = {r.get("id") for r in reglas}
    agregar = [r for r in nuevas if r["id"] not in existentes]
    if agregar:
        perfil["profileData"]["alarms"] = reglas + agregar
        tb.req("POST", "/api/deviceProfile", perfil)
        print("alarmas agregadas:", ", ".join(r["alarmType"] for r in agregar))
    else:
        print("alarmas: ya estaban")


def nodo_perfil(tb):
    """ThingsBoard 4.3 no trae el nodo "Device Profile" en la cadena raíz y sin
    él las reglas de alarma no se evalúan. Se agrega como primer nodo de la
    cadena raíz de ESTE tenant, con copia previa. Si ya está, no toca nada."""
    raiz = next(r for r in tb.req("GET", "/api/ruleChains?pageSize=50&page=0")["data"] if r.get("root"))
    meta = tb.req("GET", f"/api/ruleChain/{raiz['id']['id']}/metadata")
    if any(n["type"].endswith("TbDeviceProfileNode") for n in meta["nodes"]):
        print("cadena raíz: ya evalúa las alarmas de perfil")
        return
    respaldo = os.path.expanduser(f"~/tb-cadena-raiz-{raiz['id']['id']}-antes.json")
    with open(respaldo, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    meta["nodes"].append({"type": "org.thingsboard.rule.engine.profile.TbDeviceProfileNode",
                          "name": "Alarmas de perfil", "debugMode": False,
                          "configuration": {"persistAlarmRulesState": True, "fetchAlarmRulesStateOnStart": True},
                          "additionalInfo": {"layoutX": 120, "layoutY": 300}})
    meta["connections"].append({"fromIndex": len(meta["nodes"]) - 1, "toIndex": meta["firstNodeIndex"],
                                "type": "Success"})
    meta["firstNodeIndex"] = len(meta["nodes"]) - 1
    tb.req("POST", "/api/ruleChain/metadata", meta)
    print(f"cadena raíz: nodo de alarmas agregado (copia previa en {respaldo})")


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
    ap.add_argument("--alarmas", action="store_true")
    ap.add_argument("--dispositivo", default="panol/LAB01",
                    help="nombre del dispositivo en ThingsBoard (por defecto panol/LAB01)")
    args = ap.parse_args()
    clave = open(os.environ["TB_CLAVE_ARCHIVO"]).read().strip() if os.environ.get("TB_CLAVE_ARCHIVO") \
        else os.environ.get("TB_CLAVE", "")
    tb = TB(os.environ.get("TB_URL", "http://127.0.0.1:18080"), os.environ["TB_USUARIO"], clave)
    t = tablero(armar(tb), args.dispositivo)
    with open(os.path.join(AQUI, "tablero.json"), "w", encoding="utf-8") as f:
        json.dump(t, f, ensure_ascii=False, indent=1)
    print("guardado tablero.json")
    if args.crear:
        crear(tb, t, args.reemplazar)
    if args.alarmas:
        alarmas(tb)
        nodo_perfil(tb)


if __name__ == "__main__":
    main()
