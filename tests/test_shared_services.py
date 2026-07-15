"""Shared-services host-level smoke tests — run on the provisioned host.

    py.test -v --hosts=local:// tests/test_shared_services.py

Verifies Postgres/Redis/Mailpit are up and each team got a credentials file.
"""
import pytest

TEAMS = ["equipo-01", "equipo-02", "equipo-03", "equipo-04", "equipo-05"]


@pytest.mark.parametrize("name", ["postgres", "redis", "mailpit"])
def test_shared_service_running(host, name):
    ps = host.run(f"docker ps --filter name=^/{name}$ --format '{{{{.Status}}}}'")
    assert "Up" in ps.stdout, f"{name} not running: {ps.stdout!r}"


@pytest.mark.parametrize("team", TEAMS)
def test_team_credentials_file(host, team):
    f = host.file(f"/srv/classroom/{team}/.shared-services.env")
    assert f.exists
    assert f.group == f"grp-{team}"
    assert f.mode == 0o640
    assert f.contains(f"PGDATABASE=db_{team.replace('-', '_')}")


@pytest.mark.parametrize("team", TEAMS)
def test_team_database_exists(host, team):
    tid = team.replace("-", "_")
    q = f"docker exec postgres psql -U postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='db_{tid}'\""
    r = host.run(q)
    assert r.stdout.strip() == "1", f"db_{tid} missing"
