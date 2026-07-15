"""Unit tests for the classroom Compose policy validator.

Pure Python — no host, no Docker — so this runs in CI. Proves that dangerous
Compose files are rejected and a well-formed lab stack is accepted.

    py.test -v tests/test_labctl_policy.py
"""
import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "ansible", "roles", "labctl", "files"),
)
import policy  # noqa: E402

PROJECT = "/srv/classroom/equipo-01"


def _svc(**over):
    """A minimal service that PASSES policy; override to break one rule."""
    base = {
        "image": "eclipse-mosquitto:2.0.18",
        "restart": "unless-stopped",
        "pids_limit": 100,
        "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}},
        "deploy": {"resources": {"limits": {"cpus": "0.25", "memory": "128M"}}},
    }
    base.update(over)
    return base


def _doc(**services):
    return {"services": services or {"web": _svc()}}


def ok(doc):
    return policy.validate_compose(doc, project_dir=PROJECT)


# --- the happy path --------------------------------------------------------

def test_minimal_valid_service_passes():
    assert ok(_doc()) == []


def test_realistic_iot_stack_passes():
    doc = {
        "services": {
            "mosquitto": _svc(
                image="eclipse-mosquitto:2.0.18",
                ports=["127.0.0.1:1883:1883"],
                volumes=["./mosquitto/config:/mosquitto/config"],
            ),
            "nodered": _svc(
                image="nodered/node-red:4.0",
                ports=["127.0.0.1:1880:1880"],
                volumes=["./nodered/data:/data"],
            ),
        }
    }
    assert ok(doc) == []


# --- privilege / namespace escapes ----------------------------------------

def test_privileged_rejected():
    assert any("privileged" in x for x in ok(_doc(web=_svc(privileged=True))))


def test_network_mode_host_rejected():
    assert any("network_mode" in x for x in ok(_doc(web=_svc(network_mode="host"))))


def test_pid_host_rejected():
    assert any("pid" in x for x in ok(_doc(web=_svc(pid="host"))))


def test_ipc_host_rejected():
    assert any("ipc" in x for x in ok(_doc(web=_svc(ipc="host"))))


def test_dangerous_cap_rejected():
    assert any("SYS_ADMIN" in x for x in ok(_doc(web=_svc(cap_add=["SYS_ADMIN"]))))


# --- docker socket & host mounts ------------------------------------------

def test_docker_socket_mount_rejected():
    out = ok(_doc(web=_svc(volumes=["/var/run/docker.sock:/var/run/docker.sock"])))
    assert any("Docker socket" in x for x in out)


def test_mount_of_etc_rejected():
    out = ok(_doc(web=_svc(volumes=["/etc:/host-etc"])))
    assert any("outside the project dir" in x for x in out)


def test_mount_outside_project_via_dotdot_rejected():
    out = ok(_doc(web=_svc(volumes=["../equipo-02/data:/data"])))
    assert any("outside the project dir" in x for x in out)


def test_bind_mount_inside_project_ok():
    assert ok(_doc(web=_svc(volumes=["./data:/data"]))) == []


def test_named_volume_rejected():
    doc = _doc(web=_svc(volumes=["pgdata:/var/lib/postgresql/data"]))
    assert any("named volume" in x for x in ok(doc))


def test_top_level_named_volumes_rejected():
    doc = _doc(web=_svc(volumes=["./data:/data"]))
    doc["volumes"] = {"pgdata": None}
    assert any("named volumes are not allowed" in x for x in ok(doc))


# --- images ----------------------------------------------------------------

def test_latest_image_rejected():
    assert any("latest" in x for x in ok(_doc(web=_svc(image="nginx:latest"))))


def test_untagged_image_rejected():
    assert any("explicit tag" in x for x in ok(_doc(web=_svc(image="nginx"))))


# --- limits / pids / logging / restart ------------------------------------

def test_missing_memory_limit_rejected():
    svc = _svc()
    del svc["deploy"]
    assert any("memory limit" in x for x in ok(_doc(web=svc)))


def test_missing_pids_limit_rejected():
    svc = _svc()
    del svc["pids_limit"]
    assert any("pids_limit" in x for x in ok(_doc(web=svc)))


def test_missing_logging_rejected():
    svc = _svc()
    del svc["logging"]
    assert any("logging" in x for x in ok(_doc(web=svc)))


def test_missing_restart_rejected():
    svc = _svc()
    del svc["restart"]
    assert any("restart" in x for x in ok(_doc(web=svc)))


# --- ports -----------------------------------------------------------------

def test_port_on_all_interfaces_rejected():
    assert any("127.0.0.1" in x for x in ok(_doc(web=_svc(ports=["8080:80"]))))


def test_port_explicit_0000_rejected():
    assert any("127.0.0.1" in x for x in ok(_doc(web=_svc(ports=["0.0.0.0:8080:80"]))))


def test_port_loopback_ok():
    assert ok(_doc(web=_svc(ports=["127.0.0.1:8080:80"]))) == []


def test_long_form_port_without_host_ip_rejected():
    svc = _svc(ports=[{"target": 80, "published": 8080}])
    assert any("host_ip" in x for x in ok(_doc(web=svc)))


# --- counts / shape --------------------------------------------------------

def test_too_many_services_rejected():
    doc = {"services": {f"s{i}": _svc() for i in range(6)}}
    assert any("too many services" in x for x in ok(doc))


def test_no_services_rejected():
    assert ok({"services": {}}) == ["no services defined"]


def test_non_mapping_rejected():
    assert ok([]) == ["compose file is not a mapping"]
