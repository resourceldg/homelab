"""Genera las imágenes (SVG) del manual. Todo como código: para corregir una
imagen se edita este archivo y se vuelve a correr.

    python3 docs/handbook/img/generar_imagenes.py

Por qué SVG: se ven nítidas a cualquier tamaño, en GitHub, en el sitio (MkDocs)
y en el PDF, y son texto (se versionan y se revisan como el resto del repo).
"""
import os
from xml.sax.saxutils import escape

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE = "DejaVu Sans, Verdana, Arial, sans-serif"
PROBLEMAS = []

# El Grafana del aula está activo desde el 2026-10-05. Si se apagara: False y
# regenerar, y las imágenes lo marcan "en puesta en marcha".
GRAFANA_AULA_ACTIVO = True
EN_MARCHA = "" if GRAFANA_AULA_ACTIVO else "(en puesta en marcha)"

# Paleta: un color por "mundo", el mismo en todas las imágenes.
C = {
    "placa": ("#e8f5e9", "#2e7d32"),     # verde: dispositivo
    "red": ("#e3f2fd", "#1565c0"),       # azul: redes
    "nube": ("#ede7f6", "#5e35b1"),      # violeta: Tailscale / internet
    "server": ("#fff3e0", "#e65100"),    # naranja: servidor
    "vos": ("#fce4ec", "#ad1457"),       # rosa: la persona
    "gris": ("#f5f5f5", "#616161"),
    "seg": ("#fffde7", "#f9a825"),       # amarillo: seguridad
}


class Svg:
    def __init__(self, ancho, alto, titulo):
        self.w, self.h = ancho, alto
        self.partes = []
        self.titulo = titulo

    def add(self, s):
        self.partes.append(s)

    def rect(self, x, y, w, h, tipo="gris", r=10, grosor=2, guiones=False, zona=False):
        f, s = C[tipo]
        d = ' stroke-dasharray="7 5"' if guiones else ""
        d += ' data-zona="1"' if zona else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{f}" stroke="{s}" stroke-width="{grosor}"{d}/>')

    def texto(self, x, y, t, tam=14, peso="normal", color="#212121", ancla="middle", estilo="normal"):
        self.add(f'<text x="{x}" y="{y}" font-family="{FUENTE}" font-size="{tam}" font-weight="{peso}" '
                 f'font-style="{estilo}" fill="{color}" text-anchor="{ancla}">{escape(t)}</text>')

    def texto_fondo(self, x, y, t, tam=14, ancla="start", **kw):
        ancho = len(t) * tam * 0.62 + 16
        x0 = x - 8 if ancla == "start" else x - ancho / 2
        self.add(f'<rect data-fondo="1" x="{x0}" y="{y - tam - 4}" width="{ancho}" height="{tam + 12}" rx="6" fill="#ffffff"/>')
        self.texto(x, y, t, tam=tam, ancla=ancla, **kw)

    def lineas(self, x, y, lista, tam=13, sep=17, **kw):
        for i, t in enumerate(lista):
            self.texto(x, y + i * sep, t, tam=tam, **kw)

    def caja(self, x, y, w, h, tipo, titulo, lineas=(), tam_t=15, tam=12.5, **kw):
        self.rect(x, y, w, h, tipo, **kw)
        # sin texto debajo, el título va centrado en la caja
        ty = y + 24 if any(lineas) else y + h / 2 + tam_t * 0.35
        self.texto(x + w / 2, ty, titulo, tam=tam_t, peso="bold", color=C[tipo][1])
        self.lineas(x + w / 2, y + 44, lineas, tam=tam, sep=16)

    def flecha(self, x1, y1, x2, y2, color="#424242", grosor=2.5, guiones=False, etiqueta=None,
               dy=-8, tam=12, color_t=None):
        d = ' stroke-dasharray="6 5"' if guiones else ""
        self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{grosor}"{d} '
                 f'marker-end="url(#punta-{color.strip("#")})"/>')
        self._punta(color)
        if etiqueta:
            self.texto((x1 + x2) / 2, (y1 + y2) / 2 + dy, etiqueta, tam=tam, peso="bold",
                       color=color_t or color)

    def _punta(self, color):
        idm = f"punta-{color.strip('#')}"
        if any(idm in p for p in self.partes if p.startswith("<marker")):
            return
        self.partes.insert(0, f'<marker id="{idm}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
                              f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>')

    def numero(self, x, y, n, color="#212121"):
        self.add(f'<circle cx="{x}" cy="{y}" r="13" fill="{color}"/>')
        self.add(f'<text data-num="1" x="{x}" y="{y + 5}" font-family="{FUENTE}" font-size="13" font-weight="bold" '
                 f'fill="#ffffff" text-anchor="middle">{escape(str(n))}</text>')

    def guardar(self, nombre):
        markers = [p for p in self.partes if p.startswith("<marker")]
        resto = [p for p in self.partes if not p.startswith("<marker")]
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" '
               f'height="{self.h}" role="img" aria-label="{escape(self.titulo)}">\n'
               f'<title>{escape(self.titulo)}</title>\n<defs>{"".join(markers)}</defs>\n'
               f'<rect width="100%" height="100%" fill="#ffffff"/>\n' + "\n".join(resto) + "\n</svg>\n")
        with open(os.path.join(AQUI, nombre), "w", encoding="utf-8") as fh:
            fh.write(svg)
        n = len(verificar(svg, nombre))
        print("escrito", nombre, "· sin problemas" if n == 0 else f"· {n} problemas")
        PROBLEMAS.append(n)


