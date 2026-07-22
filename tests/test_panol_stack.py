"""Static checks del plano Pañol IoT — Python puro, corre en CI (sin host).

    py.test -v tests/test_panol_stack.py

Cuida las tres cosas que, si se rompen, se rompen en silencio: que el broker no
quede anónimo, que el único puerto ruteable sea el de MQTT, y que el tag de
imagen del broker sea el mismo en el compose y en el rol (el rol usa esa imagen
para hashear las contraseñas).
"""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")
COMPOSE = os.path.join(ROOT, "compose", "panol", "compose.yml")
MOSQ_CONF = os.path.join(ROOT, "compose", "panol", "mosquitto", "mosquitto.conf")
ROLE_DEFAULTS = os.path.join(ROOT, "ansible", "roles", "panol", "defaults", "main.yml")
CADDYFILE = os.path.join(ROOT, "compose", "proxy", "Caddyfile")
SITE = os.path.join(ROOT, "ansible", "site.yml")


def _read(path):
    with open(path) as fh:
        return fh.read()


def test_stack_declares_the_three_services():
    compose = _read(COMPOSE)
    for service in ("mosquitto:", "postgres:", "nodered:"):
        assert service in compose, f"falta el servicio {service} en el compose"


def test_broker_is_not_anonymous():
    conf = _read(MOSQ_CONF)
    assert re.search(r"^allow_anonymous\s+false$", conf, re.M), "el broker quedó anónimo"
    assert re.search(r"^password_file\s+\S+$", conf, re.M), "sin password_file"
    assert re.search(r"^acl_file\s+\S+$", conf, re.M), "sin acl_file"


def test_only_mqtt_listens_off_loopback():
    """Todo puerto publicado que no sea el de MQTT tiene que ser 127.0.0.1."""
    for line in _read(COMPOSE).splitlines():
        line = line.strip()
        if not line.startswith('- "') or ":" not in line:
            continue
        mapping = line[3:].rstrip('"')
        if "PANOL_MQTT_PORT" in mapping:          # el broker: lo cuida UFW
            continue
        assert mapping.startswith("127.0.0.1:"), f"puerto expuesto sin loopback: {mapping}"


def test_mosquitto_image_matches_the_role():
    """El rol corre mosquitto_passwd con esta imagen: si divergen, el hash lo
    genera una versión distinta de la que después lee el archivo."""
    compose_tag = re.search(r"image:\s*(eclipse-mosquitto:\S+)", _read(COMPOSE)).group(1)
    role_tag = re.search(
        r'panol_mosquitto_image:\s*"([^"]+)"', _read(ROLE_DEFAULTS)
    ).group(1)
    assert compose_tag == role_tag, f"compose={compose_tag} rol={role_tag}"


def test_default_credentials_announce_themselves():
    """Las claves por defecto son conocidas a propósito, así que tienen que
    seguir siendo obviamente provisorias: si alguna vez alguien pega ahí un
    secreto real, este test lo frena antes del commit."""
    defaults = _read(ROLE_DEFAULTS)
    bloque = defaults.split("panol_mqtt_default_passwords:", 1)[1].split("\n\n", 1)[0]
    claves = re.findall(r':\s*"([^"]+)"', bloque)
    claves.append(re.search(r'panol_db_default_password:\s*"([^"]*)"', defaults).group(1))
    for c in claves:
        assert c == "" or c.startswith("cambiar-"), f"clave por defecto sospechosa: {c}"


def test_dashboard_is_published_behind_sso():
    caddy = _read(CADDYFILE)
    assert "reverse_proxy panol-nodered:1880" in caddy, "Node-RED no está publicado"
    site = caddy.split("{$PANOL_SUBDOMAIN}.{$CADDY_BASE_DOMAIN} {", 1)[1].split("}\n", 1)[0]
    assert "import authelia" in site, "el tablero quedó sin SSO"


def test_role_is_wired_into_the_playbook():
    assert re.search(r"role:\s*panol\b", _read(SITE)), "el rol panol no está en site.yml"
