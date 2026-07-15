"""labctl broker host-level smoke tests — run on the provisioned host.

    py.test -v --hosts=local:// tests/test_labctl.py

Verifies the daemon is installed and running, the client is present, and the
socket is reachable only by the classroom group.
"""


def test_client_installed(host):
    f = host.file("/usr/local/bin/labctl")
    assert f.exists and f.mode == 0o755


def test_daemon_and_policy_installed(host):
    assert host.file("/opt/labctl/labctld").exists
    assert host.file("/opt/labctl/policy.py").exists


def test_pyyaml_present(host):
    assert host.package("python3-yaml").is_installed


def test_labctld_running(host):
    svc = host.service("labctld")
    assert svc.is_enabled
    assert svc.is_running


def test_socket_group_restricted(host):
    s = host.file("/run/labctld.sock")
    assert s.exists
    assert s.group == "classroom"
    # 0660 = rw for owner (root) and the classroom group, nothing for others.
    assert s.mode == 0o660


def test_common_classroom_group(host):
    assert host.group("classroom").exists


def test_audit_log_dir_private(host):
    d = host.file("/var/log/labctl")
    assert d.is_directory
    assert d.mode == 0o750