# ======================================================================================
# 1. El ciclo completo, ida y vuelta
# ======================================================================================
def ciclo_completo():
    s = Svg(2000, 1020, "El ciclo completo: del sensor a Grafana y de tu botón al actuador")
    s.texto(1000, 40, "El ciclo completo: ida (el dato) y vuelta (la orden)", tam=27, peso="bold")
    s.texto(1000, 66, "Cada flecha dice QUÉ protocolo viaja por ese tramo. Los números y letras marcan el orden del recorrido.",
            tam=14.5, color="#616161")

    # Zonas, con 80 px entre columnas para las etiquetas de protocolo
    zonas = [(20, 290, "placa", "TU PLACA", "ESP32 + sensor / actuador"),
             (390, 240, "red", "WIFI Y ROUTER", "red de la casa o el colegio"),
             (710, 270, "nube", "INTERNET + TAILSCALE", "Funnel: el portero"),
             (1060, 600, "server", "SERVIDOR homelab-01", "contenedores Docker"),
             (1740, 240, "vos", "VOS", "tu compu y tu navegador")]
    for x, w, tipo, t, sub in zonas:
        s.rect(x, 90, w, 720, tipo, r=14, grosor=1.5, guiones=True, zona=True)
        s.texto(x + w / 2, 118, t, tam=15.5, peso="bold", color=C[tipo][1])
        s.texto(x + w / 2, 137, sub, tam=12, color="#616161")

    def etiqueta(x, y, arriba, abajo=None, color="#424242"):
        s.texto_fondo(x, y, arriba, tam=12.5, ancla="middle", peso="bold", color=color)
        if abajo:
            s.texto_fondo(x, y + 44, abajo, tam=11.5, ancla="middle", color=color)

    # ---------------- IDA ----------------
    s.texto_fondo(40, 182, "IDA → el dato viaja del sensor a tu pantalla", tam=17, peso="bold", color="#2e7d32")
    s.caja(40, 200, 250, 66, "placa", "Sensor", ["mide 24,7 °C"])
    s.flecha(165, 266, 165, 298)
    s.texto(175, 287, "señal eléctrica (GPIO)", tam=11, color="#424242", ancla="start")
    s.caja(40, 300, 250, 130, "placa", "Firmware ESP32", ["MicroPython o Arduino", "lee y arma el mensaje:", "equipo-03/sala/", "temperatura = \"24.7\""])
    s.numero(40, 300, 1, "#2e7d32")
    s.caja(410, 300, 200, 130, "red", "WiFi + router", ["WiFi 802.11 · 2.4 GHz", "IP privada 192.168.x", "el router hace NAT", "y sale a internet"])
    s.numero(410, 300, 2, "#1565c0")
    s.flecha(290, 365, 408, 365, color="#2e7d32"); etiqueta(350, 352, "MQTT", "dentro de TLS 🔒", "#2e7d32")
    s.caja(730, 300, 230, 130, "nube", "Tailscale Funnel", ["…tail4eda13.ts.net:10000", "recibe la conexión,", "abre el sobre TLS y", "la pasa por el túnel"])
    s.numero(730, 300, 3, "#5e35b1")
    s.flecha(610, 365, 728, 365, color="#5e35b1"); etiqueta(670, 352, "TCP/IP", "por internet", "#5e35b1")
    s.caja(1080, 300, 150, 130, "server", "mqtt-aula", ["broker MQTT", "Mosquitto 2.0", "valida usuario", "y topic (ACL)"])
    s.numero(1080, 300, 4, "#e65100")
    s.flecha(960, 365, 1078, 365, color="#5e35b1"); etiqueta(1020, 352, "WireGuard", "túnel cifrado", "#5e35b1")
    s.caja(1270, 190, 170, 90, "server", "Telegraf", ["texto \"24.7\"", "→ número 24.7"])
    s.numero(1270, 190, 5, "#e65100")
    s.caja(1270, 340, 170, 90, "server", "VictoriaMetrics", ["guarda 15 días", "(serie temporal)"])
    s.caja(1480, 300, 160, 130, "server", "Grafana", ["consulta y dibuja", "el panel (PromQL)", EN_MARCHA])
    s.numero(1480, 300, 6, "#e65100")
    s.flecha(1230, 330, 1268, 260, color="#e65100"); s.texto(1222, 290, "MQTT", tam=11.5, peso="bold", color="#e65100", ancla="end")
    s.flecha(1355, 280, 1355, 338, color="#e65100"); s.texto(1365, 314, "escribe", tam=11.5, peso="bold", color="#e65100", ancla="start")
    s.flecha(1478, 385, 1442, 385, color="#e65100"); s.texto(1460, 452, "consulta (HTTP)", tam=11.5, peso="bold", color="#e65100")
    s.caja(1760, 300, 200, 130, "vos", "Tu navegador", ["grafana-aula…", "login del aula", "ves el 24,7 en el", "gráfico (≈15 s)"])
    s.numero(1760, 300, 7, "#ad1457")
    s.flecha(1640, 365, 1758, 365, color="#ad1457"); etiqueta(1700, 352, "HTTPS", "Caddy + tailnet", "#ad1457")

    s.add('<line x1="30" y1="485" x2="1970" y2="485" stroke="#bdbdbd" stroke-width="1.5" stroke-dasharray="4 6"/>')

    # ---------------- VUELTA ----------------
    s.texto_fondo(40, 525, "VUELTA ← la orden viaja de tu botón al actuador", tam=17, peso="bold", color="#ad1457")
    s.caja(1760, 550, 200, 130, "vos", "Tu compu", ["clic en un botón del", "dashboard de Node-RED", "(localhost:1880,", "por el túnel SSH)"])
    s.numero(1760, 550, "A", "#ad1457")
    s.caja(1430, 550, 210, 130, "server", "Node-RED", ["de tu equipo:", "recibe el clic y", "publica la orden", "…/enchufe/cmd = ON"])
    s.numero(1430, 550, "B", "#e65100")
    s.flecha(1758, 615, 1642, 615, color="#ad1457"); etiqueta(1700, 602, "SSH (túnel)", "HTTP · WebSocket", "#ad1457")
    s.caja(1080, 550, 150, 130, "server", "mqtt-aula", ["reparte la orden", "a quien está", "suscripto a", "…/enchufe/cmd"])
    s.numero(1080, 550, "C", "#e65100")
    s.flecha(1428, 615, 1232, 615, color="#e65100"); s.texto_fondo(1330, 602, "MQTT", tam=12.5, ancla="middle", peso="bold", color="#e65100")
    s.caja(730, 550, 230, 130, "nube", "Funnel + túnel", ["la placa mantiene", "SU conexión abierta:", "la orden baja por", "ese mismo camino"])
    s.flecha(1078, 615, 962, 615, color="#5e35b1"); etiqueta(1020, 602, "WireGuard", None, "#5e35b1")
    s.caja(410, 550, 200, 130, "red", "Router + WiFi", ["la entrega por la", "conexión que abrió", "la placa (a la placa", "nadie la \"visita\")"])
    s.flecha(728, 615, 612, 615, color="#5e35b1"); etiqueta(670, 602, "TLS + TCP", None, "#5e35b1")
    s.caja(40, 550, 250, 130, "placa", "ESP32: callback", ["llega \"ON\" →", "prende el relé (GPIO)", "y publica el estado:", "…/enchufe/estado = ON"])
    s.numero(40, 550, "D", "#2e7d32")
    s.flecha(408, 615, 292, 615, color="#1565c0"); etiqueta(350, 602, "WiFi", None, "#1565c0")
    s.caja(40, 715, 250, 70, "placa", "Actuador", ["el aparato se prende"])
    s.flecha(165, 680, 165, 713)
    # E: la confirmación sube y llega al Node-RED
    s.add('<path d="M 290 750 C 800 800, 1300 800, 1530 684" fill="none" stroke="#2e7d32" stroke-width="2.5" '
          'stroke-dasharray="8 6" marker-end="url(#punta-2e7d32)"/>')
    s.numero(860, 785, "E", "#2e7d32")
    s.texto_fondo(880, 790, "la confirmación (…/estado = ON) sube por la IDA: Node-RED muestra \"PRENDIDO\" recién cuando la placa confirma",
                  tam=12.5, peso="bold", color="#2e7d32")

    # ---------------- Cómo llega el código a la placa ----------------
    s.rect(20, 840, 1960, 160, "gris", r=12, grosor=1.5)
    s.texto(40, 870, "ANTES DE TODO: cómo llega tu código a la placa (y con qué trabajás vos)", tam=15.5, peso="bold", ancla="start", color="#424242")
    s.caja(40, 890, 260, 90, "vos", "Thonny", ["escribís main.py", "en MicroPython"], tam_t=14, tam=12)
    s.caja(320, 890, 260, 90, "vos", "IDE de Arduino", ["escribís el .ino (C++)", "con PubSubClient"], tam_t=14, tam=12)
    s.flecha(580, 935, 690, 935, color="#424242"); s.texto_fondo(635, 925, "cable USB", tam=12, ancla="middle", peso="bold", color="#424242")
    s.texto(635, 960, "(puerto serie)", tam=11, color="#616161")
    s.caja(695, 890, 260, 90, "placa", "Firmware en la ESP32", ["queda grabado y", "arranca solo al prender"], tam_t=14, tam=12)
    s.texto(1000, 915, "Otras herramientas tuyas, y para qué:", tam=13.5, peso="bold", ancla="start", color="#424242")
    s.texto(1000, 938, "• Tailscale: entrar a la red privada del aula   • Terminal + SSH: entrar al servidor y abrir el túnel", tam=12.5, ancla="start", color="#424242")
    s.texto(1000, 960, "• MQTT Explorer: escuchar tus mensajes en el broker   • Navegador: Node-RED, tu página y Grafana", tam=12.5, ancla="start", color="#424242")
    s.texto(1000, 982, "• Consola de Thonny / Monitor Serie: ver qué hace la placa (WiFi OK, MQTT OK, errores)", tam=12.5, ancla="start", color="#424242")
    s.guardar("ciclo-completo.svg")


