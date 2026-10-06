#!/usr/bin/env python3
"""Claves del aula: arma la hoja de claves para repartir y genera claves nuevas.

Corre EN EL SERVIDOR, como `homelab` (ahí está la clave del vault, ~/.vault_pass).

Por qué existe: cada alumno tiene UNA clave para todo (Grafana del aula, página
de inicio y SSH). Vive en el vault (`vault_sso_passwords`), cifrada, y la usan
los roles `authelia` y `classroom`. Editarla a mano con `ansible-vault edit` es
fácil de romper, y repartirla exige leerla de a una. Este script hace las dos
cosas sin que ninguna clave pase por el repositorio.

    claves-aula.py hoja                    hoja de todos los equipos (no cambia nada)
    claves-aula.py hoja equipo-03          solo ese equipo (o un usuario: mijael)
    claves-aula.py nueva mijael jorge      clave nueva para esos alumnos
    claves-aula.py nueva --faltantes       solo para quien todavía no tiene
    claves-aula.py nueva --todos           todos los alumnos (¡corta las sesiones SSH y web!)
    claves-aula.py ... --archivo hoja.txt  además guarda la hoja (permisos 600)

Después de `nueva`, aplicar para que tomen efecto:
    cd ~/homelab/ansible && ~/homelab/.venv/bin/ansible-playbook site.yml --tags auth,classroom -K

Las claves son tres partes fáciles de dictar y tipear: `nube-tigre-482`.
"""
import argparse
import datetime
import os
import re
import secrets
import shutil
import subprocess
import sys

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GV = os.path.join(RAIZ, "ansible", "inventories", "production", "group_vars", "all")
VAULT = os.environ.get("CLAVES_VAULT", os.path.join(GV, "vault.yml"))
ROSTER = os.environ.get("CLAVES_ROSTER", os.path.join(GV, "classroom.yml"))
CLAVE_VAULT = os.environ.get("CLAVES_VAULT_PASS_FILE", os.path.expanduser("~/.vault_pass"))
# El respaldo va FUERA del repo: un vault.yml.bak dentro no lo cubre .gitignore.
RESPALDOS = os.environ.get("CLAVES_RESPALDO_DIR", os.path.expanduser("~/.claves-aula-respaldos"))
_VENV = os.path.join(RAIZ, ".venv", "bin", "ansible-vault")
ANSIBLE_VAULT = os.environ.get("CLAVES_ANSIBLE_VAULT", _VENV if os.path.exists(_VENV) else "ansible-vault")

CLAVE_DICT = "vault_sso_passwords"
URL_GRAFANA = "https://grafana-aula.lucasland.duckdns.org"

# Palabras cortas, sin tildes ni ñ (cualquier teclado las escribe igual).
PALABRAS = """
abeja agua aire alas alba ancla arbol arena arroz astro avion balsa banco barco
bosque brisa bruma cabra cactus cafe calle campo canoa caracol carbon casa cebra
cerro cielo cinta circo clavo cobre cohete coral cuerda delfin diente dragon duna
eco faro fideo flecha flor foca fuego gato globo gorila grillo guitarra hielo
hoja horno hueso huevo humo iman isla jardin jirafa koala lago lapiz lava leon
libro lima lobo loro luna llave madera mago mango manta mapa mar martillo menta
mesa miel mono monte motor nave nido nieve nube nuez ola oro oso pajaro palma
pan papel pato perla piano piedra pino pirata planeta pluma polo puente pulpo
queso radar rana rayo red reloj rio robot roca rueda sal selva silla sol sombra
sopa taza techo tigre tierra tomate torre tren trueno tucan uva vaca valle vela
viento volcan yate yerba zorro
""".split()


def error(msg):
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(2)


def nueva_clave():
    return f"{secrets.choice(PALABRAS)}-{secrets.choice(PALABRAS)}-{secrets.randbelow(900) + 100}"


def leer_roster():
    with open(ROSTER, encoding="utf-8") as f:
        datos = yaml.safe_load(f) or {}
    nombres = {u["username"]: u.get("displayname", u["username"]) for u in datos.get("sso_users", [])}
    equipos = [(t["name"], list(t.get("members", []))) for t in datos.get("classroom_teams", [])]
    return equipos, nombres


def vault(*args, entrada=None):
    cmd = [ANSIBLE_VAULT, *args, "--vault-password-file", CLAVE_VAULT]
    r = subprocess.run(cmd, input=entrada, capture_output=True, text=True)
    if r.returncode != 0:
        error(f"ansible-vault {args[0]} falló: {r.stderr.strip()}")
    return r.stdout


def leer_vault():
    if not os.path.exists(CLAVE_VAULT):
        error(f"no encuentro la clave del vault en {CLAVE_VAULT}: esto se corre en el servidor, como homelab")
    texto = vault("view", VAULT)
    return texto, (yaml.safe_load(texto) or {}).get(CLAVE_DICT) or {}


