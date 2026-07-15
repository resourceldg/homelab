"""Validate the provisioned Grafana dashboards — pure Python, runs in CI.

    py.test -v tests/test_dashboards.py
"""
import glob
import json
import os

DASH_DIR = os.path.join(
    os.path.dirname(__file__), "..", "compose", "monitoring",
    "grafana", "provisioning", "dashboards", "json",
)


def _dashboards():
    return glob.glob(os.path.join(DASH_DIR, "*.json"))


def test_all_dashboards_valid_json_with_required_fields():
    files = _dashboards()
    assert files, "no dashboards found"
    for f in files:
        with open(f) as fh:
            d = json.load(fh)
        assert d.get("uid"), f"{f}: missing uid"
        assert d.get("title"), f"{f}: missing title"
        assert d.get("panels"), f"{f}: no panels"


def test_classroom_dashboards_present():
    uids = {json.load(open(f)).get("uid") for f in _dashboards()}
    for want in ("classroom-overview", "classroom-team-detail", "classroom-capacity"):
        assert want in uids, f"missing dashboard {want}"