# ======================================================================================
# 2. La pila de protocolos
# ======================================================================================
def pila_protocolos():
    s = Svg(1300, 760, "La pila de protocolos: qué trabaja en cada capa")
    s.texto(650, 40, "La pila de protocolos: cada capa con un solo trabajo", tam=25, peso="bold")
    s.texto(650, 66, "Como una carta: escribís el mensaje, lo metés en un sobre cerrado, le ponés la dirección y el correo lo lleva.",
            tam=14, color="#616161")
    capas = [
        ("APLICACIÓN", "qué dice el mensaje", "MQTT (placa ↔ broker) · HTTP/HTTPS (navegador) · SSH (terminal)", "server", "la carta"),
        ("SEGURIDAD", "que nadie lo lea en el camino", "TLS (sobre cerrado) · WireGuard (túnel de Tailscale)", "seg", "el sobre cerrado"),
        ("TRANSPORTE", "que llegue completo y en orden", "TCP (MQTT, HTTPS, SSH) · UDP (WireGuard)", "nube", "el remito con número de piezas"),
        ("RED", "a qué máquina va", "IP: 192.168.x (casa) · 100.110.123.76 (Tailscale) · IP pública", "red", "la dirección del sobre"),
        ("ENLACE / FÍSICO", "cómo viaja por el aire o el cable", "WiFi 802.11 a 2.4 GHz (placa, servidor) · Ethernet (cable)", "placa", "el camión del correo"),
    ]
    y = 100
    for nombre, para, ejemplo, tipo, analogia in capas:
        s.rect(60, y, 1180, 108, tipo, r=12)
        s.texto(90, y + 38, nombre, tam=19, peso="bold", color=C[tipo][1], ancla="start")
        s.texto(90, y + 64, para, tam=13.5, color="#424242", ancla="start", estilo="italic")
        s.texto(420, y + 46, ejemplo, tam=15, color="#212121", ancla="start")
        s.texto(420, y + 76, f"En la carta: {analogia}", tam=13, color="#616161", ancla="start")
        y += 122
    s.texto(650, 735, "Cuando tu ESP32 publica \"24.7\", baja por todas estas capas en la placa y sube por todas en el servidor.",
            tam=14, peso="bold", color="#424242")
    s.guardar("pila-protocolos.svg")


