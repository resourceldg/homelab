"""Puente mqtt-aula -> ThingsBoard (tb-puente).

Lee lo que publican los equipos en el broker del aula y lo reenvía a
ThingsBoard por la API de gateway MQTT (un solo token para todos los
dispositivos). Las ESP32 no cambian nada: mismo broker, mismos topics.

Contrato de topics y payloads: el MISMO que aplica Telegraf para Grafana
(compose/aula-iot/telegraf/mqtt.star), así los dos tableros muestran lo mismo:
    topic    <equipo>/<dispositivo>/<magnitud>[/<sub>...]
    payload  un número, una palabra de estado ("ON", "abierto"...) o un JSON
             plano con números ({"temp": 23.5, "hum": 60})

En ThingsBoard queda un dispositivo "<equipo>/<dispositivo>" cuyo tipo
(perfil) es el equipo, con una serie por magnitud.

Por qué no hay bucles: la cuenta del broker del aula es de SOLO LECTURA (ACL)
y el puente publica en otro broker (el transporte MQTT interno de ThingsBoard).
"""

import json
import logging
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ESTADOS = {
    "on": 1, "off": 0,
    "true": 1, "false": 0,
    "si": 1, "sí": 1, "no": 0,
    "encendido": 1, "prendido": 1, "apagado": 0,
    "abierto": 1, "cerrado": 0,
    "online": 1, "offline": 0,
    "alto": 1, "bajo": 0,
    "activo": 1, "inactivo": 0,
    "detectado": 1, "libre": 0,
}

# Topes contra una placa que publica topics inventados en un bucle (idénticos
# a los de mqtt.star).
MAX_NOMBRE = 40
MAX_CAMPOS_JSON = 20

log = logging.getLogger("tb-puente")


def limpio(texto):
    """Deja solo letras, números y guion bajo (igual que mqtt.star)."""
    out = []
    for c in texto:
        if c.isalnum() or c == "_":
            out.append(c)
        elif c in "-/. ":
            out.append("_")
    return "".join(out).lower()[:MAX_NOMBRE]


def a_numero(v):
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        try:
            n = float(s)
        except ValueError:
            e = ESTADOS.get(s.lower())
            return float(e) if e is not None else None
        # float() acepta "nan" e "inf"; mqtt.star no, y un tablero tampoco.
        return n if n == n and n not in (float("inf"), float("-inf")) else None
    return None


def convertir(topic, payload):
    """(equipo, dispositivo, {magnitud: valor}) o None si no hay qué graficar."""
    partes = topic.split("/")
    if len(partes) < 3:
        return None
    equipo = partes[0]
    dispositivo = limpio(partes[1])
    magnitud = limpio("_".join(partes[2:]))
    if not equipo or not dispositivo or not magnitud:
        return None

    try:
        crudo = payload.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None

    valores = {}
    if crudo.startswith("{"):
        try:
            datos = json.loads(crudo)
        except ValueError:
            return None
        if not isinstance(datos, dict):
            return None
        for clave, val in datos.items():
            num = a_numero(val)
            nombre = limpio(magnitud + "_" + str(clave))
            if num is not None and nombre:
                valores[nombre] = num
            if len(valores) >= MAX_CAMPOS_JSON:
                break
    else:
        num = a_numero(crudo)
        if num is not None:
            valores[magnitud] = num

    return (equipo, dispositivo, valores) if valores else None


