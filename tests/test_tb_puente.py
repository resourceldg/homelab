"""Contrato del puente mqtt-aula -> ThingsBoard — Python puro, corre en CI.

    py.test -v tests/test_tb_puente.py

El puente tiene que convertir los mensajes EXACTAMENTE como Telegraf
(compose/aula-iot/telegraf/mqtt.star): si no, el mismo sensor mostraría una
cosa en Grafana y otra en ThingsBoard. Estos casos fijan ese contrato.
"""
import importlib.util
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")
PUENTE = os.path.join(ROOT, "compose", "thingsboard", "puente", "puente.py")
STAR = os.path.join(ROOT, "compose", "aula-iot", "telegraf", "mqtt.star")

_spec = importlib.util.spec_from_file_location("puente", PUENTE)
puente = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(puente)
convertir = puente.convertir


def test_numero_simple():
    assert convertir("equipo-01/estacion/temperatura", b"23.5") == (
        "equipo-01", "estacion", {"temperatura": 23.5})


def test_subtopics_se_unen_con_guion_bajo():
    assert convertir("equipo-01/estacion/aire/co2", b" 412 ") == (
        "equipo-01", "estacion", {"aire_co2": 412.0})


def test_palabra_de_estado():
    assert convertir("equipo-02/puerta/estado", b"Abierto")[2] == {"estado": 1.0}
    assert convertir("equipo-02/led/estado", b"OFF")[2] == {"estado": 0.0}


def test_json_plano():
    r = convertir("equipo-03/dht/lectura", b'{"temp": 21, "hum": "60", "ok": true, "txt": "hola"}')
    assert r == ("equipo-03", "dht", {"lectura_temp": 21.0, "lectura_hum": 60.0, "lectura_ok": 1.0})


def test_json_acotado_a_20_campos():
    cuerpo = "{" + ",".join(f'"c{i}": {i}' for i in range(50)) + "}"
    assert len(convertir("e/d/m", cuerpo.encode())[2]) == puente.MAX_CAMPOS_JSON


def test_descarta_lo_que_no_se_grafica():
    assert convertir("equipo-01/led", b"1") is None              # menos de 3 niveles
    assert convertir("equipo-01/estacion/temp", b"hola") is None  # texto libre
    assert convertir("equipo-01/estacion/temp", b"nan") is None
    assert convertir("equipo-01/estacion/temp", b"{roto") is None
    assert convertir("equipo-01/estacion/temp", b"[1, 2]") is None
    assert convertir("equipo-01/estacion/temp", b"\xff\xfe") is None
    assert convertir("equipo-01//temp", b"1") is None


def test_nombres_limpios_y_acotados():
    r = convertir("equipo-01/Mi Placa.v2/" + "x" * 80, b"1")
    assert r[1] == "mi_placa_v2"
    assert len(next(iter(r[2]))) == puente.MAX_NOMBRE


def test_mismos_estados_y_topes_que_telegraf():
    """Si alguien suma una palabra de estado en mqtt.star, que no se olvide acá."""
    star = open(STAR, encoding="utf-8").read()
    bloque = re.search(r"ESTADOS = \{(.*?)\}", star, re.S).group(1)
    star_estados = dict((k, int(v)) for k, v in re.findall(r'"([^"]+)":\s*(\d)', bloque))
    assert star_estados == puente.ESTADOS
    assert f"MAX_NOMBRE = {puente.MAX_NOMBRE}" in star
    assert f"MAX_CAMPOS_JSON = {puente.MAX_CAMPOS_JSON}" in star