# ======================================================================================
# 3. Los dos caminos: personas y placas
# ======================================================================================
def dos_caminos():
    s = Svg(1500, 700, "Los dos caminos al servidor: personas por Tailscale, placas por Funnel")
    s.texto(750, 40, "Dos caminos al servidor (y por qué son distintos)", tam=25, peso="bold")
    s.texto(750, 66, "El router de la casa no deja entrar a nadie de afuera. Cada uno llega por su propio camino privado.",
            tam=14, color="#616161")
    # router
    s.add('<rect data-atravesable="1" x="900" y="100" width="120" height="560" rx="12" fill="#f5f5f5" stroke="#616161" stroke-width="2"/>')
    s.texto(960, 500, "ROUTER", tam=15, peso="bold", color="#616161")
    s.texto(960, 520, "🚪 no deja", tam=12, color="#616161")
    s.texto(960, 536, "entrar", tam=12, color="#616161")
    s.texto(960, 552, "visitas", tam=12, color="#616161")
    # servidor
    s.rect(1080, 100, 390, 560, "server", r=16, grosor=2)
    s.texto(1275, 132, "SERVIDOR homelab-01", tam=17, peso="bold", color=C["server"][1])
    s.caja(1110, 160, 330, 90, "server", "SSH (terminal)", ["pide tu contraseña del aula"], tam=12.5)
    s.caja(1110, 270, 330, 90, "server", "Node-RED de tu equipo", ["sin login: solo por túnel SSH"], tam=12.5)
    s.caja(1110, 380, 330, 90, "server", "Caddy → Grafana del aula", ["HTTPS + login del aula", EN_MARCHA], tam=12.5)
    s.caja(1110, 520, 330, 110, "server", "mqtt-aula (broker)", ["usuario MQTT del equipo", "solo topics equipo-NN/…"], tam=12.5)
    # personas
    s.caja(40, 170, 260, 150, "vos", "Personas", ["tu compu, la del profe", "", "están en el TAILNET", "(red privada)"])
    s.rect(330, 150, 760, 330, "nube", r=14, guiones=True, grosor=1.5, zona=True)
    s.texto(590, 178, "TAILSCALE: red privada (VPN) que cruza el router", tam=14, peso="bold", color=C["nube"][1])
    s.flecha(300, 220, 1108, 205, color="#ad1457", etiqueta="1 · Tailscale + SSH (contraseña del aula)", dy=-10)
    s.flecha(300, 250, 1108, 315, color="#ad1457", etiqueta="2 · túnel SSH -L → localhost:1880", dy=24)
    s.flecha(300, 290, 1108, 425, color="#ad1457", etiqueta="3 · HTTPS + login del aula", dy=26)
    # placas
    s.caja(40, 520, 260, 120, "placa", "Placas ESP32", ["no pueden estar en", "el tailnet (muy chicas)"])
    s.caja(420, 530, 300, 100, "nube", "Funnel: el portero", ["…ts.net : 10000", "deja pasar SOLO al broker"], tam=12.5)
    s.flecha(300, 580, 418, 580, color="#2e7d32", etiqueta="MQTT + TLS", dy=-10)
    s.flecha(720, 580, 1108, 575, color="#2e7d32")
    s.texto(810, 566, "usuario MQTT", tam=12, peso="bold", color="#2e7d32")
    s.texto(810, 604, "del equipo + ACL", tam=12, peso="bold", color="#2e7d32")
    s.texto(750, 685, "Regla de diseño: lo que no tiene login no se publica; se llega por un túnel que sí tiene login.",
            tam=14, peso="bold", color="#424242")
    s.guardar("dos-caminos.svg")


# ======================================================================================
# 4. Las herramientas (el stack del alumno)
# ======================================================================================
def herramientas():
    s = Svg(1400, 640, "Las herramientas que usás y dónde trabaja cada una")
    s.texto(700, 40, "Tus herramientas: qué es cada una y dónde trabaja", tam=25, peso="bold")
    cols = [
        (40, "placa", "EN LA PLACA", [
            ("ESP32", "la computadora chiquita con WiFi"),
            ("MicroPython 1.29", "Python para placas"),
            ("Arduino (C++)", "la otra forma de programarla"),
            ("umqtt.simple / PubSubClient", "las librerías que hablan MQTT"),
        ]),
        (490, "vos", "EN TU COMPU", [
            ("Thonny", "escribir main.py y ver la consola"),
            ("IDE de Arduino", "escribir y cargar el .ino"),
            ("Tailscale", "entrar a la red privada del aula"),
            ("Terminal + SSH", "entrar al servidor y abrir túneles"),
            ("MQTT Explorer", "escuchar tus mensajes en el broker"),
            ("Navegador", "Node-RED, tu página, Grafana"),
        ]),
        (940, "server", "EN EL SERVIDOR", [
            ("Docker + labctl", "cada servicio en su contenedor"),
            ("mqtt-aula (Mosquitto)", "el broker de todas las placas"),
            ("Node-RED", "tus reglas y tus botones"),
            ("Telegraf + VictoriaMetrics", "traducen y guardan 15 días"),
            ("Grafana del aula", "tus tableros con historia " + EN_MARCHA),
            ("Caddy + Authelia", "la puerta web con login"),
        ]),
    ]
    for x, tipo, titulo, items in cols:
        s.rect(x, 80, 420, 520, tipo, r=16)
        s.texto(x + 210, 114, titulo, tam=18, peso="bold", color=C[tipo][1])
        y = 140
        for nombre, que in items:
            s.add(f'<rect x="{x + 20}" y="{y}" width="380" height="62" rx="9" fill="#ffffff" stroke="{C[tipo][1]}" stroke-width="1.2"/>')
            s.texto(x + 40, y + 26, nombre, tam=15, peso="bold", ancla="start")
            s.texto(x + 40, y + 47, que, tam=12.5, ancla="start", color="#616161")
            y += 73
    s.flecha(488, 300, 462, 300, color="#424242")
    s.texto(474, 330, "USB", tam=11, peso="bold", color="#424242")
    s.flecha(910, 300, 938, 300, color="#424242")
    s.texto(924, 330, "red", tam=11, peso="bold", color="#424242")
    s.guardar("herramientas.svg")


