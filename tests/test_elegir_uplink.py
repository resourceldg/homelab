"""Unit tests for scripts/elegir-uplink.sh — the server-side uplink chooser.

The decision logic is proved against stubbed `nmcli`, `ip` and `ping` on PATH,
so this runs in CI with no server, no root and no real network.

    py.test -v tests/test_elegir_uplink.py
"""
import os
import stat
import subprocess

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "elegir-uplink.sh")

# device -> (type, has_link, loss%, rtt, connection profile)
ETH_SANO = ("ethernet", True, "0", "0.4", "Wired connection 1")
WIFI_MALO = ("wifi", True, "60", "12.0", "TOTOLINK_N600R 1")


def _escribir(path, cuerpo):
    with open(path, "w") as fh:
        fh.write(cuerpo)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _stubs(tmp_path, devices, prioridad="0"):
    """Build fake nmcli/ip/ping reflecting `devices` = {name: tupla}."""
    d = tmp_path / "bin"
    d.mkdir()

    estado = "\n".join(f"{n}:{v[0]}:connected" for n, v in devices.items())
    conns = "\n".join(f"{v[4]}:{prioridad}" for v in devices.values())
    casos_conn = "\n".join(
        f'    {n}) echo "{v[4]}";;' for n, v in devices.items()
    )
    _escribir(d / "nmcli", f"""#!/usr/bin/env bash
args="$*"
case "$args" in
  *"DEVICE,TYPE,STATE device status"*) printf '%s\\n' "{estado}" ;;
  *"NAME,AUTOCONNECT-PRIORITY connection show"*) printf '%s\\n' "{conns}" ;;
  *"GENERAL.CONNECTION device show"*)
    case "${{@: -1}}" in
{casos_conn}
    esac ;;
  *"GENERAL.STATE device show"*) echo "GENERAL.STATE:100 (connected)" ;;
  *) : ;;
esac
""")

    # Only linked devices get LOWER_UP and a default route.
    rutas = "\n".join(
        f"default via 192.168.{i}.1 dev {n} proto dhcp metric {100 + i}"
        for i, (n, v) in enumerate(devices.items()) if v[1]
    )
    casos_link = "\n".join(
        f'      {n}) echo "9: {n}: <BROADCAST,MULTICAST{",UP,LOWER_UP" if v[1] else ""}>";;'
        for n, v in devices.items()
    )
    _escribir(d / "ip", f"""#!/usr/bin/env bash
case "$*" in
  *"route show default"*) printf '%s\\n' "{rutas}" ;;
  *"link show"*)
    case "${{@: -1}}" in
{casos_link}
    esac ;;
esac
""")

    casos_ping = "\n".join(
        f'  {n}) perdida="{v[2]}"; rtt="{v[3]}";;' for n, v in devices.items()
    )
    _escribir(d / "ping", f"""#!/usr/bin/env bash
iface=""
while [ $# -gt 0 ]; do
  [ "$1" = "-I" ] && iface="$2"
  shift
done
case "$iface" in
{casos_ping}
  *) perdida="100"; rtt="0";;
esac
echo "--- ping statistics ---"
echo "20 packets transmitted, 8 received, ${{perdida}}% packet loss, time 100ms"
echo "rtt min/avg/max/mdev = 0.100/${{rtt}}/20.000/1.500 ms"
""")
    # `sudo -n <cmd>`: en el test simplemente ejecuta lo que le pasan.
    _escribir(d / "sudo", """#!/usr/bin/env bash
[ "$1" = "-n" ] && shift
exec "$@"
""")
    return d


def _run(tmp_path, devices, args=(), prioridad="0"):
    binp = _stubs(tmp_path, devices, prioridad)
    env = dict(os.environ, PATH=f"{binp}:{os.environ['PATH']}")
    return subprocess.run(
        ["bash", SCRIPT, "--pings", "20", *args],
        capture_output=True, text=True, env=env, timeout=60,
    )


def test_sintaxis_valida():
    assert subprocess.run(["bash", "-n", SCRIPT]).returncode == 0


def test_ayuda_dice_donde_se_corre():
    r = subprocess.run(["bash", SCRIPT, "--ayuda"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "EN EL SERVIDOR" in r.stdout


@pytest.mark.parametrize("flag,code", [("--chirimbolo", 2), ("--pings=2", 2)])
def test_argumentos_invalidos(flag, code):
    r = subprocess.run(["bash", SCRIPT, flag], capture_output=True, text=True)
    assert r.returncode == code


def test_pings_con_espacio_en_cualquier_posicion(tmp_path):
    """`--pings N` toma el N aunque no sea la primera opción (antes no lo hacía)."""
    r = _run(tmp_path, {"eth0": ETH_SANO}, args=("--pings", "7"))
    assert r.returncode == 0, r.stderr
    assert "(7 pings" in r.stdout


def test_elige_el_de_menor_perdida(tmp_path):
    r = _run(tmp_path, {"eth0": ETH_SANO, "wlan0": WIFI_MALO})
    assert r.returncode == 0
    assert "El mejor uplink es: eth0" in r.stdout
    assert "degradado" in r.stdout          # el wifi queda marcado
    assert "pérdida 0%" in r.stdout


def test_ignora_la_interfaz_sin_enlace(tmp_path):
    muerta = ("ethernet", False, "0", "0.1", "Wired connection 1")
    r = _run(tmp_path, {"eth0": muerta, "wlan0": WIFI_MALO})
    assert r.returncode == 0
    assert "sin enlace físico" in r.stdout
    assert "El mejor uplink es: wlan0" in r.stdout
    assert "el mejor de los malos" in r.stdout


def test_avisa_prioridad_saboteada(tmp_path):
    r = _run(tmp_path, {"eth0": ETH_SANO}, prioridad="-999")
    assert "prioridad -999" in r.stdout
    assert "nunca va a ganar" in r.stdout


def test_sin_aplicar_no_modifica_nada(tmp_path):
    r = _run(tmp_path, {"eth0": ETH_SANO, "wlan0": WIFI_MALO})
    assert "solo un diagnóstico" in r.stdout
    assert "métrica" not in r.stdout


def test_aplicar_ordena_por_ranking(tmp_path):
    r = _run(tmp_path, {"eth0": ETH_SANO, "wlan0": WIFI_MALO}, args=("--aplicar",))
    assert r.returncode == 0
    # el ganador recibe la métrica más baja (= ruta preferida)
    assert "Wired connection 1 → métrica 100" in r.stdout
    assert "TOTOLINK_N600R 1 → métrica 200" in r.stdout
