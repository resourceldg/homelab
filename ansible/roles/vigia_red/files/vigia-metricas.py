#!/usr/bin/env python3
"""Métricas de caídas de homelab-01 para Prometheus.

node-exporter corre en un contenedor y no ve el WiFi del host ni el diario de
systemd. Este script (lo corre un timer cada minuto) junta esas pistas y las
deja en un archivo .prom que node-exporter publica con su colector "textfile".
Así Grafana muestra POR QUÉ se cayó, no solo QUE se cayó.

Fuentes (todas locales, solo lectura):
  /var/log/homelab/vigia-red.log*        cortes de red y reinicios del vigía
  /var/log/homelab/arranques/*.txt       resumen de cada arranque (causa)
  journalctl                             pérdidas de señal WiFi (BEACON-LOSS)
  /sys/class/watchdog/watchdog0/state    watchdog de hardware
"""
import datetime as dt
import glob
import gzip
import os
import re
import subprocess
import tempfile

SALIDA = os.environ.get("VIGIA_METRICAS", "/var/lib/node_exporter/textfile/homelab.prom")
LOG = "/var/log/homelab/vigia-red.log"
ARRANQUES = "/var/log/homelab/arranques"
DIAS = int(os.environ.get("VIGIA_RETENCION_DIAS", "20"))

AHORA = dt.datetime.now()
DESDE = AHORA - dt.timedelta(days=DIAS)
lineas = []


def metrica(nombre, valor, ayuda=None, **etiquetas):
    if ayuda:
        lineas.append(f"# HELP {nombre} {ayuda}")
        lineas.append(f"# TYPE {nombre} gauge")
    if etiquetas:
        e = ",".join(f'{k}="{v}"' for k, v in etiquetas.items())
        lineas.append(f"{nombre}{{{e}}} {valor}")
    else:
        lineas.append(f"{nombre} {valor}")


def correr(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def leer(ruta):
    abrir = gzip.open if ruta.endswith(".gz") else open
    try:
        with abrir(ruta, "rt", errors="replace") as f:
            return f.read().splitlines()
    except OSError:
        return []


def epoch(t):
    return int(t.timestamp())


# --- Estado actual ---------------------------------------------------------
ruta = correr("ip", "-4", "route", "show", "default").split()
gw = ruta[ruta.index("via") + 1] if "via" in ruta else ""
red_ok = 1 if gw and correr("ping", "-c1", "-W2", gw).count(" 0% packet loss") else 0
metrica("homelab_red_ok", red_ok, "1 si el router responde ahora")

# (La señal en dBm no se publica: el driver del RTL8187B informa valores imposibles.)

beacon = correr("journalctl", "--since", "-24h", "-t", "wpa_supplicant", "-q", "--no-pager", "-o", "cat")
metrica("homelab_wifi_beacon_loss_24h", beacon.count("BEACON-LOSS"),
        "Veces que el WiFi dejó de escuchar al router en 24 h")

try:
    wd = open("/sys/class/watchdog/watchdog0/state").read().strip() == "active"
except OSError:
    wd = False
metrica("homelab_watchdog_activo", int(wd), "1 si el watchdog de hardware está armado")

boton = "ignore" in correr("busctl", "get-property", "org.freedesktop.login1", "/org/freedesktop/login1",
                           "org.freedesktop.login1.Manager", "HandlePowerKey")
metrica("homelab_boton_ignorado", int(boton), "1 si el botón de encendido NO apaga el servidor")

aide = correr("systemctl", "is-active", "dailyaidecheck.service").strip() == "active"
metrica("homelab_aide_corriendo", int(aide), "1 mientras corre el escaneo de AIDE (calienta la CPU)")

# --- Cortes de red (log del vigía, incluidos los rotados) ------------------
re_linea = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) (.*)$")
re_recup = re.compile(r"tras (\d+) min sin red \(desde (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\)")
cortes, reinicios_vigia = [], []
for ruta_log in sorted(glob.glob(LOG + "*")):
    for linea in leer(ruta_log):
        m = re_linea.match(linea)
        if not m:
            continue
        cuando = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        if cuando < DESDE:
            continue
        texto = m.group(2)
        r = re_recup.search(texto)
        if texto.startswith("RECUPERADO") and r:
            cortes.append((dt.datetime.strptime(r.group(2), "%Y-%m-%d %H:%M:%S"), int(r.group(1))))
        elif texto.startswith("REINICIO (último recurso)"):
            reinicios_vigia.append(cuando)