# ======================================================================================
# 5. Árbol de diagnóstico
# ======================================================================================
def arbol_diagnostico():
    pasos = [
        ("¿El sensor mide?", "valor en la consola de Thonny / Monitor Serie", "Cableado, pines o librería del sensor", "es físico: todavía no hay red"),
        ("¿Dice WiFi OK?", "y muestra una IP 192.168.x.x", "Nombre/clave del WiFi · red de 2.4 GHz", "o el hotspot del celular"),
        ("¿Dice MQTT OK?", "la placa entró al broker", "Leé el código de error", "tabla del paso 3 · casos 5, 6 y 7"),
        ("¿Publica sin error?", "print después del publish", "La conexión se corta", "volvé al paso 3"),
        ("¿El topic respeta el contrato?", "equipo-NN/dispositivo/magnitud", "Corregí el topic", "guion en el topic, guion bajo en el usuario"),
        ("¿Lo ves en MQTT Explorer?", "conectado con la clave de tu equipo", "El broker lo descartó", "prefijo de otro equipo, o placa en otro broker"),
        ("¿Node-RED lo recibe? (opcional)", "si no usás Node-RED, seguí al 8", "Nodo mqtt-broker o topic mal", "mqtt-aula:1883 + usuario MQTT · probá equipo-NN/#"),
        ("¿Aparece en \"Estado actual\"?", ("Grafana " + EN_MARCHA) if EN_MARCHA else "Grafana: dispositivo, magnitud y \"Hace\"", "El mensaje no es número ni estado", "¿coma decimal? ¿unidad pegada?"),
        ("¿Tu panel lo muestra?", "Grafana: tu dashboard", "Datasource, etiquetas o rango", "probá la consulta: mqtt_valor"),
    ]
    alto_fila = 98
    s = Svg(1260, 150 + alto_fila * len(pasos) + 70, "Árbol de diagnóstico: no veo mi sensor")
    s.texto(630, 40, "No veo mi sensor: ¿dónde se cortó?", tam=26, peso="bold")
    s.texto(630, 66, "Bajá por la izquierda mientras la respuesta sea SÍ. Al primer NO, ese es tu problema: andá a la derecha.",
            tam=14, color="#616161")
    s.texto(250, 110, "Pregunta (de arriba hacia abajo)", tam=13, peso="bold", color="#2e7d32")
    s.texto(980, 110, "Si la respuesta es NO", tam=13, peso="bold", color="#c62828")
    tramos = [("placa", 0, 4), ("red", 4, 6), ("server", 6, 9)]
    y0 = 128
    for i, (preg, como, falla, donde) in enumerate(pasos):
        y = y0 + i * alto_fila
        tipo = "placa" if i < 5 else ("nube" if i == 5 else "server")
        opcional = i == 6   # Node-RED: para llegar a Grafana NO hace falta
        s.caja(90, y, 330, 70, tipo, preg, [como], tam_t=14, tam=12, guiones=opcional)
        s.numero(90, y, i + 1, C[tipo][1])
        s.add(f'<rect x="760" y="{y}" width="440" height="70" rx="10" fill="#ffebee" stroke="#c62828" stroke-width="2"/>')
        s.texto(980, y + 27, falla, tam=14, peso="bold", color="#c62828")
        s.texto(980, y + 50, donde, tam=12, color="#424242")
        s.flecha(420, y + 35, 758, y + 35, color="#c62828")
        s.texto_fondo(590, y + 30, "NO", tam=13, ancla="middle", peso="bold", color="#c62828")
        if i < len(pasos) - 1:
            s.flecha(255, y + 70, 255, y + alto_fila - 2, color="#2e7d32")
            s.texto(268, y + 88, "sí", tam=12.5, peso="bold", color="#2e7d32", ancla="start")
    y = y0 + len(pasos) * alto_fila
    s.flecha(255, y - alto_fila + 70, 255, y + 6, color="#2e7d32")
    s.add(f'<rect x="90" y="{y + 8}" width="330" height="46" rx="10" fill="#e8f5e9" stroke="#2e7d32" stroke-width="2"/>')
    s.texto(255, y + 37, "✅ Todo el recorrido funciona", tam=15, peso="bold", color="#2e7d32")
    # tramos a la izquierda
    for tipo, a, b in [("placa", 0, 5), ("nube", 5, 6), ("server", 6, 9)]:
        ya, yb = y0 + a * alto_fila, y0 + b * alto_fila - 28
        s.add(f'<line x1="50" y1="{ya}" x2="50" y2="{yb}" stroke="{C[tipo][1]}" stroke-width="6" stroke-linecap="round"/>')
    s.add(f'<text x="34" y="{y0 + 2.5 * alto_fila}" font-family="{FUENTE}" font-size="13" font-weight="bold" fill="{C["placa"][1]}" text-anchor="middle" transform="rotate(-90 34 {y0 + 2.5 * alto_fila})">EN TU PLACA</text>')
    s.add(f'<text x="34" y="{y0 + 7.4 * alto_fila}" font-family="{FUENTE}" font-size="13" font-weight="bold" fill="{C["server"][1]}" text-anchor="middle" transform="rotate(-90 34 {y0 + 7.4 * alto_fila})">EN EL SERVIDOR</text>')
    s.guardar("arbol-diagnostico.svg")


