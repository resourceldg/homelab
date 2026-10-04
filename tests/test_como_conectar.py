"""Unit tests for scripts/como-conectar.sh — the connection-path advisor.

No host and no real server: the reachable case is proved against a throwaway
socket on 127.0.0.1, and the unreachable case against TEST-NET-1 (RFC 5737),
so this runs in CI and offline.

    py.test -v tests/test_como_conectar.py
"""
import os
import socket
import subprocess
import threading

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "como-conectar.sh")
# RFC 5737 documentation range: guaranteed not to be routed anywhere.
INALCANZABLE = "192.0.2.1"


def _run(args=(), env=None, timeout=90):
    e = dict(os.environ)
    # Keep every probe off the real network unless a test opts in.
    e.update({
        "HOMELAB_NOMBRE": INALCANZABLE,
        "HOMELAB_IP_TAILNET": INALCANZABLE,
        "HOMELAB_IPS_LAN": INALCANZABLE,
    })
    e.update(env or {})
    return subprocess.run(
        ["bash", SCRIPT, *args],
        capture_output=True, text=True, env=e, timeout=timeout,
    )


class _Listener:
    """A socket that accepts and immediately closes, like a live sshd port."""

    def __enter__(self):
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(8)
        self.port = self.srv.getsockname()[1]
        self.stop = False
        self.th = threading.Thread(target=self._serve, daemon=True)
        self.th.start()
        return self

    def _serve(self):
        self.srv.settimeout(0.4)
        while not self.stop:
            try:
                self.srv.accept()[0].close()
            except OSError:
                pass

    def __exit__(self, *_):
        self.stop = True
        self.srv.close()


def test_sintaxis_valida():
    assert subprocess.run(["bash", "-n", SCRIPT]).returncode == 0


def test_ayuda_sale_bien():
    r = _run(["--ayuda"])
    assert r.returncode == 0
    assert "EN TU COMPUTADORA" in r.stdout


def test_opcion_desconocida_es_error_de_uso():
    r = _run(["--chirimbolo"])
    assert r.returncode == 2
    assert "opción desconocida" in r.stderr


def test_sin_caminos_falla_y_lo_explica():
    r = _run(["jessi"])
    assert r.returncode == 1
    assert "Ningún camino funciona" in r.stdout


def test_recomienda_el_camino_que_responde():
    with _Listener() as lis:
        r = _run(["jessi"], env={
            "HOMELAB_IPS_LAN": "127.0.0.1",
            "HOMELAB_PUERTO": str(lis.port),
        })
    assert r.returncode == 0
    # sin equipo no hay túnel: no sabemos a qué Node-RED llevarlo
    assert "ssh jessi@127.0.0.1" in r.stdout
    assert "-L" not in r.stdout
    assert "--equipo" in r.stdout


def test_equipo_arma_el_tunel_con_sus_puertos():
    with _Listener() as lis:
        r = _run(["jessi", "--equipo", "equipo-04"], env={
            "HOMELAB_IPS_LAN": "127.0.0.1",
            "HOMELAB_PUERTO": str(lis.port),
        })
    assert r.returncode == 0
    assert "ssh -L 1880:localhost:1884 -L 8080:localhost:8084 jessi@127.0.0.1" in r.stdout
    # MQTT va por el Funnel, nunca por el túnel
    assert "1883" not in r.stdout


def test_equipo_sin_web_solo_lleva_node_red():
    with _Listener() as lis:
        r = _run(["jessi", "--equipo=1"], env={
            "HOMELAB_IPS_LAN": "127.0.0.1",
            "HOMELAB_PUERTO": str(lis.port),
        })
    assert r.returncode == 0
    assert "ssh -L 1880:localhost:1880 jessi@127.0.0.1" in r.stdout
    assert "8080" not in r.stdout


def test_equipo_desconocido_es_error_de_uso():
    r = _run(["jessi", "--equipo", "99"])
    assert r.returncode == 2
    assert "equipo «99»" in r.stderr


def test_puerto_cerrado_se_distingue_de_host_muerto():
    """Si el host responde pero el puerto no, el mensaje culpa al firewall."""
    r = _run(["jessi"], env={"HOMELAB_IPS_LAN": "127.0.0.1", "HOMELAB_PUERTO": "9"})
    assert r.returncode == 1
    assert "puerto 9 está cerrado" in r.stdout
    assert "firewall" in r.stdout
