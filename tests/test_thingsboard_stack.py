"""Static checks del stack de ThingsBoard — Python puro, corre en CI (sin host).

    py.test -v tests/test_thingsboard_stack.py

Cuida lo que, si se rompe, se rompe en silencio y expone algo:
  - versiones fijas (nada de `latest`) y ningún puerto fuera de loopback;
  - ThingsBoard sin transporte HTTP, sin Swagger y con clave JWT propia;
  - el proxy público deniega por defecto y NO deja pasar escrituras
    (probado contra ThingsBoard CE 4.3.1.6: el token público puede escribir
    telemetría, atributos y RPC si llega directo — ver docs/thingsboard.md);
  - la cuenta del puente en mqtt-aula es de solo lectura (sin bucles);
  - los proyectos son privados salvo que se los marque públicos.
"""
import json
import os
import re

import jinja2
import yaml

ROOT = os.path.join(os.path.dirname(__file__), "..")
STACK = os.path.join(ROOT, "compose", "thingsboard")
COMPOSE = os.path.join(STACK, "compose.yml")
CADDY_PUBLICO = os.path.join(STACK, "publico", "Caddyfile")
SERVE = os.path.join(STACK, "publico", "serve.json")
ROLE = os.path.join(ROOT, "ansible", "roles", "thingsboard")
SHARED_DEFAULTS = os.path.join(ROOT, "ansible", "roles", "shared_services", "defaults", "main.yml")
SITE = os.path.join(ROOT, "ansible", "site.yml")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _compose():
    return yaml.safe_load(_read(COMPOSE))


def test_imagenes_con_version_fija():
    for nombre, svc in _compose()["services"].items():
        imagen = svc["image"]
        assert ":" in imagen and not imagen.endswith(":latest"), f"{nombre}: imagen sin versión fija ({imagen})"
    for dockerfile in ("puente/Dockerfile", "publico/Dockerfile"):
        for linea in _read(os.path.join(STACK, dockerfile)).splitlines():
            if linea.startswith("FROM "):
                assert re.search(r":\d+\.\d+\.\d+", linea), f"{dockerfile}: FROM sin versión exacta: {linea}"
    assert "caddy-ratelimit@" in _read(os.path.join(STACK, "publico", "Dockerfile")), "módulo rate_limit sin versión fija"


def test_ningun_puerto_fuera_de_loopback():
    for nombre, svc in _compose()["services"].items():
        for p in svc.get("ports", []):
            assert str(p).startswith("127.0.0.1:"), f"{nombre}: publica {p} fuera de loopback"


def test_thingsboard_endurecido():
    tb = _compose()["services"]["thingsboard"]
    env = tb["environment"]
    for clave in ("HTTP_ENABLED", "SWAGGER_ENABLED", "COAP_ENABLED", "LWM2M_ENABLED", "SNMP_ENABLED", "EDGES_ENABLED"):
        assert env[clave] == "false", f"{clave} tiene que estar apagado"
    assert env["JWT_TOKEN_SIGNING_KEY"] == "${TB_JWT_SIGNING_KEY}", "la clave JWT tiene que salir de un secreto"
    assert "env_file" not in tb, "thingsboard no debe recibir el .env entero (tiene el token del puente y la auth key)"
    assert tb["deploy"]["resources"]["limits"]["cpus"] == "1.0", "tope de 1 núcleo (temperatura del server)"


def test_red_interna_sin_salida():
    redes = _compose()["networks"]
    assert redes["tb"]["internal"] is True


def test_proxy_publico_deniega_por_defecto():
    # Sin comentarios: el archivo nombra las rutas prohibidas para explicarlas.
    caddy = "\n".join(l for l in _read(CADDY_PUBLICO).splitlines() if not l.strip().startswith("#"))
    sitio = caddy[caddy.index(":8080 {"):caddy.index(":9180 {")]
    # El último handle del sitio público es el 404 para todo lo demás.
    ultimo = sitio.rstrip().rsplit("handle {", 1)[1]
    assert 'respond "No encontrado" 404' in ultimo
    # Ninguna ruta de escritura ni de administración en la lista.
    for prohibida in ("/api/plugins", "/api/rpc", "/actuator", "/swagger", "/api/auth/login ",
                      "/api/device", "/api/customer", "/api/entitiesQuery", "/api/v1"):
        assert prohibida not in sitio, f"el proxy público menciona {prohibida}"
    # Los únicos POST: login público y renovación del token.
    posts = re.findall(r"method POST\s*\n\s*path ([^\n]+)", sitio)
    assert posts == ["/api/auth/login/public /api/auth/token"], posts
    assert "rate_limit" in sitio and "max_size" in sitio