# ======================================================================================
# 6. Árbol de accesos: no puedo entrar
# ======================================================================================
def arbol_accesos():
    s = Svg(1300, 760, "No puedo entrar: primero la red, después el camino según a qué querés entrar")
    s.texto(650, 40, "No puedo entrar: ¿qué puerta está cerrada?", tam=26, peso="bold")
    s.texto(650, 66, "Primero, siempre, la red. Después el camino se divide: la terminal y Node-RED pasan por SSH; Grafana no.",
            tam=14, color="#616161")
    s.texto(650, 86, "Flecha verde = sí · flecha roja = no / error", tam=12.5, peso="bold", color="#424242")

    def falla(x, y, w, titulo, detalle):
        s.add(f'<rect x="{x}" y="{y}" width="{w}" height="62" rx="10" fill="#ffebee" stroke="#c62828" stroke-width="2"/>')
        s.texto(x + w / 2, y + 25, titulo, tam=13.5, peso="bold", color="#c62828")
        s.texto(x + w / 2, y + 46, detalle, tam=11.5, color="#424242")

    # 1 · red
    s.caja(470, 100, 360, 72, "nube", "¿Aparece homelab-01?", ["tailscale status (en tu compu)"], tam_t=14.5, tam=12)
    s.numero(470, 100, 1, C["nube"][1])
    falla(930, 105, 340, "Tailscale apagado o sin aprobar", "o en tu propio tailnet: logout + up")
    s.flecha(830, 136, 928, 136, color="#c62828"); s.texto_fondo(879, 129, "NO", tam=12.5, ancla="middle", peso="bold", color="#c62828")
    # bifurcación
    s.caja(500, 215, 300, 60, "gris", "¿A qué querés entrar?", [], tam_t=14.5)
    s.flecha(650, 172, 650, 213, color="#2e7d32"); s.texto(662, 199, "sí", tam=12.5, peso="bold", color="#2e7d32", ancla="start")

    # rama izquierda: terminal / Node-RED (SSH)
    s.texto(30, 318, "TERMINAL o TU NODE-RED (con SSH)", tam=14, peso="bold", color=C["vos"][1], ancla="start")
    s.flecha(560, 275, 300, 343, color="#424242")
    s.caja(110, 345, 380, 72, "vos", "¿Entra el ssh?", ["ssh tu-usuario@100.110.123.76"], tam_t=14.5, tam=12)
    s.numero(110, 345, 2, C["vos"][1])
    falla(30, 450, 260, "timed out", "servidor caído: esperá y avisá")
    falla(310, 450, 260, "Permission denied", "contraseña del aula equivocada")
    s.flecha(220, 417, 160, 448, color="#c62828")
    s.flecha(380, 417, 440, 448, color="#c62828")
    s.caja(110, 560, 380, 72, "vos", "¿Abre localhost:1880?", ["con la ventana del túnel abierta"], tam_t=14.5, tam=12)
    s.numero(110, 560, 3, C["vos"][1])
    s.flecha(300, 417, 300, 558, color="#2e7d32"); s.texto(312, 540, "sí, entra", tam=12, peso="bold", color="#2e7d32", ancla="start")
    falla(110, 670, 380, "Túnel con puertos de OTRO equipo", "o se cerró la ventana del SSH")
    s.flecha(300, 632, 300, 668, color="#c62828")

    # rama derecha: Grafana (sin SSH)
    s.texto(1270, 318, "GRAFANA DEL AULA (sin SSH: navegador)", tam=14, peso="bold", color=C["server"][1], ancla="end")
    s.flecha(740, 275, 1000, 343, color="#424242")
    s.caja(810, 345, 380, 72, "server", "¿Abre grafana-aula… ?", ["en el navegador · " + (EN_MARCHA or "login del aula")], tam_t=14.5, tam=12)
    s.numero(810, 345, 2, C["server"][1])
    falla(700, 450, 290, "No carga", ("en puesta en marcha, o sin Tailscale" if EN_MARCHA else "¿Tailscale prendido?"))
    falla(1010, 450, 270, "Vuelve al login", "usuario/contraseña del aula")
    s.flecha(920, 417, 845, 448, color="#c62828")
    s.flecha(1080, 417, 1145, 448, color="#c62828")
    falla(810, 560, 380, "Entra, pero no ves tu carpeta", "no estás en el roster del equipo: avisá")
    s.flecha(1000, 417, 1000, 558, color="#c62828")
    s.guardar("arbol-accesos.svg")


