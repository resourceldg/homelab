"""Unit tests for ansible/roles/aula_iot/files/aula_grafana.py — one Grafana
organization per team. Runs against an in-memory fake of the Grafana API.

    py.test -v tests/test_aula_grafana.py

Lo que cuida: que cada equipo quede en su org con SOLO su fuente (filtrada y
predeterminada), que los alumnos salgan de la org del operador, que la migración
desde el diseño anterior no pierda lo que el equipo editó, y que correrlo dos
veces no cambie nada.
"""
import importlib.util
import json
import os
import re

import pytest

RUTA = os.path.join(os.path.dirname(__file__), "..", "ansible", "roles", "aula_iot", "files", "aula_grafana.py")
spec = importlib.util.spec_from_file_location("aula_grafana", RUTA)
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)

TABLERO = os.path.join(os.path.dirname(RUTA), "equipo-dashboard.json")


class FakeGrafana:
    """Lo justo de la API de Grafana que usa el script, en memoria."""

    def __init__(self):
        self.orgs = {1: {"name": "Main Org.", "users": {}, "ds": {}, "dash": {}, "folders": {}, "teams": {}}}
        self.users = {}           # login -> id
        self.next = 100
        self.llamadas = []

    def _id(self):
        self.next += 1
        return self.next

    def add_user(self, login, org=1, role="Viewer"):
        uid = self.users.setdefault(login, self._id())
        self.orgs[org]["users"][login] = role
        return uid

    def pedir(self, metodo, ruta, cuerpo=None, org=None, ok=(200,)):
        self.llamadas.append((metodo, ruta, org))
        o = self.orgs.get(org or 1)
        path = ruta.split("?")[0]
        qs = dict(p.split("=", 1) for p in ruta.split("?")[1].split("&")) if "?" in ruta else {}
        unq = ag.urllib.parse.unquote

        def no(code=404):
            if code in ok:
                return code, {"message": "not found"}
            raise AssertionError(f"inesperado {code} en {metodo} {ruta}")

        if m := re.fullmatch(r"/api/orgs/(\d+)", path):
            oo = self.orgs[int(m[1])]
            if metodo == "GET":
                return 200, {"id": int(m[1]), "name": oo["name"]}
            oo["name"] = cuerpo["name"]
            return 200, {}
        if m := re.fullmatch(r"/api/orgs/name/(.+)", path):
            for i, oo in self.orgs.items():
                if oo["name"] == unq(m[1]):
                    return 200, {"id": i, "name": oo["name"]}
            return no()
        if path == "/api/orgs" and metodo == "POST":
            i = self._id()
            self.orgs[i] = {"name": cuerpo["name"], "users": {"operator": "Admin"}, "ds": {}, "dash": {},
                            "folders": {}, "teams": {}}
            return 200, {"orgId": i}
        if path == "/api/users/lookup":
            login = unq(qs["loginOrEmail"])
            return (200, {"id": self.users[login]}) if login in self.users else no()
        if path == "/api/admin/users":
            return 200, {"id": self.add_user(cuerpo["login"])}
        if m := re.fullmatch(r"/api/orgs/(\d+)/users", path):
            oo = self.orgs[int(m[1])]
            if metodo == "GET":
                return 200, [{"login": l, "userId": self.users[l], "role": r} for l, r in oo["users"].items()]
            oo["users"][cuerpo["loginOrEmail"]] = cuerpo["role"]
            return 200, {}
        if m := re.fullmatch(r"/api/orgs/(\d+)/users/(\d+)", path):
            oo = self.orgs[int(m[1])]
            login = next(l for l, i in self.users.items() if i == int(m[2]))
            if metodo == "DELETE":
                del oo["users"][login]
            else:
                oo["users"][login] = cuerpo["role"]
            return 200, {}
        if m := re.fullmatch(r"/api/users/(\d+)/using/(\d+)", path):
            return 200, {}
        if m := re.fullmatch(r"/api/datasources/uid/(.+)", path):
            if metodo == "GET":
                return (200, {**o["ds"][m[1]], "id": 1}) if m[1] in o["ds"] else no()
            o["ds"][m[1]] = {k: v for k, v in cuerpo.items() if k != "id"}
            return 200, {}
        if path == "/api/datasources":
            o["ds"][cuerpo["uid"]] = cuerpo
            return 200, {}
        if m := re.fullmatch(r"/api/dashboards/uid/(.+)", path):
            return (200, {"dashboard": {**o["dash"][m[1]], "id": 7, "version": 3}}) if m[1] in o["dash"] else no()
        if path == "/api/dashboards/db":
            assert cuerpo["overwrite"] is False
            o["dash"][cuerpo["dashboard"]["uid"]] = cuerpo["dashboard"]
            return 200, {}
        if m := re.fullmatch(r"/api/folders/(.+)", path):
            if m[1] not in o["folders"]:
                return no()
            if metodo == "DELETE":
                for uid in o["folders"].pop(m[1]):
                    o["dash"].pop(uid, None)
            return 200, {}
        if path == "/api/teams/search":
            name = unq(qs["name"])
            return 200, {"teams": [{"id": i, "name": n} for i, n in o["teams"].items() if n == name]}
        if m := re.fullmatch(r"/api/teams/(\d+)", path):
            del o["teams"][int(m[1])]
            return 200, {}
        raise AssertionError(f"ruta no simulada: {metodo} {ruta}")


