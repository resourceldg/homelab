"""Smoke tests del plano Pañol IoT — corren contra el host aprovisionado.

    py.test -v --hosts=local:// --sudo tests/test_panol.py

Comprueban lo que solo se puede comprobar con el stack arriba: contenedores
sanos, secretos con permisos de secreto, y un broker que efectivamente rechaza
a quien no tiene credencial.
"""
import pytest

CONTAINERS = ["panol-mosquitto", "panol-postgres", "panol-nodered"]


@pytest.mark.parametrize("name", CONTAINERS)
def test_container_running(host, name):
    ps = host.run(f"docker ps --filter name=^/{name}$ --format '{{{{.Status}}}}'")
    assert "Up" in ps.stdout, f"{name} no está corriendo: {ps.stdout!r}"


def test_broker_rejects_anonymous_clients(host):
    """La garantía de fondo: sin usuario y clave no se publica nada."""
    r = host.run(
        "docker exec panol-mosquitto "
        "mosquitto_sub -h 127.0.0.1 -p 1883 -t 'panol/#' -C 1 -W 3"
    )
    assert r.rc != 0, "el broker aceptó un cliente anónimo"


def test_password_file_is_readable_only_by_the_broker(host):
    f = host.file("/opt/homelab/stacks/panol/mosquitto/passwd")
    assert f.exists
    assert f.mode == 0o640
    assert f.uid == 1883 and f.gid == 1883


def test_acl_gives_each_node_its_own_branch(host):
    acl = host.file("/opt/homelab/stacks/panol/mosquitto/acl")
    assert acl.exists
    assert acl.contains("topic write panol/panol-lab01/panol-lab01-puerta/evento/#")
    # Escribir en todo el árbol es privilegio de UNA sola identidad: el servidor.
    n = host.run("grep -c 'topic readwrite panol/#' /opt/homelab/stacks/panol/mosquitto/acl")
    assert n.stdout.strip() == "1", "más de un usuario con escritura total"


def test_secrets_are_root_only(host):
    d = host.file("/etc/panol/secrets")
    assert d.is_directory and d.mode == 0o700 and d.user == "root"


def test_app_credentials_file(host):
    f = host.file("/etc/panol/app.env")
    assert f.exists
    assert f.mode == 0o640
    assert f.contains("MQTT_HOST=mosquitto")
    assert f.contains("PANOL_DSN=postgresql://")


def test_mqtt_port_is_open_only_to_device_networks(host):
    rules = host.run("ufw status | grep -i 1883").stdout
    assert "1883" in rules, "no hay regla UFW para MQTT"
    assert "Anywhere" not in rules.replace("Anywhere (v6)", ""), \
        "MQTT quedó abierto a cualquier origen"


def test_project_network_exists(host):
    r = host.run("docker network inspect panol --format '{{.Name}}'")
    assert r.rc == 0 and r.stdout.strip() == "panol"
