"""Static checks del broker del aula (mqtt-aula) — Python puro, corre en CI.

    py.test -v tests/test_shared_services_stack.py

Cuida lo que se rompe en silencio: que el broker quede anónimo (sale a internet
por Funnel), que publique fuera de loopback, que la ACL deje a un equipo en el
árbol de otro, y que el tag de imagen del compose y del rol diverjan (el rol usa
esa imagen para hashear las contraseñas).
"""
import os
import re

import yaml
from jinja2 import Environment

ROOT = os.path.join(os.path.dirname(__file__), "..")
COMPOSE = os.path.join(ROOT, "compose", "shared-data", "compose.yml")
MOSQ_CONF = os.path.join(ROOT, "compose", "shared-data", "mosquitto", "mosquitto.conf")
ROLE = os.path.join(ROOT, "ansible", "roles", "shared_services")
LABCTLD = os.path.join(ROOT, "ansible", "roles", "labctl", "files", "labctld")


def _read(path):
    with open(path) as fh:
        return fh.read()


def _broker():
    return yaml.safe_load(_read(COMPOSE))["services"]["mqtt-aula"]


def test_broker_is_not_anonymous():
    conf = _read(MOSQ_CONF)
    assert re.search(r"^allow_anonymous\s+false$", conf, re.M), "el broker quedó anónimo"
    assert re.search(r"^password_file\s+\S+$", conf, re.M), "sin password_file"
    assert re.search(r"^acl_file\s+\S+$", conf, re.M), "sin acl_file"


def test_broker_publishes_only_on_loopback():
    for port in _broker().get("ports", []):
        assert str(port).startswith("127.0.0.1:"), f"mqtt-aula publica fuera de loopback: {port}"


def test_mosquitto_image_matches_the_role():
    compose_tag = _broker()["image"]
    role_tag = re.search(r'shared_mqtt_image:\s*"([^"]+)"', _read(os.path.join(ROLE, "defaults", "main.yml"))).group(1)
    assert compose_tag == role_tag


def test_acl_confines_each_team_to_its_tree():
    tpl = Environment().from_string(_read(os.path.join(ROLE, "templates", "mqtt-aula-acl.j2")))
    acl = tpl.render(ansible_managed="x", classroom_teams=[{"name": "equipo-01"}, {"name": "equipo-03"}])
    rules = re.findall(r"^user (\S+)\ntopic readwrite (\S+)$", acl, re.M)
    assert rules == [("equipo_01", "equipo-01/#"), ("equipo_03", "equipo-03/#")]
    assert "topic readwrite #" not in acl


def test_labctld_attaches_the_broker_to_team_networks():
    assert '"mqtt-aula"' in re.search(r"INFRA_CONTAINERS = \(([^)]*)\)", _read(LABCTLD)).group(1)