# ======================================================================================
# 7. Mapa de servicios (cap. 5): quién depende de quién
# ======================================================================================
def mapa_servicios():
    s = Svg(1400, 860, "Mapa de servicios del servidor: quién depende de quién")
    s.texto(700, 38, "El mapa de servicios: quién depende de quién", tam=25, peso="bold")
    s.texto(700, 62, "Cada flecha va del que pide al que responde. Si se cae una caja, se rompe todo lo que le apunta.",
            tam=14, color="#616161")
    # zonas
    s.rect(20, 85, 1360, 165, "nube", r=14, grosor=1.5, guiones=True, zona=True)
    s.texto(40, 108, "PUERTAS DE ENTRADA", tam=14, peso="bold", color=C["nube"][1], ancla="start")
    s.rect(20, 280, 840, 530, "placa", r=14, grosor=1.5, guiones=True, zona=True)
    s.texto(40, 303, "PARA EL AULA", tam=14, peso="bold", color=C["placa"][1], ancla="start")
    s.rect(880, 280, 500, 530, "server", r=14, grosor=1.5, guiones=True, zona=True)
    s.texto(1360, 303, "PARA EL OPERADOR", tam=14, peso="bold", color=C["server"][1], ancla="end")
    # puertas
    s.caja(60, 130, 260, 80, "nube", "Funnel", ["entrada por internet", "(las placas)"], tam=12)
    s.caja(420, 130, 220, 80, "nube", "Tailscale", ["red privada", "(las personas)"], tam=12)
    s.caja(740, 130, 220, 80, "nube", "Caddy", ["puerta web", "con HTTPS"], tam=12)
    s.caja(1060, 130, 280, 80, "nube", "Authelia", ["login único", "(¿quién sos?)"], tam=12)
    s.flecha(640, 170, 738, 170, color="#5e35b1")
    s.flecha(960, 170, 1058, 170, color="#5e35b1")
    s.texto_fondo(1009, 160, "pregunta", tam=11.5, ancla="middle", peso="bold", color="#5e35b1")
    # aula
    s.caja(60, 330, 200, 80, "placa", "mqtt-aula", ["broker MQTT"], tam=12)
    s.caja(320, 330, 180, 80, "placa", "Telegraf", ["traduce"], tam=12)
    s.caja(560, 330, 220, 80, "placa", "VictoriaMetrics", ["guarda 15 días"], tam=12)
    s.caja(560, 470, 240, 80, "placa", "Grafana del aula", [EN_MARCHA or "tableros por equipo"], tam=12)
    s.flecha(318, 370, 262, 370, color="#2e7d32")      # Telegraf le pide al broker (lee)
    s.texto_fondo(290, 360, "lee", tam=11.5, ancla="middle", peso="bold", color="#2e7d32")
    s.flecha(500, 370, 558, 370, color="#2e7d32")      # y escribe en VictoriaMetrics
    s.texto_fondo(529, 360, "escribe", tam=11.5, ancla="middle", peso="bold", color="#2e7d32")
    s.flecha(670, 468, 670, 412, color="#2e7d32")
    s.texto(682, 445, "consulta", tam=11.5, peso="bold", color="#2e7d32", ancla="start")
    s.caja(60, 640, 200, 80, "placa", "labctld", ["levanta los stacks"], tam=12)
    s.caja(320, 640, 200, 80, "placa", "Stacks de equipos", ["Node-RED, nginx"], tam=12)
    s.flecha(260, 680, 318, 680, color="#2e7d32")
    s.flecha(360, 638, 200, 412, color="#2e7d32")
    s.texto(250, 540, "MQTT", tam=11.5, peso="bold", color="#2e7d32", ancla="end")
    for i, (n, d) in enumerate([("PostgreSQL", "base de datos"), ("Redis", "memoria rápida"), ("Mailpit", "correo de prueba")]):
        y = 600 + i * 68
        s.caja(600, y, 220, 56, "placa", n, [], tam_t=13.5)
        s.flecha(520, 680, 598, y + 28, color="#2e7d32", grosor=2)
    # operador
    s.caja(910, 330, 200, 80, "server", "Homepage", ["página de inicio"], tam=12)
    s.caja(1150, 330, 210, 80, "server", "Grafana", ["de operación"], tam=12)
    s.caja(1150, 470, 210, 70, "server", "Prometheus", ["lee los medidores"], tam=12)
    s.caja(910, 470, 200, 70, "server", "Loki + Alloy", ["logs, a pedido"], tam=12)
    s.caja(1080, 620, 135, 60, "server", "node-exporter", [], tam_t=12.5)
    s.caja(1235, 620, 125, 60, "server", "cAdvisor", [], tam_t=12.5)
    s.flecha(1255, 410, 1255, 468, color="#e65100")
    s.flecha(1150, 400, 1080, 468, color="#e65100")
    s.flecha(1200, 540, 1160, 618, color="#e65100")
    s.flecha(1300, 540, 1300, 618, color="#e65100")
    # cruces entre zonas
    s.flecha(190, 210, 160, 328, color="#5e35b1")
    s.texto(186, 268, "MQTT + TLS", tam=11.5, peso="bold", color="#5e35b1", ancla="start")
    s.flecha(790, 210, 790, 468, color="#5e35b1")
    s.flecha(880, 210, 990, 328, color="#5e35b1")
    s.flecha(950, 210, 1240, 328, color="#5e35b1")
    s.texto(700, 842, "Caddy reparte los pedidos web (después de preguntarle a Authelia); Funnel deja pasar solo al broker.",
            tam=13, peso="bold", color="#424242")
    s.guardar("mapa-servicios.svg")



# ======================================================================================
# Verificador: que ningún texto se salga de su caja ni pise a otro, y que las flechas
# no atraviesen textos ni cajas ajenas. Mide con la fuente real (DejaVu), porque con
# letra chica un desborde de 3 px no se ve a ojo pero sí impreso.
# ======================================================================================
import re as _re

try:
    from PIL import ImageFont as _IF
    _FUENTES = {}

    def _ancho(t, tam, negrita):
        clave = (round(tam * 4), negrita)
        if clave not in _FUENTES:
            arch = "DejaVuSans-Bold.ttf" if negrita else "DejaVuSans.ttf"
            _FUENTES[clave] = _IF.truetype("/usr/share/fonts/truetype/dejavu/" + arch, max(1, round(tam * 4)))
        return _FUENTES[clave].getlength(t) / 4
except ImportError:  # sin PIL: estimación gruesa
    def _ancho(t, tam, negrita):
        return len(t) * tam * (0.62 if negrita else 0.56)


def _desescapar(t):
    return t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')


