load("json.star", "json")

# Convierte cada mensaje MQTT de un equipo en una métrica numérica.
#
# Contrato (lo explica el manual de conexión):
#   topic    <equipo>/<dispositivo>/<magnitud>[/<sub>...]
#   payload  un número ("23.5"), una palabra de estado de la tabla ESTADOS
#            ("ON", "abierto", "online"...) o un JSON plano con números
#            ({"temp": 23.5, "hum": 60}).
#
# Sale una serie  mqtt_valor{equipo, dispositivo, magnitud}  por cada valor.
# Lo que no se puede convertir a número se descarta: Grafana grafica números,
# y guardar texto libre de 30 alumnos es la forma más rápida de llenar el disco.

ESTADOS = {
    "on": 1, "off": 0,
    "true": 1, "false": 0,
    "si": 1, "sí": 1, "no": 0,
    "encendido": 1, "prendido": 1, "apagado": 0,
    "abierto": 1, "cerrado": 0,
    "online": 1, "offline": 0,
    "alto": 1, "bajo": 0,
    "activo": 1, "inactivo": 0,
    "detectado": 1, "libre": 0,
}

# Topes contra una placa que publica topics inventados en un bucle.
MAX_NOMBRE = 40
MAX_CAMPOS_JSON = 20

def limpio(texto):
    """Deja solo letras, números y guion bajo (formato de nombre de métrica)."""
    out = ""
    for c in texto.elems():
        if c.isalnum() or c == "_":
            out += c
        elif c in "-/. ":
            out += "_"
    return out.lower()[:MAX_NOMBRE]

def es_numero(s):
    s = s.strip()
    if s == "":
        return False
    if s[0] in "+-":
        s = s[1:]
    if s == "":
        return False
    punto = False
    exp = False
    previo = ""
    for c in s.elems():
        if c.isdigit():
            pass
        elif c == "." and not punto and not exp:
            punto = True
        elif c in "eE" and not exp and previo.isdigit():
            exp = True
        elif c in "+-" and previo in "eE":
            pass
        else:
            return False
        previo = c
    return previo.isdigit() or previo == "."

def a_numero(v):
    t = type(v)
    if t == "int" or t == "float":
        return float(v)
    if t == "bool":
        return 1.0 if v else 0.0
    if t == "string":
        s = v.strip()
        if es_numero(s):
            return float(s)
        e = ESTADOS.get(s.lower())
        if e != None:
            return float(e)
    return None

def serie(equipo, dispositivo, magnitud, valor, ts):
    m = Metric("mqtt")
    m.tags["equipo"] = equipo
    m.tags["dispositivo"] = dispositivo
    m.tags["magnitud"] = magnitud
    m.fields["valor"] = valor
    m.time = ts
    return m

def apply(metric):
    partes = metric.tags.get("topic", "").split("/")
    # Mínimo equipo/dispositivo/magnitud: con menos no hay qué graficar.
    if len(partes) < 3:
        return None
    equipo = partes[0]
    dispositivo = limpio(partes[1])
    magnitud = limpio("_".join(partes[2:]))
    if dispositivo == "" or magnitud == "":
        return None

    crudo = metric.fields.get("value", "")
    if type(crudo) != "string":
        crudo = str(crudo)
    crudo = crudo.strip()

    salida = []
    if crudo.startswith("{"):
        datos = json.decode(crudo)
        n = 0
        for clave, val in datos.items():
            num = a_numero(val)
            nombre = limpio(magnitud + "_" + clave)
            if num != None and nombre != "":
                salida.append(serie(equipo, dispositivo, nombre, num, metric.time))
                n += 1
            if n >= MAX_CAMPOS_JSON:
                break
    else:
        num = a_numero(crudo)
        if num != None:
            salida.append(serie(equipo, dispositivo, magnitud, num, metric.time))

    return salida if salida else None
