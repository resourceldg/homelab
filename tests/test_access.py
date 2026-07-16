"""SSO / access-layer host checks — run on the provisioned host.

    py.test -v --hosts=local:// tests/test_access.py
"""


def test_authelia_running(host):
    ps = host.run("docker ps --filter name=^/authelia$ --format '{{.Status}}'")
    assert "Up" in ps.stdout, f"authelia not running: {ps.stdout!r}"


def test_authelia_config_rendered(host):
    cfg = host.file("/opt/homelab/stacks/auth/config/configuration.yml")
    assert cfg.exists
    assert cfg.contains("access_control")


def test_caddyfile_has_authelia_forward_auth(host):
    cf = host.file("/opt/homelab/stacks/proxy/Caddyfile")
    assert cf.contains("forward_auth authelia")


def test_dnsmasq_active(host):
    assert host.service("dnsmasq").is_enabled
    assert host.service("dnsmasq").is_running
