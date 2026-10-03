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

    def rect(self, x, y, w, h, tipo="gris", r=10, grosor=2, guiones=False):
        f, s = C[tipo]
        d = ' stroke-dasharray="7 5"' if guiones else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{f}" stroke="{s}" stroke-width="{grosor}"{d}/>')

    def texto(self, x, y, t, tam=14, peso="normal", color="#212121", ancla="middle", estilo="normal"):
        self.add(f'<text x="{x}" y="{y}" font-family="{FUENTE}" font-size="{tam}" font-weight="{peso}" '
                 f'font-style="{estilo}" fill="{color}" text-anchor="{ancla}">{escape(t)}</text>')

    def texto_fondo(self, x, y, t, tam=14, ancla="start", **kw):
        ancho = len(t) * tam * 0.62 + 16
        x0 = x - 8 if ancla == "start" else x - ancho / 2
        self.add(f'<rect x="{x0}" y="{y - tam - 4}" width="{ancho}" height="{tam + 12}" rx="6" fill="#ffffff"/>')
        self.texto(x, y, t, tam=tam, ancla=ancla, **kw)

    def lineas(self, x, y, lista, tam=13, sep=17, **kw):
        for i, t in enumerate(lista):
            self.texto(x, y + i * sep, t, tam=tam, **kw)

    def caja(self, x, y, w, h, tipo, titulo, lineas=(), tam_t=15, tam=12.5, **kw):
        self.rect(x, y, w, h, tipo, **kw)
        self.texto(x + w / 2, y + 24, titulo, tam=tam_t, peso="bold", color=C[tipo][1])
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
        self.texto(x, y + 5, str(n), tam=13, peso="bold", color="#ffffff")

    def guardar(self, nombre):
        markers = [p for p in self.partes if p.startswith("<marker")]
        resto = [p for p in self.partes if not p.startswith("<marker")]
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" '
               f'height="{self.h}" role="img" aria-label="{escape(self.titulo)}">\n'
               f'<title>{escape(self.titulo)}</title>\n<defs>{"".join(markers)}</defs>\n'
               f'<rect width="100%" height="100%" fill="#ffffff"/>\n' + "\n".join(resto) + "\n</svg>\n")
        with open(os.path.join(AQUI, nombre), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print("escrito", nombre)


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
        s.rect(x, 90, w, 720, tipo, r=14, grosor=1.5, guiones=True)
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
    s.caja(1480, 300, 160, 130, "server", "Grafana", ["consulta y dibuja", "el panel", "(PromQL)"])
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
    s.rect(900, 100, 120, 560, "gris", r=12)
    s.texto(960, 500, "ROUTER", tam=15, peso="bold", color="#616161")
    s.texto(960, 520, "🚪 no deja", tam=12, color="#616161")
    s.texto(960, 536, "entrar", tam=12, color="#616161")
    s.texto(960, 552, "visitas", tam=12, color="#616161")
    # servidor
    s.rect(1080, 100, 390, 560, "server", r=16, grosor=2)
    s.texto(1275, 132, "SERVIDOR homelab-01", tam=17, peso="bold", color=C["server"][1])
    s.caja(1110, 160, 330, 90, "server", "SSH (terminal)", ["pide tu contraseña del aula"], tam=12.5)
    s.caja(1110, 270, 330, 90, "server", "Node-RED de tu equipo", ["sin login: solo por túnel SSH"], tam=12.5)
    s.caja(1110, 380, 330, 90, "server", "Caddy → Grafana del aula", ["HTTPS + login del aula"], tam=12.5)
    s.caja(1110, 520, 330, 110, "server", "mqtt-aula (broker)", ["usuario MQTT del equipo", "solo topics equipo-NN/…"], tam=12.5)
    # personas
    s.caja(40, 170, 260, 150, "vos", "Personas", ["tu compu, la del profe", "", "están en el TAILNET", "(red privada)"])
    s.rect(330, 150, 760, 330, "nube", r=14, guiones=True, grosor=1.5)
    s.texto(590, 178, "TAILSCALE: red privada (VPN) que cruza el router", tam=14, peso="bold", color=C["nube"][1])
    s.flecha(300, 220, 1108, 205, color="#ad1457", etiqueta="1 · Tailscale + SSH (contraseña del aula)", dy=-10)
    s.flecha(300, 250, 1108, 315, color="#ad1457", etiqueta="2 · túnel SSH -L → localhost:1880", dy=24)
    s.flecha(300, 290, 1108, 425, color="#ad1457", etiqueta="3 · HTTPS + login del aula", dy=26)
    # placas
    s.caja(40, 520, 260, 120, "placa", "Placas ESP32", ["no pueden estar en", "el tailnet (muy chicas)"])
    s.caja(420, 530, 300, 100, "nube", "Funnel: el portero", ["…ts.net : 10000", "deja pasar SOLO al broker"], tam=12.5)
    s.flecha(300, 580, 418, 580, color="#2e7d32", etiqueta="MQTT + TLS", dy=-10)
    s.flecha(720, 580, 1108, 575, color="#2e7d32", etiqueta="usuario MQTT del equipo + ACL", dy=-10)
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
            ("Grafana del aula", "tus tableros con historia"),
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
        ("¿Node-RED lo recibe?", "nodo debug · \"connected\" en verde", "Nodo mqtt-broker o topic mal", "mqtt-aula:1883 + usuario MQTT · probá equipo-NN/#"),
        ("¿Aparece en \"Estado actual\"?", "Grafana: dispositivo, magnitud y \"Hace\"", "El mensaje no es número ni estado", "¿coma decimal? ¿unidad pegada?"),
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
        s.caja(90, y, 330, 70, tipo, preg, [como], tam_t=14, tam=12)
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


if __name__ == "__main__":
    ciclo_completo()
    pila_protocolos()
    dos_caminos()
    herramientas()
    arbol_diagnostico()
