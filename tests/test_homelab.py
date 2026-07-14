"""
Smoke tests for the home server, executed with pytest + testinfra.

    pip install -r tests/requirements.txt
    # Test the local machine:
    py.test -v --hosts=local://           tests/test_homelab.py
    # Or over SSH:
    py.test -v --hosts=ssh://ansible@homelab-01 tests/test_homelab.py
"""


def test_ssh_hardening(host):
    cfg = host.file("/etc/ssh/sshd_config")
    assert cfg.contains("PermitRootLogin no")
    assert cfg.contains("PasswordAuthentication no")
    assert cfg.contains("PubkeyAuthentication yes")


def test_sshd_running(host):
    ssh = host.service("ssh")
    ssh_socket = host.service("ssh.socket")
    # Ubuntu 24.04 usa socket activation: ssh.service arranca on-demand
    # y puede figurar disabled/inactive mientras ssh.socket es quien
    # escucha y está enabled al boot.
    assert ssh.is_running or ssh_socket.is_running
    assert ssh.is_enabled or ssh_socket.is_enabled

def test_ufw_active(host):
    ufw = host.run("ufw status verbose")
    assert ufw.rc == 0
    assert "Status: active" in ufw.stdout
    assert "deny (incoming)" in ufw.stdout


def test_fail2ban_sshd_jail(host):
    assert host.service("fail2ban").is_running
    status = host.run("fail2ban-client status sshd")
    assert status.rc == 0


def test_apparmor_enforcing(host):
    assert host.service("apparmor").is_running
    aa = host.run("aa-status")
    assert aa.rc == 0
    assert "profiles are in enforce mode" in aa.stdout


def test_unattended_upgrades(host):
    assert host.package("unattended-upgrades").is_installed
    assert host.service("unattended-upgrades").is_enabled


def test_sysctl_hardening(host):
    assert host.sysctl("kernel.randomize_va_space") == 2
    assert host.sysctl("net.ipv4.conf.all.accept_redirects") == 0
    assert host.sysctl("net.ipv4.tcp_syncookies") == 1


def test_audit_tooling(host):
    assert host.package("lynis").is_installed
    assert host.package("aide").is_installed
    assert host.file("/var/lib/aide/aide.db").exists
    assert host.service("lynis-scan.timer").is_enabled
    assert host.service("aide-check.timer").is_enabled


def test_docker_running(host):
    assert host.service("docker").is_running
    daemon = host.file("/etc/docker/daemon.json")
    assert daemon.contains("no-new-privileges")


def test_tailscale_installed(host):
    assert host.package("tailscale").is_installed
    assert host.service("tailscaled").is_enabled


def test_ddns_timer(host):
    assert host.service("duckdns.timer").is_enabled
    assert host.file("/usr/local/bin/duckdns-update.sh").mode == 0o750


def test_backup_timer(host):
    assert host.package("borgbackup").is_installed
    assert host.service("borgmatic.timer").is_enabled


def test_containers_up(host):
    ps = host.run("docker ps --format '{{.Names}}'")
    for name in ("caddy", "prometheus", "grafana", "node-exporter"):
        assert name in ps.stdout, f"{name} container not running"
