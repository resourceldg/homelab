"""Pruebas del guardián de red (vigia-red) con comandos simulados — corre en CI.

    py.test -v tests/test_vigia_red.py

El guardián puede REINICIAR el servidor: por eso se prueba su máquina de estados
sin tocar nada real. Los comandos que cambian cosas (nmcli, systemctl, tailscale)
y los que miran la red (ping, ip) se reemplazan por scripts que anotan lo que se
les pidió y responden lo que cada prueba necesita.
"""
import json
import os
import stat
import subprocess
import time

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "ansible", "roles", "vigia_red", "files", "vigia-red.sh")


def _stub(path, body):
    with open(path, "w") as fh:
        fh.write("#!/usr/bin/env bash\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)


@pytest.fixture
def entorno(tmp_path):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    llamadas = tmp_path / "llamadas.log"
    alcanzables = tmp_path / "alcanzables"          # IPs que "responden" al ping
    alcanzables.write_text("192.168.8.1\n1.1.1.1\n")
    ts_estado = tmp_path / "ts_estado"
    ts_estado.write_text("Running")
    _stub(bin_ / "ping", f'ip="${{@: -1}}"; grep -qx "$ip" {alcanzables}\n')
    _stub(bin_ / "ip", 'echo "default via 192.168.8.1 dev wlx0 proto dhcp"\n')
    _stub(bin_ / "logger", "exit 0\n")
    _stub(bin_ / "nmcli", f'echo "nmcli $*" >> {llamadas}\n'
          'case "$*" in\n'
          '  *"DEVICE,TYPE device"*) echo "wlx0:wifi"; echo "enp2s0:ethernet";;\n'
          '  *"DEVICE,STATE device"*) echo "wlx0:disconnected";;\n'
          'esac\n')
    _stub(bin_ / "systemctl", f'echo "systemctl $*" >> {llamadas}\n')
    _stub(bin_ / "tailscale", f'echo "{{\\"BackendState\\": \\"$(cat {ts_estado})\\"}}"\n')
    uptime = tmp_path / "uptime"
    uptime.write_text("36000.0 1.0\n")              # 10 h encendido
    estado = tmp_path / "estado"

    def correr(veces=1):
        env = dict(os.environ, PATH=f"{bin_}:{os.environ['PATH']}",
                   VIGIA_ESTADO_DIR=str(estado), VIGIA_LOG=str(tmp_path / "vigia.log"),
                   VIGIA_SYSFS=str(tmp_path / "sys"), VIGIA_UPTIME=str(uptime),
                   VIGIA_ESPERA="0")
        for _ in range(veces):
            subprocess.run(["bash", SCRIPT], env=env, check=True, timeout=30)
        return llamadas.read_text() if llamadas.exists() else ""

    def log():
        p = tmp_path / "vigia.log"
        return p.read_text() if p.exists() else ""

    return dict(correr=correr, log=log, alcanzables=alcanzables, ts=ts_estado,
                uptime=uptime, estado=estado)


def test_red_sana_no_toca_nada_y_deja_latido(entorno):
    llamadas = entorno["correr"](3)
    assert "systemctl" not in llamadas and "reconnect" not in llamadas
    assert (entorno["estado"] / "latido").exists()


def test_internet_caido_afuera_no_toca_nuestro_enlace(entorno):
    entorno["alcanzables"].write_text("192.168.8.1\n")   # router sí, internet no
    llamadas = entorno["correr"](20)
    assert "systemctl" not in llamadas and "reconnect" not in llamadas
    assert "AFUERA" in entorno["log"]()


def test_escalera_en_el_minuto_correcto(entorno):
    entorno["alcanzables"].write_text("")                # ni el router responde
    llamadas = entorno["correr"](1)
    assert "device connect" not in llamadas               # todavía no: espera 2 min
    llamadas = entorno["correr"](1)                       # minuto 2
    # La placa está 'disconnected' (como al arrancar): busca redes y conecta a la mejor.
    assert "device wifi rescan ifname wlx0" in llamadas and "device connect wlx0" in llamadas
    llamadas = entorno["correr"](4)                       # minuto 6
    assert "systemctl restart NetworkManager" in llamadas
    log = entorno["log"]()
    assert "PASO 1 (2 min)" in log and "PASO 2 (6 min)" in log


def test_reinicio_ultimo_recurso_con_limites(entorno):
    entorno["alcanzables"].write_text("")
    llamadas = entorno["correr"](29)
    assert "reboot" not in llamadas
    llamadas = entorno["correr"](1)                       # minuto 30
    assert llamadas.count("systemctl reboot") == 1
    # Volvió a caerse enseguida: NO reinicia de nuevo (uno cada 6 h como mucho).
    (entorno["estado"] / "minutos-sin-router").write_text("0")
    llamadas = entorno["correr"](40)
    assert llamadas.count("systemctl reboot") == 1
    assert "REINICIO EVITADO" in entorno["log"]()


def test_no_reinicia_recien_encendido(entorno):
    entorno["alcanzables"].write_text("")
    entorno["uptime"].write_text("600.0 1.0\n")           # 10 minutos encendido
    llamadas = entorno["correr"](35)
    assert "reboot" not in llamadas


def test_recuperacion_se_anota_y_resetea(entorno):
    entorno["alcanzables"].write_text("")
    entorno["correr"](5)
    entorno["alcanzables"].write_text("192.168.8.1\n1.1.1.1\n")
    entorno["correr"](1)
    assert "RECUPERADO" in entorno["log"]() and "tras 5 min" in entorno["log"]()
    assert (entorno["estado"] / "minutos-sin-router").read_text().strip() == "0"


def test_tailscale_caido_con_internet_se_reinicia(entorno):
    entorno["ts"].write_text("NeedsLogin")
    llamadas = entorno["correr"](2)
    assert "restart tailscaled" not in llamadas
    llamadas = entorno["correr"](1)                       # minuto 3
    assert llamadas.count("restart tailscaled") == 1
    llamadas = entorno["correr"](5)                       # no lo martilla cada minuto
    assert llamadas.count("restart tailscaled") == 1


def test_conectado_pero_sin_router_reconecta(entorno, tmp_path):
    """Si NM dice 'connected' pero el router no responde, se reconecta (no se busca otra red)."""
    entorno["alcanzables"].write_text("")
    nm = tmp_path / "bin" / "nmcli"
    nm.write_text(nm.read_text().replace('echo "wlx0:disconnected"', 'echo "wlx0:connected"'))
    llamadas = entorno["correr"](2)
    assert "device reconnect wlx0" in llamadas and "device connect wlx0" not in llamadas