class Estado:
    """Contadores para /metrics (Prometheus) y /salud (healthcheck)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.mensajes = {"enviado": 0, "descartado": 0, "retenido": 0,
                         "sin_cupo": 0, "cola_llena": 0}
        self.conectado = {"aula": 0}
        self.ultimo = 0.0

    def sumar(self, resultado):
        with self.lock:
            self.mensajes[resultado] += 1

    def metricas(self, dispositivos):
        with self.lock:
            lineas = [
                "# HELP tb_puente_mensajes_total Mensajes del aula por resultado.",
                "# TYPE tb_puente_mensajes_total counter",
            ]
            for k, v in self.mensajes.items():
                lineas.append(f'tb_puente_mensajes_total{{resultado="{k}"}} {v}')
            lineas += [
                "# HELP tb_puente_conectado 1 si la conexión al broker está arriba.",
                "# TYPE tb_puente_conectado gauge",
            ]
            for k, v in self.conectado.items():
                lineas.append(f'tb_puente_conectado{{lado="{k}"}} {v}')
            lineas += [
                "# HELP tb_puente_dispositivos Dispositivos distintos vistos.",
                "# TYPE tb_puente_dispositivos gauge",
                f"tb_puente_dispositivos {dispositivos}",
                "# HELP tb_puente_ultimo_mensaje_segundos Hora (unix) del último envío.",
                "# TYPE tb_puente_ultimo_mensaje_segundos gauge",
                f"tb_puente_ultimo_mensaje_segundos {self.ultimo}",
            ]
            return "\n".join(lineas) + "\n"


def leer_secreto(nombre):
    """Valor de VAR o del archivo en VAR_FILE (secretos de Compose)."""
    ruta = os.environ.get(nombre + "_FILE")
    if ruta:
        with open(ruta, encoding="utf-8") as f:
            return f.read().strip()
    valor = os.environ.get(nombre, "")
    if not valor:
        sys.exit(f"Falta {nombre} (o {nombre}_FILE)")
    return valor


def main():
    import paho.mqtt.client as mqtt  # solo en el contenedor; los tests no lo necesitan

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(message)s")

    topics = [t.strip() for t in os.environ["TOPICS"].split(",") if t.strip()]
    max_disp = int(os.environ.get("MAX_DISPOSITIVOS", "200"))
    cola_max = int(os.environ.get("COLA_MAX", "10000"))
    estado = Estado()
    vistos = set()          # dispositivos aceptados (tope MAX_DISPOSITIVOS)
    avisado_tope = [False]

    # --- Lado ThingsBoard (destinos) -------------------------------------
    # Siempre el tenant del aula (TB_TOKEN). Además, cada equipo que es
    # administrador de su propio tenant recibe SOLO lo suyo, con el token del
    # gateway de ese tenant (TB_TOKENS_EQUIPOS="equipo-01=tok,equipo-03=tok").
    class Destino:
        def __init__(self, nombre, token):
            self.nombre = nombre
            self.conectados = set()   # dispositivos anunciados en esta conexión
            sufijo = "" if nombre == "tb" else "-" + nombre
            self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="tb-puente" + sufijo)
            self.c.username_pw_set(token)
            # QoS 1 + cola acotada: si TB se reinicia, paho guarda lo pendiente y
            # lo manda al reconectar. Pasado el tope se descarta (y se cuenta).
            self.c.max_queued_messages_set(cola_max)
            self.c.reconnect_delay_set(1, 30)
            self.c.on_connect = self.al_conectar
            self.c.on_disconnect = self.al_desconectar
            estado.conectado[nombre] = 0

        def al_conectar(self, c, u, flags, rc, props):
            estado.conectado[self.nombre] = 1 if rc == 0 else 0
            self.conectados.clear()   # re-anunciar dispositivos tras reconectar
            log.info("ThingsBoard (%s): conectado (%s)", self.nombre, rc)

        def al_desconectar(self, c, u, flags, rc, props):
            estado.conectado[self.nombre] = 0
            log.warning("ThingsBoard (%s): desconectado (%s)", self.nombre, rc)

        def enviar(self, nombre, equipo, valores):
            if nombre not in self.conectados:
                self.c.publish("v1/gateway/connect",
                               json.dumps({"device": nombre, "type": equipo}), qos=1)
                self.conectados.add(nombre)
            cuerpo = {nombre: [{"ts": int(time.time() * 1000), "values": valores}]}
            return self.c.publish("v1/gateway/telemetry", json.dumps(cuerpo), qos=1)

    principal = Destino("tb", leer_secreto("TB_TOKEN"))
    por_equipo = {}
    for par in os.environ.get("TB_TOKENS_EQUIPOS", "").split(","):
        if "=" in par:
            equipo, token = par.split("=", 1)
            por_equipo[equipo.strip()] = Destino(equipo.strip(), token.strip())
    destinos = [principal] + list(por_equipo.values())

    # --- Lado aula (origen) -----------------------------------------------
    aula = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="tb-puente",
                       clean_session=False)
    aula.username_pw_set(os.environ["AULA_USER"], leer_secreto("AULA_PASS"))
    aula.reconnect_delay_set(1, 30)

    def aula_on_connect(c, u, flags, rc, props):
        estado.conectado["aula"] = 1 if rc == 0 else 0
        if rc == 0:
            # QoS 1 con sesión persistente: si el puente se reinicia, el broker
            # guarda lo que llegue con QoS 1 mientras tanto.
            c.subscribe([(t, 1) for t in topics])
            log.info("Aula: conectado, suscripto a %s", ", ".join(topics))
        else:
            log.error("Aula: conexión rechazada (%s)", rc)

    def aula_on_disconnect(c, u, flags, rc, props):
        estado.conectado["aula"] = 0
        log.warning("Aula: desconectado (%s)", rc)

    def aula_on_message(c, u, msg):
        # Los retenidos son estado viejo (p. ej. el último comando a un LED):
        # se reenviarían con hora nueva en cada reconexión. Se saltean.
        if msg.retain:
            estado.sumar("retenido")
            return
        r = convertir(msg.topic, msg.payload)
        if r is None:
            estado.sumar("descartado")
            return
        equipo, dispositivo, valores = r
        nombre = f"{equipo}/{dispositivo}"
        if nombre not in vistos:
            if len(vistos) >= max_disp:
                estado.sumar("sin_cupo")
                if not avisado_tope[0]:
                    log.warning("Tope de %d dispositivos: se ignoran los nuevos", max_disp)
                    avisado_tope[0] = True
                return
            vistos.add(nombre)
        info = principal.enviar(nombre, equipo, valores)
        if equipo in por_equipo:
            por_equipo[equipo].enviar(nombre, equipo, valores)
        if info.rc == mqtt.MQTT_ERR_QUEUE_SIZE:
            estado.sumar("cola_llena")
        else:
            estado.sumar("enviado")
            estado.ultimo = time.time()

    aula.on_connect = aula_on_connect
    aula.on_disconnect = aula_on_disconnect
    aula.on_message = aula_on_message

    # --- /metrics y /salud --------------------------------------------------
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/metrics":
                cuerpo = estado.metricas(len(vistos)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
            elif self.path == "/salud":
                ok = estado.conectado["aula"] == 1
                cuerpo = b"ok\n" if ok else b"sin aula\n"
                self.send_response(200 if ok else 503)
            else:
                cuerpo = b"no\n"
                self.send_response(404)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def log_message(self, *a):
            pass

    http = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("METRICS_PORT", "9101"))), Handler)
    threading.Thread(target=http.serve_forever, daemon=True).start()

    for d in destinos:
        d.c.connect_async(os.environ.get("TB_HOST", "thingsboard"), int(os.environ.get("TB_PORT", "1883")))
        d.c.loop_start()
    aula.connect_async(os.environ.get("AULA_HOST", "mqtt-aula"), int(os.environ.get("AULA_PORT", "1883")))
    aula.loop_start()

    parar = threading.Event()
    signal.signal(signal.SIGTERM, lambda *a: parar.set())
    signal.signal(signal.SIGINT, lambda *a: parar.set())
    parar.wait()
    log.info("Cerrando")
    aula.loop_stop()
    aula.disconnect()
    for d in destinos:
        d.c.loop_stop()
        d.c.disconnect()
    http.shutdown()


if __name__ == "__main__":
    main()