def verificar(svg_texto, nombre):
    problemas = []
    rects, textos, flechas = [], [], []
    for m in _re.finditer(r'<rect (?!width="100%")([^>]*)/>', svg_texto):
        a = dict(_re.findall(r'([\w-]+)="([^"]*)"', m.group(1)))
        if "x" not in a:
            continue
        rects.append(dict(x=float(a["x"]), y=float(a["y"]), w=float(a["width"]), h=float(a["height"]),
                          zona="data-zona" in a, fondo="data-fondo" in a,
                          atravesable="data-atravesable" in a))
    for m in _re.finditer(r'<text ([^>]*)>([^<]*)</text>', svg_texto):
        a = dict(_re.findall(r'([\w-]+)="([^"]*)"', m.group(1)))
        if "transform" in a or "data-num" in a:
            continue
        t, tam = _desescapar(m.group(2)), float(a["font-size"])
        neg = a.get("font-weight") == "bold"
        w = _ancho(t, tam, neg)
        x, y = float(a["x"]), float(a["y"])
        x0 = {"middle": x - w / 2, "end": x - w}.get(a.get("text-anchor", "start"), x)
        textos.append(dict(t=t, x0=x0, x1=x0 + w, y0=y - tam * 0.78, y1=y + tam * 0.22))
    for m in _re.finditer(r'<line ([^>]*marker-end[^>]*)/>', svg_texto):
        a = dict(_re.findall(r'([\w-]+)="([^"]*)"', m.group(1)))
        flechas.append(tuple(float(a[k]) for k in ("x1", "y1", "x2", "y2")))

    cajas = [r for r in rects if not r["zona"] and not r["fondo"]]
    W, H = map(float, _re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg_texto).groups())

    for t in textos:
        if t["x0"] < 2 or t["x1"] > W - 2 or t["y0"] < 0 or t["y1"] > H:
            problemas.append(f'se sale de la imagen: "{t["t"]}"')
        cx, cy = (t["x0"] + t["x1"]) / 2, (t["y0"] + t["y1"]) / 2
        dentro = [r for r in cajas if r["x"] <= cx <= r["x"] + r["w"] and r["y"] <= cy <= r["y"] + r["h"]]
        if dentro:
            r = min(dentro, key=lambda r: r["w"] * r["h"])
            margen = 5
            if t["x0"] < r["x"] + margen - 0.5 or t["x1"] > r["x"] + r["w"] - margen + 0.5:
                problemas.append(f'desborda su caja ({t["x1"] - t["x0"]:.0f} px en {r["w"]:.0f}): "{t["t"]}"')
    # Texto que cruza el borde punteado de una zona: se lee mal, salvo que tenga
    # un fondo blanco debajo (texto_fondo), puesto justamente para eso.
    zonas = [r for r in rects if r["zona"]]
    fondos = [r for r in rects if r["fondo"]]
    for t in textos:
        cx, cy = (t["x0"] + t["x1"]) / 2, (t["y0"] + t["y1"]) / 2
        if any(f["x"] <= cx <= f["x"] + f["w"] and f["y"] <= cy <= f["y"] + f["h"] for f in fondos):
            continue
        for z in zonas:
            if not (z["y"] < cy < z["y"] + z["h"]):
                continue
            for borde in (z["x"], z["x"] + z["w"]):
                if t["x0"] + 1 < borde < t["x1"] - 1:
                    problemas.append(f'cruza el borde de una zona: "{t["t"]}"')
    for i, a in enumerate(textos):
        for b in textos[i + 1:]:
            if a["x0"] < b["x1"] - 1 and b["x0"] < a["x1"] - 1 and a["y0"] < b["y1"] - 1 and b["y0"] < a["y1"] - 1:
                problemas.append(f'se pisan: "{a["t"]}" y "{b["t"]}"')

    def corta(x1, y1, x2, y2, r, pad=0):
        """¿El segmento atraviesa el rectángulo r (con margen pad)?"""
        rx0, ry0, rx1, ry1 = r[0] - pad, r[1] - pad, r[2] + pad, r[3] + pad
        for k in range(1, 40):
            px, py = x1 + (x2 - x1) * k / 40, y1 + (y2 - y1) * k / 40
            if rx0 < px < rx1 and ry0 < py < ry1:
                return True
        return False

    def en_borde(px, py, r, tol=6):
        x0, y0, x1, y1 = r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]
        cerca_x = x0 - tol <= px <= x1 + tol
        cerca_y = y0 - tol <= py <= y1 + tol
        return cerca_x and cerca_y and (min(abs(px - x0), abs(px - x1)) <= tol or min(abs(py - y0), abs(py - y1)) <= tol)

    for (x1, y1, x2, y2) in flechas:
        ini = [r for r in cajas if en_borde(x1, y1, r)]
        fin = [r for r in cajas if en_borde(x2, y2, r)]
        if not ini:
            problemas.append(f"flecha que no sale de ninguna caja: ({x1:.0f},{y1:.0f})→({x2:.0f},{y2:.0f})")
        if not fin:
            problemas.append(f"flecha que no llega a ninguna caja: ({x1:.0f},{y1:.0f})→({x2:.0f},{y2:.0f})")
        def contiene(r, px, py):
            return r["x"] < px < r["x"] + r["w"] and r["y"] < py < r["y"] + r["h"]
        for r in cajas:
            # el origen, el destino, un recuadro que CONTIENE una punta (la flecha entra
            # a buscar algo de adentro) y lo marcado como atravesable (el router que el
            # túnel cruza) no cuentan
            if r in ini or r in fin or r["atravesable"] or contiene(r, x1, y1) or contiene(r, x2, y2):
                continue
            if corta(x1, y1, x2, y2, (r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"])):
                problemas.append(f"flecha ({x1:.0f},{y1:.0f})→({x2:.0f},{y2:.0f}) atraviesa una caja en ({r['x']:.0f},{r['y']:.0f})")
        for t in textos:
            if corta(x1, y1, x2, y2, (t["x0"], t["y0"], t["x1"], t["y1"]), pad=1):
                problemas.append(f'flecha ({x1:.0f},{y1:.0f})→({x2:.0f},{y2:.0f}) tacha el texto "{t["t"]}"')
    for p in problemas:
        print(f"  ✗ {nombre}: {p}")
    return problemas


if __name__ == "__main__":
    ciclo_completo()
    pila_protocolos()
    dos_caminos()
    herramientas()
    arbol_diagnostico()
    arbol_accesos()
    mapa_servicios()
    if sum(PROBLEMAS):
        raise SystemExit(f"{sum(PROBLEMAS)} problemas de diseño: revisá la lista de arriba.")
