"""Unit tests for scripts/claves-aula.py — the classroom password sheet/rotator.

Runs against a throwaway vault encrypted with a throwaway password: no real
secret is ever read. Needs `ansible-vault` (ansible-core) on PATH.

    py.test -v tests/test_claves_aula.py
"""
import os
import re
import shutil
import subprocess

import pytest
import yaml

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "claves-aula.py")
pytestmark = pytest.mark.skipif(shutil.which("ansible-vault") is None, reason="ansible-vault no instalado")

ROSTER = """
classroom_teams:
  - name: equipo-01
    members: [jessi, dardo]
  - name: equipo-03
    members: [santi, mijael]
sso_users:
  - { username: operator, displayname: "Operador", groups: [operators] }
  - { username: jessi, displayname: "Jessi", groups: [students] }
  - { username: dardo, displayname: "Dardo", groups: [students] }
  - { username: santi, displayname: "Santi", groups: [students] }
  - { username: mijael, displayname: "Mijael", groups: [students] }
"""

VAULT_PLANO = """---
# secretos de prueba
vault_grafana_admin_password: "admin-no-tocar"
vault_sso_passwords:
  operator: "clave-del-profe"   # no se toca
  jessi: "vieja-jessi"
  santi: "vieja-santi"
vault_duckdns_token: "token-no-tocar"
"""

FORMATO = re.compile(r"^[a-z]+-[a-z]+-\d{3}$")


@pytest.fixture
def entorno(tmp_path):
    clave = tmp_path / "vault_pass"
    clave.write_text("clave-de-prueba\n")
    vault = tmp_path / "vault.yml"
    vault.write_text(VAULT_PLANO)
    subprocess.run(["ansible-vault", "encrypt", str(vault), "--vault-password-file", str(clave)],
                   check=True, capture_output=True)
    roster = tmp_path / "classroom.yml"
    roster.write_text(ROSTER)
    env = dict(os.environ, CLAVES_VAULT=str(vault), CLAVES_ROSTER=str(roster),
               CLAVES_VAULT_PASS_FILE=str(clave), CLAVES_RESPALDO_DIR=str(tmp_path / "respaldos"),
               CLAVES_ANSIBLE_VAULT="ansible-vault")
    return {"env": env, "vault": vault, "clave": clave, "tmp": tmp_path}


def _run(entorno, *args):
    return subprocess.run(["python3", SCRIPT, *args], capture_output=True, text=True, env=entorno["env"])


def _plano(entorno):
    return subprocess.run(["ansible-vault", "view", str(entorno["vault"]), "--vault-password-file",
                           str(entorno["clave"])], capture_output=True, text=True, check=True).stdout


def test_hoja_no_cambia_nada(entorno):
    antes = entorno["vault"].read_text()
    r = _run(entorno, "hoja")
    assert r.returncode == 0, r.stderr
    assert "vieja-jessi" in r.stdout and "vieja-santi" in r.stdout
    assert "sin clave" in r.stdout            # dardo y mijael no tienen
    assert "clave-del-profe" not in r.stdout   # el operador no va en la hoja
    assert entorno["vault"].read_text() == antes


def test_hoja_filtra_por_equipo(entorno):
    r = _run(entorno, "hoja", "equipo-03")
    assert r.returncode == 0, r.stderr
    assert "santi" in r.stdout and "jessi" not in r.stdout


def test_nueva_cambia_solo_a_quien_se_pide_y_respeta_el_resto(entorno):
    r = _run(entorno, "nueva", "jessi")
    assert r.returncode == 0, r.stderr
    plano = _plano(entorno)
    datos = yaml.safe_load(plano)
    claves = datos["vault_sso_passwords"]
    assert FORMATO.match(claves["jessi"])
    assert claves["santi"] == "vieja-santi"
    assert claves["operator"] == "clave-del-profe"
    assert datos["vault_grafana_admin_password"] == "admin-no-tocar"
    assert datos["vault_duckdns_token"] == "token-no-tocar"
    assert "# secretos de prueba" in plano and "# no se toca" in plano
    assert claves["jessi"] in r.stdout and "santi" not in r.stdout
    assert "--tags auth,classroom" in r.stdout
    assert len(list((entorno["tmp"] / "respaldos").iterdir())) == 1


def test_faltantes_agrega_solo_a_los_que_no_tienen(entorno):
    r = _run(entorno, "nueva", "--faltantes")
    assert r.returncode == 0, r.stderr
    claves = yaml.safe_load(_plano(entorno))["vault_sso_passwords"]
    assert FORMATO.match(claves["dardo"]) and FORMATO.match(claves["mijael"])
    assert claves["jessi"] == "vieja-jessi" and claves["santi"] == "vieja-santi"
    assert _run(entorno, "nueva", "--faltantes").stdout.startswith("✓ Nadie")


def test_todos_no_toca_al_operador(entorno):
    assert _run(entorno, "nueva", "--todos").returncode == 0
    claves = yaml.safe_load(_plano(entorno))["vault_sso_passwords"]
    assert claves["operator"] == "clave-del-profe"
    assert all(FORMATO.match(claves[u]) for u in ("jessi", "dardo", "santi", "mijael"))
    assert len(set(claves[u] for u in ("jessi", "dardo", "santi", "mijael"))) == 4


def test_rechaza_al_operador_y_a_desconocidos(entorno):
    antes = entorno["vault"].read_text()
    for quien in ("operator", "nadie"):
        r = _run(entorno, "nueva", quien)
        assert r.returncode == 2 and "no son alumnos" in r.stderr
    assert entorno["vault"].read_text() == antes


def test_archivo_queda_privado(entorno):
    destino = entorno["tmp"] / "hoja.txt"
    assert _run(entorno, "hoja", "--archivo", str(destino)).returncode == 0
    assert oct(destino.stat().st_mode & 0o777) == "0o600"
    assert "vieja-jessi" in destino.read_text()


def test_sin_clave_del_vault_explica_donde_correrlo(entorno):
    env = dict(entorno["env"], CLAVES_VAULT_PASS_FILE=str(entorno["tmp"] / "no-existe"))
    r = subprocess.run(["python3", SCRIPT, "hoja"], capture_output=True, text=True, env=env)
    assert r.returncode == 2 and "en el servidor" in r.stderr