cortes = sorted(set(cortes))

metrica("homelab_corte_red_minutos", 0, "Cada corte de red: etiqueta desde = inicio, valor = minutos sin red")
lineas.pop()
for inicio, minutos in cortes:
    metrica("homelab_corte_red_minutos", minutos, desde=inicio.strftime("%Y-%m-%d %H:%M"))
for horas, sufijo in ((24, "24h"), (24 * 7, "7d")):
    lim = AHORA - dt.timedelta(hours=horas)
    sel = [mi for ini, mi in cortes if ini >= lim]
    metrica(f"homelab_cortes_red_{sufijo}", len(sel), f"Cortes de red en {sufijo}")
    metrica(f"homelab_minutos_sin_red_{sufijo}", sum(sel), f"Minutos sin red en {sufijo}")
metrica("homelab_reinicios_vigia_7d",
        sum(1 for t in reinicios_vigia if t >= AHORA - dt.timedelta(days=7)),
        "Reinicios ordenados por el vigía (último recurso sin red) en 7 días")

# --- Causa de cada arranque (resúmenes del post-mortem) ---------------------
CAUSAS = {
    "watchdog": "Se colgó y el watchdog lo reinició",
    "boton": "Alguien apretó el botón de encendido",
    "de_golpe": "Apagado de golpe: luz, fuente o cuelgue",
    "vigia_sin_red": "El vigía reinició (sin red mucho tiempo)",
    "actualizacion": "Reinicio por actualización automática",
    "ordenado": "Apagado ordenado (manual o programado)",
}


def seccion(texto, titulo):
    """Líneas de una sección '== <titulo>' del resumen (hasta la próxima '==')."""
    for bloque in texto.split("\n== "):
        if bloque.lstrip("= ").startswith(titulo):
            return [ln for ln in bloque.splitlines()[1:] if ln.strip()]
    return []


def boton_antes(texto):
    """Resúmenes viejos no traen la línea del botón: se busca en el diario."""
    m = re.search(r"Último registro previo: (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", texto)
    if not m:
        return False
    fin = dt.datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
    salida = correr("journalctl", "-q", "--no-pager", "-o", "cat", "-t", "systemd-logind",
                    "--since", str(fin - dt.timedelta(minutes=5)), "--until", str(fin + dt.timedelta(seconds=5)))
    return "Power key pressed" in salida


def causa(texto):
    if "EL WATCHDOG DE HARDWARE REINICIÓ" in texto:
        return "watchdog"
    if "Se APRETÓ EL BOTÓN" in texto:
        return "boton"
    if "DE GOLPE" in texto:
        return "de_golpe"
    if "REINICIO (último recurso)" in texto:
        return "vigia_sin_red"
    if boton_antes(texto):
        return "boton"
    if seccion(texto, "Pedidos de reinicio de la actualización automática"):
        return "actualizacion"
    return "ordenado"


metrica("homelab_arranque", 0, "Cada arranque: valor = hora (epoch); causa = cómo terminó el anterior")
lineas.pop()
conteo = dict.fromkeys(CAUSAS, 0)
for ruta_arr in sorted(glob.glob(os.path.join(ARRANQUES, "*.txt"))):
    m = re.match(r"(\d{8})-(\d{6})\.txt$", os.path.basename(ruta_arr))
    if not m:
        continue
    cuando = dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    if cuando < DESDE:
        continue
    c = causa("\n".join(leer(ruta_arr)))
    conteo[c] += 1
    metrica("homelab_arranque", epoch(cuando), arranque=cuando.strftime("%Y-%m-%d %H:%M"),
            causa=c, descripcion=CAUSAS[c])
metrica("homelab_arranques_por_causa", 0, f"Arranques de los últimos {DIAS} días según la causa")
lineas.pop()
for c, n in conteo.items():
    metrica("homelab_arranques_por_causa", n, causa=c, descripcion=CAUSAS[c])

metrica("homelab_metricas_actualizadas", epoch(AHORA), "Última corrida de este colector (epoch)")

# Escritura atómica: node-exporter nunca lee un archivo a medias.
os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(SALIDA), prefix=".homelab.")
with os.fdopen(fd, "w") as f:
    f.write("\n".join(lineas) + "\n")
os.chmod(tmp, 0o644)
os.replace(tmp, SALIDA)
