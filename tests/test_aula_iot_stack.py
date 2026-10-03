"""Static checks de la capa aula-iot — Python puro, corre en CI (sin host).

    py.test -v tests/test_aula_iot_stack.py

Cuida lo que se rompe en silencio: que Grafana confíe en el header de usuario
desde cualquier red (suplantación), que una imagen quede en :latest, que un
equipo quede sin datasource filtrado, y que el broker le dé a los servicios de
lectura permiso de escribir.
"""
import json
import os
import re

import yaml
from jinja2 import Environment

ROOT = os.path.join(os.path.dirname(__file__), "..")
COMPOSE = os.path.join(ROOT, "compose", "aula-iot", "compose.yml")
ROLE = os.path.join(ROOT, "ansible", "roles", "aula_iot")
DOCKER_TASKS = os.path.join(ROOT, "ansible", "roles", "docker", "tasks", "main.yml")
PROXY = os.path.join(ROOT, "compose", "proxy", "compose.yml")
SHARED = os.path.join(ROOT, "ansible", "roles", "shared_services")
AUTHELIA = os.path.join(ROOT, "ansible", "roles", "authelia", "templates", "configuration.yml.j2")
TEAMS = [{"name": "equipo-01", "members": ["a"]}, {"name": "equipo-03", "members": ["b"]}]


def _read(path):
    with open(path) as fh:
        return fh.read()


def _services():
    return yaml.safe_load(_read(COMPOSE))["services"]


def test_images_are_pinned():
    for name, svc in _services().items():
        assert not svc["image"].endswith(":latest") and ":" in svc["image"], f"{name} sin versión fija"


def test_ports_only_on_loopback():
    for name, svc in _services().items():
        for port in svc.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{name} publica fuera de loopback: {port}"


def test_grafana_trusts_user_header_only_from_the_proxy_network():
    env = _services()["grafana"]["environment"]
    assert env["GF_AUTH_PROXY_ENABLED"] == "true"
    assert env["GF_AUTH_PROXY_WHITELIST"] == "${AULA_PROXY_SUBNET}"
    assert env["GF_AUTH_ANONYMOUS_ENABLED"] == "false"
    assert env["GF_AUTH_DISABLE_LOGIN_FORM"] == "true"
    assert "edge" not in _services()["grafana"]["networks"], "grafana-aula no puede estar en edge"
    subnet = yaml.safe_load(_read(os.path.join(ROLE, "defaults", "main.yml")))["aula_iot_proxy_subnet"]
    assert subnet in _read(DOCKER_TASKS), "la red grafana-aula-proxy no tiene el rango de la whitelist"
    assert "grafana-aula-proxy" in yaml.safe_load(_read(PROXY))["services"]["caddy"]["networks"]


def test_every_team_gets_a_filtered_datasource():
    tpl = Environment(trim_blocks=True, lstrip_blocks=True).from_string(
        _read(os.path.join(ROLE, "templates", "datasources.yml.j2")))
    doc = yaml.safe_load(tpl.render(ansible_managed="x", classroom_teams=TEAMS))
    by_uid = {d["uid"]: d for d in doc["datasources"]}
    for team in TEAMS:
        ds = by_uid[f"mqtt-{team['name']}"]
        assert ds["jsonData"]["customQueryParameters"] == f"extra_label=equipo={team['name']}"
    assert "customQueryParameters" not in by_uid["mqtt-aula"]["jsonData"]


def test_starter_dashboard_uses_the_team_datasource_only():
    raw = _read(os.path.join(ROLE, "files", "equipo-dashboard.json"))
    body = json.loads(raw.replace("__EQUIPO__", "equipo-07"))
    uids = set(re.findall(r'"uid": "(mqtt-[^"]+)"', json.dumps(body)))
    assert uids == {"mqtt-equipo-07"}, uids
    assert body["folderUid"] == "equipo-07" and body["overwrite"] is False


def test_telegraf_subscribes_one_topic_per_team():
    tpl = Environment(trim_blocks=True, lstrip_blocks=True).from_string(
        _read(os.path.join(ROLE, "templates", "telegraf.conf.j2")))
    conf = tpl.render(ansible_managed="x", classroom_teams=TEAMS)
    assert re.findall(r'"(equipo-\d+)/#"', conf) == ["equipo-01", "equipo-03"]
    assert '"#"' not in conf


def test_service_users_are_read_only_on_the_broker():
    tpl = Environment(trim_blocks=True, lstrip_blocks=True).from_string(
        _read(os.path.join(SHARED, "templates", "mqtt-aula-acl.j2")))
    svc = yaml.safe_load(_read(os.path.join(SHARED, "defaults", "main.yml")))["shared_mqtt_service_users"]
    acl = tpl.render(ansible_managed="x", classroom_teams=TEAMS, shared_mqtt_service_users=svc)
    bloque = acl[acl.index("user aula-telegraf"):]
    assert "readwrite" not in bloque and "topic write" not in bloque
    assert "topic read equipo-01/#" in bloque and "topic read $SYS/#" in bloque


def test_students_cannot_open_the_operations_grafana():
    conf = _read(AUTHELIA)
    regla = conf[conf.index("- domain: 'grafana.{{"):]
    regla = regla[:regla.index("- domain:", 5)]
    assert "group:students" not in regla, "los alumnos verían la auditoría del pañol"
