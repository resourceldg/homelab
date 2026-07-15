"""Classroom base-plane smoke tests — run on the provisioned host.

    py.test -v --hosts=local:// --sudo tests/test_classroom.py

Verifies team isolation (Linux groups, 2770 setgid dirs on their own loopback
filesystems) and that students have NO privilege-escalation paths.
"""
import pytest

TEAMS = {
    "equipo-01": ["jessi"],
    "equipo-02": ["alan", "gabi"],
    "equipo-03": ["santi", "mijael", "gino"],
    "equipo-04": ["mariano", "jorge"],
    "equipo-05": ["guido"],
}
STUDENTS = [(team, user) for team, users in TEAMS.items() for user in users]


@pytest.mark.parametrize("team", TEAMS)
def test_team_group_exists(host, team):
    assert host.group(f"grp-{team}").exists


@pytest.mark.parametrize("team,user", STUDENTS)
def test_student_user_has_no_privileges(host, team, user):
    u = host.user(user)
    assert u.exists, f"{user} does not exist"
    assert f"grp-{team}" in u.groups, f"{user} not in grp-{team}"
    # Students must never reach the engine directly.
    assert "docker" not in u.groups, f"{user} is in the docker group!"
    assert "sudo" not in u.groups, f"{user} has sudo!"


@pytest.mark.parametrize("team", TEAMS)
def test_team_dir_isolated(host, team):
    d = host.file(f"/srv/classroom/{team}")
    assert d.exists and d.is_directory
    assert d.user == "root"
    assert d.group == f"grp-{team}"
    # 2770 = setgid + rwxrwx--- : own team read/write, no access for others.
    assert oct(d.mode) == "0o2770", f"{team} dir mode is {oct(d.mode)}"


@pytest.mark.parametrize("team", TEAMS)
def test_team_dir_on_own_loopback(host, team):
    # Each team dir is a distinct mounted filesystem (hard disk quota).
    assert host.mount_point(f"/srv/classroom/{team}").exists


@pytest.mark.parametrize("team", TEAMS)
def test_team_slice_has_hard_ceiling(host, team):
    r = host.run(f"systemctl show classroom-{team}.slice -p MemoryMax --value")
    assert r.rc == 0
    assert r.stdout.strip() not in ("", "infinity"), \
        f"classroom-{team}.slice has no MemoryMax"