def con_claves_nuevas(texto, nuevas):
    """Cambia o agrega `usuario: "clave"` dentro de vault_sso_passwords, tocando
    solo esas líneas: el resto del vault (comentarios, orden, otras claves) queda igual."""
    lineas = texto.splitlines()
    try:
        inicio = next(i for i, l in enumerate(lineas) if re.match(rf"^{CLAVE_DICT}:\s*(#.*)?$", l))
    except StopIteration:
        lineas += ["", f"{CLAVE_DICT}:"]
        inicio = len(lineas) - 1
    # El bloque son las líneas indentadas que siguen (las vacías y comentarios también).
    fin = inicio + 1
    while fin < len(lineas) and (lineas[fin].startswith((" ", "\t")) or not lineas[fin].strip()):
        fin += 1
    while fin > inicio + 1 and not lineas[fin - 1].strip():
        fin -= 1
    sangria = next((re.match(r"^(\s+)\S", l).group(1) for l in lineas[inicio + 1:fin]
                    if re.match(r"^\s+[^\s#]", l)), "  ")
    pendientes = dict(nuevas)
    for i in range(inicio + 1, fin):
        m = re.match(r"^\s+([A-Za-z0-9_.-]+):", lineas[i])
        if m and m.group(1) in pendientes:
            lineas[i] = f'{sangria}{m.group(1)}: "{pendientes.pop(m.group(1))}"'
    agregar = [f'{sangria}{u}: "{c}"' for u, c in pendientes.items()]
    lineas[fin:fin] = agregar
    return "\n".join(lineas) + "\n"


def guardar_vault(texto):
    os.makedirs(RESPALDOS, mode=0o700, exist_ok=True)
    sello = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    respaldo = os.path.join(RESPALDOS, f"vault-{sello}.yml")
    shutil.copy2(VAULT, respaldo)  # el respaldo sigue cifrado
    os.chmod(respaldo, 0o600)
    cifrado = vault("encrypt", "--output", "-", "-", entrada=texto)
    yaml.safe_load(vault("decrypt", "--output", "-", "-", entrada=cifrado))  # se puede volver a abrir
    with open(VAULT, "w", encoding="utf-8") as f:
        f.write(cifrado)
    return respaldo


def hoja(equipos, nombres, claves, quienes=None):
    """Hoja para repartir. `quienes`: solo esos usuarios (None = todos)."""
    salida = [
        "CLAVES DEL AULA — entregar a cada alumno EN PRIVADO (no por el grupo).",
        "Sirven para: Grafana del aula, la página de inicio y SSH.",
        f"Grafana: con Tailscale prendido, abrí {URL_GRAFANA}",
        "",
    ]
    for equipo, miembros in equipos:
        elegidos = [u for u in miembros if quienes is None or u in quienes]
        if not elegidos:
            continue
        salida.append(equipo)
        for u in elegidos:
            clave = claves.get(u, "(sin clave: claves-aula.py nueva --faltantes)")
            salida.append(f"  {nombres.get(u, u):<12} usuario: {u:<10} clave: {clave}")
        salida.append("")
    return "\n".join(salida)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="accion", required=True)
    h = sub.add_parser("hoja", help="mostrar la hoja de claves (no cambia nada)")
    h.add_argument("filtro", nargs="?", help="equipo-NN o usuario")
    n = sub.add_parser("nueva", help="generar claves nuevas y guardarlas en el vault")
    n.add_argument("usuarios", nargs="*")
    g = n.add_mutually_exclusive_group()
    g.add_argument("--todos", action="store_true", help="todos los alumnos del roster")
    g.add_argument("--faltantes", action="store_true", help="solo quien no tiene clave")
    for p in (h, n):
        p.add_argument("--archivo", help="guardar también la hoja en este archivo (permisos 600)")
    a = ap.parse_args()

    equipos, nombres = leer_roster()
    alumnos = [u for _, miembros in equipos for u in miembros]
    texto, claves = leer_vault()

    if a.accion == "hoja":
        quienes = None
        if a.filtro:
            del_equipo = dict(equipos).get(a.filtro)
            if del_equipo is None and a.filtro not in alumnos:
                error(f"«{a.filtro}» no es un equipo ni un alumno del roster")
            quienes = set(del_equipo or [a.filtro])
        resultado = hoja(equipos, nombres, claves, quienes)
    else:
        if a.todos:
            elegidos = alumnos
        elif a.faltantes:
            elegidos = [u for u in alumnos if u not in claves]
        else:
            if not a.usuarios:
                error("decí a quién: usuarios, --faltantes o --todos")
            ajenos = [u for u in a.usuarios if u not in alumnos]
            if ajenos:
                error(f"no son alumnos del roster: {', '.join(ajenos)} (al operador no se le cambia la clave acá)")
            elegidos = a.usuarios
        if not elegidos:
            print("✓ Nadie para cambiar: todos los alumnos ya tienen clave.")
            return
        nuevas = {u: nueva_clave() for u in elegidos}
        respaldo = guardar_vault(con_claves_nuevas(texto, nuevas))
        claves.update(nuevas)
        print(f"✓ Vault actualizado ({len(nuevas)} clave/s). Respaldo cifrado: {respaldo}")
        print("  Para que tomen efecto (Grafana, página de inicio y SSH):")
        print("  cd ~/homelab/ansible && ~/homelab/.venv/bin/ansible-playbook site.yml --tags auth,classroom -K\n")
        resultado = hoja(equipos, nombres, claves, set(nuevas))

    print(resultado)
    if a.archivo:
        fd = os.open(a.archivo, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(resultado + "\n")
        print(f"(hoja guardada en {a.archivo}: borrala cuando la entregues)")


if __name__ == "__main__":
    main()
