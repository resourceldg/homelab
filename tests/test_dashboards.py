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


def test_label_values_variables_use_a_plain_selector():
    # label_values() va a la API /series de Prometheus, que solo acepta un
    # selector (metrica{etiquetas}), no funciones. Con label_replace() adentro
    # Prometheus responde "parse error", la variable queda vacia y TODOS los
    # paneles del tablero muestran "No data" (le paso a classroom-team-detail).
    # Para derivar valores con funciones: query_result(...) + regex.
    import re
    for f in _dashboards():
        d = json.load(open(f))
        for v in d.get("templating", {}).get("list", []):
            if v.get("type") != "query":
                continue
            q = v.get("query")
            q = q.get("query", "") if isinstance(q, dict) else (q or "")
            m = re.match(r"\s*label_values\((.*)\)\s*$", q, re.S)
            if m:
                inner = m.group(1)
                assert not re.match(r"\s*[a-z_]+\(", inner), (
                    f"{os.path.basename(f)}: variable {v['name']} usa una funcion "
                    f"dentro de label_values(): {q}"
                )
