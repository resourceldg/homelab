"""Classroom publication host-level checks — run on the provisioned host.

    py.test -v --hosts=local:// tests/test_classroom_publish.py
"""


def test_caddyfile_imports_conf_d(host):
    assert host.file("/opt/homelab/stacks/proxy/Caddyfile").contains("import conf.d")


def test_exposures_file_present(host):
    f = host.file("/opt/homelab/stacks/proxy/conf.d/classroom-exposures.caddy")
    assert f.exists