def _cfg(equipos):
    with open(TABLERO) as f:
        tablero = f.read()
    return {"operador": "operator", "nombre_org_operador": "Aula — operador",
            "vm_url": "http://aula-victoriametrics:8428", "tablero_inicial": tablero,
            "equipos": equipos, "nombres": {"santi": "Santi", "mijael": "Mijael", "jorge": "Jorge"}}


EQUIPOS = [{"name": "equipo-03", "members": ["santi", "mijael"]}, {"name": "equipo-04", "members": ["jorge"]}]


def _org(g, nombre):
    return next(o for o in g.orgs.values() if o["name"] == nombre)


@pytest.fixture
def g():
    g = FakeGrafana()
    g.add_user("operator", role="Admin")
    return g


def test_cada_equipo_queda_en_su_org_con_solo_su_fuente(g):
    ag.sincronizar(_cfg(EQUIPOS), g)
    for nombre, miembros in (("equipo-03", {"santi", "mijael"}), ("equipo-04", {"jorge"})):
        o = _org(g, nombre)
        assert list(o["ds"]) == [f"mqtt-{nombre}"]
        ds = o["ds"][f"mqtt-{nombre}"]
        assert ds["isDefault"] is True
        assert ds["jsonData"]["customQueryParameters"] == f"extra_label=equipo={nombre}"
        assert {l for l, r in o["users"].items() if r == "Editor"} == miembros
        assert o["users"]["operator"] == "Admin"
        assert f"{nombre}-mqtt" in o["dash"]


def test_los_alumnos_salen_de_la_org_del_operador(g):
    g.add_user("santi")  # como quedó con el diseño anterior
    ag.sincronizar(_cfg(EQUIPOS), g)
    assert set(g.orgs[1]["users"]) == {"operator"}
    assert g.orgs[1]["name"] == "Aula — operador"


def test_migracion_conserva_lo_que_el_equipo_edito(g):
    o1 = g.orgs[1]
    editado = {"uid": "equipo-03-mqtt", "title": "Lo de Mijael", "panels": [{"title": "mi panel"}]}
    o1["dash"]["equipo-03-mqtt"] = editado
    o1["folders"]["equipo-03"] = ["equipo-03-mqtt"]
    o1["teams"][55] = "equipo-03"
    ag.sincronizar(_cfg(EQUIPOS), g)
    nuevo = _org(g, "equipo-03")["dash"]["equipo-03-mqtt"]
    assert nuevo["title"] == "Lo de Mijael" and nuevo["panels"] == [{"title": "mi panel"}]
    assert "id" not in nuevo and "version" not in nuevo
    assert "equipo-03" not in o1["folders"] and "equipo-03-mqtt" not in o1["dash"]
    assert 55 not in o1["teams"]


def test_la_carpeta_vieja_se_borra_recien_con_el_tablero_a_salvo(g):
    g.orgs[1]["dash"]["equipo-03-mqtt"] = {"uid": "equipo-03-mqtt", "title": "x"}
    g.orgs[1]["folders"]["equipo-03"] = ["equipo-03-mqtt"]
    ag.sincronizar(_cfg(EQUIPOS), g)
    orden = [(m, r) for m, r, _ in g.llamadas if r in ("/api/dashboards/db", "/api/folders/equipo-03")]
    assert orden.index(("POST", "/api/dashboards/db")) < orden.index(("DELETE", "/api/folders/equipo-03"))


def test_segunda_corrida_no_cambia_nada(g):
    assert ag.sincronizar(_cfg(EQUIPOS), g)
    assert ag.sincronizar(_cfg(EQUIPOS), g) == []


def test_alumno_que_cambia_de_equipo_sale_de_la_org_vieja(g):
    ag.sincronizar(_cfg(EQUIPOS), g)
    movido = [{"name": "equipo-03", "members": ["santi"]}, {"name": "equipo-04", "members": ["jorge", "mijael"]}]
    cambios = ag.sincronizar(_cfg(movido), g)
    assert "mijael" not in _org(g, "equipo-03")["users"]
    assert _org(g, "equipo-04")["users"]["mijael"] == "Editor"
    assert any("mijael quitado" in c for c in cambios)


def test_no_pisa_el_tablero_que_el_equipo_ya_tiene(g):
    ag.sincronizar(_cfg(EQUIPOS), g)
    o = _org(g, "equipo-03")
    o["dash"]["equipo-03-mqtt"]["title"] = "cambiado por el equipo"
    ag.sincronizar(_cfg(EQUIPOS), g)
    assert o["dash"]["equipo-03-mqtt"]["title"] == "cambiado por el equipo"


def test_corrige_una_fuente_alterada(g):
    ag.sincronizar(_cfg(EQUIPOS), g)
    o = _org(g, "equipo-03")
    o["ds"]["mqtt-equipo-03"]["jsonData"]["customQueryParameters"] = ""
    cambios = ag.sincronizar(_cfg(EQUIPOS), g)
    assert o["ds"]["mqtt-equipo-03"]["jsonData"]["customQueryParameters"] == "extra_label=equipo=equipo-03"
    assert any("corregida" in c for c in cambios)


def test_tablero_inicial_aunque_ansible_lo_pase_como_objeto(g):
    cfg = _cfg(EQUIPOS)
    cfg["tablero_inicial"] = json.loads(cfg["tablero_inicial"])
    ag.sincronizar(cfg, g)
    assert _org(g, "equipo-04")["dash"]["equipo-04-mqtt"]["title"].startswith("equipo-04")