def test_funnel_solo_al_proxy_publico():
    serve = json.loads(_read(SERVE))
    proxies = [h["Proxy"] for web in serve["Web"].values() for h in web["Handlers"].values()]
    assert proxies == ["http://tableros-proxy:8080"], proxies


def test_vhost_admin_detras_de_authelia_y_sin_metricas():
    vhost = _read(os.path.join(ROLE, "templates", "thingsboard.caddy.j2"))
    assert "import authelia" in vhost
    assert "/actuator" in vhost and "404" in vhost


def test_cuentas_mqtt_coherentes_y_puente_de_solo_lectura():
    shared = yaml.safe_load(_read(SHARED_DEFAULTS))
    cuentas = {c["name"]: c["acl"] for c in shared["shared_mqtt_tb_users"]}
    assert all(r.startswith("topic read ") for r in cuentas["tb-puente"]), "tb-puente tiene que ser SOLO lectura"
    demo_tb = yaml.safe_load(_read(os.path.join(ROLE, "defaults", "main.yml")))["thingsboard_demo_proyectos"]
    demo_puente = sorted(r.split()[-1][:-2] for r in cuentas["tb-puente"] if "{teams}" not in r)
    demo_simulador = sorted(r.split()[-1][:-2] for r in cuentas["tb-demo"])
    assert demo_puente == sorted(demo_tb) == demo_simulador


def test_apagado_por_defecto_y_con_tag_propio():
    defaults = yaml.safe_load(_read(os.path.join(ROLE, "defaults", "main.yml")))
    assert defaults["thingsboard_enabled"] is False
    assert defaults["thingsboard_publico_enabled"] is False
    assert "role: thingsboard, tags: [\"thingsboard\"]" in _read(SITE)


def _render_tableros(**extra):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(ROLE, "templates")),
                             extensions=["jinja2.ext.do"])
    env.filters["to_nice_json"] = lambda v: json.dumps(v, ensure_ascii=False, indent=2)
    env.filters["bool"] = lambda v: v if isinstance(v, bool) else str(v).lower() in ("true", "yes", "1")
    defaults = yaml.safe_load(_read(os.path.join(ROLE, "defaults", "main.yml")))
    vars_ = dict(defaults, stacks_root="/opt/homelab/stacks",
                 classroom_teams=[{"name": "equipo-01"}, {"name": "equipo-02"}])
    # Los defaults con Jinja adentro se resuelven a mano para el test.
    vars_["thingsboard_dashboards_generales"] = [
        {"titulo": "IoT — General", "tipos": vars_["thingsboard_demo_proyectos"], "publico": True}]
    vars_["thingsboard_publico_host"] = "tableros.example.ts.net"
    vars_.update(extra)
    return json.loads(env.get_template("tableros.json.j2").render(**vars_))


def test_proyectos_privados_por_defecto():
    cfg = _render_tableros()
    por_titulo = {d["titulo"]: d for d in cfg["dashboards"]}
    assert por_titulo["Proyecto — equipo-01"]["publico"] is False
    assert por_titulo["Aula — Todos los proyectos"]["publico"] is False
    assert por_titulo["Estación meteorológica"]["publico"] is True
    cfg = _render_tableros(thingsboard_proyectos_publicos=["equipo-02"])
    assert {d["titulo"]: d for d in cfg["dashboards"]}["Proyecto — equipo-02"]["publico"] is True


def test_sin_datos_personales_en_los_titulos():
    """Los títulos salen del NOMBRE del equipo, nunca de sus integrantes."""
    cfg = _render_tableros(classroom_teams=[{"name": "equipo-01", "members": ["jessi", "dardo"]}])
    texto = json.dumps(cfg)
    assert "jessi" not in texto and "dardo" not in texto


def test_espacio_de_equipo_con_admin_alumno():
    """Un equipo con espacio propio: login <usuario>@dominio, clave en un
    archivo de secretos (nunca en la config) y token de gateway propio."""
    cfg = _render_tableros(thingsboard_equipos_admin=[{"equipo": "equipo-01", "usuarios": ["dardo"]}])
    (esp,) = cfg["equipos_admin"]
    assert esp["equipo"] == "equipo-01"
    assert esp["usuarios"] == [{"usuario": "dardo", "email": "dardo@isft238.local",
                                "clave": "/etc/thingsboard/secrets/tb-usuario-dardo.pass"}]
    assert esp["gateway_token"] == "/etc/thingsboard/secrets/gateway-equipo-01.token"
    assert _render_tableros()["equipos_admin"] == []
