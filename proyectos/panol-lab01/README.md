# Pañol IoT · LAB01 — tablero de ThingsBoard

Tablero **oscuro** del pañol, al estilo de los paneles industriales: plano
animado del pañol, sesión en curso, indicadores del día, gráficos, registro y
alarmas. Esta carpeta tiene el **generador del tablero** (`tablero.py`), su copia
en JSON y un **simulador** para verlo funcionar sin el hardware.

> **Estado (16/10/2026):** en la **réplica local** de ThingsBoard (la de la
> notebook), con **datos reales** del pañol que trae `puente_real.py` (punto 6).
> **Todavía no está en producción.**

## 1. Qué muestra

| Bloque | Qué es | De dónde sale |
|---|---|---|
| Encabezado | Nodo en línea / sesión / alarma, como "chips" que laten | `active`, `sesion`, `alarma` |
| **Plano del pañol** | Puerta (verde cerrada, ámbar abierta, roja si se abrió sin credencial), lector RFID (verde concedido, rojo denegado), cerradura, sensor PIR con ondas cuando detecta movimiento, 4 armarios y la persona adentro si hay sesión | `puerta`, `acceso`, `pir`, `armario1..4`, `sesion_usuario` |
| Sesión actual | Iniciales en un anillo que se llena con el tiempo (2 h = lleno), nombre, rol, hora de entrada y minutos adentro. Sin sesión: cómo terminó la última | `sesion*`, `fin_sesion` |
| Indicadores del día | Accesos concedidos, denegados, sesiones y alarmas desde las 00:00 | suma de `acceso_concedido`, `acceso_denegado`, `sesion_nueva`, `alarma_evento` |
| Accesos por hora | Barras de 24 h: concedidos, denegados y "liberó sin entrar" | `acceso_*` |
| Puerta y sesión | Línea de estado de las últimas 6 h | `puerta`, `sesion` |
| Registro de eventos | Cada acceso, movimiento de puerta, fin de sesión y alarma | varios |
| Alarmas activas | Las del motor de sesiones del pañol (abajo) | perfil `panol` |

El plano, el encabezado y la sesión son **tarjetas Markdown con una función**
que arma HTML/SVG con los datos en vivo (con animaciones CSS). El resto son
widgets estándar de ThingsBoard con los colores pasados a oscuro por
`oscurecer()`. No hace falta ningún widget propio ni la versión paga.

**Limitación de la versión CE:** el menú lateral y la barra de ThingsBoard no
cambian de color (eso es *white-labeling*, solo en la versión paga). En pantalla
completa (botón ⛶ arriba a la derecha) o en la vista pública, no se ven.

## 2. Contrato de datos (telemetría del dispositivo `panol/LAB01`)

Es lo que tiene que mandar el puente del pañol. Sale del motor de sesiones
(`Documents/panol-iot/docs/DISENO.md`, tabla de transiciones).

| Clave | Valor | Cuándo |
|---|---|---|
| `acceso` | `CONCEDIDO` / `DENEGADO` / `SIN_INGRESO` | cada lectura de tarjeta |
| `acceso_usuario` | nombre o UID de la tarjeta | junto con `acceso` |
| `acceso_concedido` / `acceso_denegado` / `acceso_sin_ingreso` | 1 | uno por evento, para contar |
| `puerta` | 1 abierta / 0 cerrada | cada cambio del reed |
| `pir` | 1 movimiento / 0 | cada detección |
| `armario1` … `armario4` | 1 abierto / 0 cerrado | nodo de armarios (futuro) |
| `sesion` | 1 en curso / 0 sin sesión | al crear y al cerrar |
| `sesion_nueva` | 1 | al crear una sesión (para contar) |
| `sesion_usuario`, `sesion_rol`, `sesion_inicio` (ms) | texto / ms | al crear |
| `fin_sesion` | `RELEVO` / `AUSENCIA` / `CIERRE_SISTEMA` | al cerrar |
| `alarma` | código del motor u `OK` | al aparecer y al resolverse |
| `alarma_evento` | 1 | cada alarma nueva (para contar) |
| `alarma_<código en minúscula>` | 1 activa / 0 resuelta | dispara y borra la alarma de ThingsBoard |

### Alarmas (`--alarmas`, perfil `panol`)

| Alarma | Severidad | Se activa / se borra |
|---|---|---|
| Pañol: puerta abierta sin credencial | CRITICAL | `alarma_apertura_sin_credencial` 1 / 0 |
| Pañol: movimiento sin sesión | MAJOR | `alarma_presencia_sin_sesion` 1 / 0 |
| Pañol: armario abierto sin sesión | MAJOR | `alarma_armario_sin_sesion` 1 / 0 |
| Pañol: puerta abierta sin gente | WARNING | `alarma_puerta_abierta_sin_gente` 1 / 0 |
| Pañol: nodo sin conexión | MAJOR | ThingsBoard marca el dispositivo inactivo (2 min sin datos) / vuelve |

## 3. Crear o actualizar el tablero

```bash
# Donde corre ThingsBoard (réplica local o, más adelante, homelab-01):
TB_URL=http://127.0.0.1:18080 TB_USUARIO=<admin del tenant> TB_CLAVE_ARCHIVO=<archivo con la clave> \
  python3 tablero.py --crear --alarmas                  # primera vez
TB_URL=... python3 tablero.py --crear --reemplazar      # después de cambiar tablero.py
```

- `--dispositivo` cambia el dispositivo al que se ata (por defecto `panol/LAB01`;
  para mirar el simulador en producción: `panol/LAB01_simulado`).
- Nunca pisa un tablero hecho a mano: solo actualiza el que lleva su marca.

## 4. Simulador

Carga **24 h de historia** y después sigue **en vivo** (con `--rapido`, 6 veces
más rápido, para mostrar). Personas inventadas. Publica por **MQTT con el token
del dispositivo**, igual que un nodo real. Como ThingsBoard tiene el HTTP
apagado y su MQTT solo existe dentro de la red de Docker `thingsboard`, se
corre en un contenedor de esa red (que no tiene internet: la librería
`paho-mqtt` se monta desde un archivo `.whl` descargado antes):

```bash
docker run -d --name panol-sim --network thingsboard \
  -v $PWD:/app:ro -v <carpeta con paho_mqtt-2.1.0-py3-none-any.whl>:/whl:ro \
  -v <archivo con la clave>:/run/admin.pass:ro \
  -e TB_URL=http://thingsboard:8080 -e TB_USUARIO=<admin del tenant> -e TB_CLAVE_ARCHIVO=/run/admin.pass \
  -w /app python:3.12-alpine \
  sh -c "pip install -q --no-index /whl/paho_mqtt-2.1.0-py3-none-any.whl && python simulador.py --rapido"
docker rm -f panol-sim     # cortarlo
```

Por defecto escribe en `panol/LAB01_simulado` para no mezclar datos falsos con
los reales.

## 5. Para conectarlo al pañol real (pendiente)

1. Un puente que se suscriba a `panol/LAB01/sesion` y `panol/LAB01/alarma/#` del
   broker del pañol (y a los eventos del nodo) y publique en ThingsBoard las
   claves de la tabla 2. Lo más simple: sumar un destino al puente del aula
   (`compose/thingsboard/puente/puente.py`), que ya sabe hablar con ThingsBoard
   como gateway.
2. Crear el tablero en producción con `--crear --alarmas`, en el tenant del ISFT.
3. Decidir si se publica (vista pública sin login) o queda privado: muestra
   **nombres de personas** que entran al pañol, así que por defecto **privado**.

## 6. Datos reales para la muestra: `puente_real.py`

Lee la base del pañol en homelab-01 **por SSH, solo con SELECT**, cada 2 s, y
publica lo nuevo en ThingsBoard con la hora real de cada evento (puerta, PIR,
armarios, accesos, sesiones, alarmas y el latido del nodo). Al arrancar carga
las últimas 24 h. No escribe nada en el pañol.

```bash
TB_URL=http://127.0.0.1:18080 TB_USUARIO=<admin del tenant> TB_CLAVE_ARCHIVO=<archivo con la clave> \
  python3 puente_real.py            # Ctrl+C para cortar
```

- Necesita SSH sin contraseña a `ansible@homelab-01` (`--host` para otro).
- La base no registra cuándo se resuelve una alarma ni cuándo se cierra un
  armario: el puente da la alarma por resuelta al minuto y el armario por
  cerrado a los 20 s, solo para el tablero.
- Es de muestra. El camino definitivo es el puente MQTT del pañol hacia
  ThingsBoard (punto 5).

**PIR:** el nodo lo reporta como máximo una vez cada `THROTTLE_PIR_MS` (en la
placa: 5 s en modo muestra, 30 s normal). En el tablero, cada movimiento
ilumina el cono de detección del plano durante 15 s y suma una barra en
"Movimiento (PIR) por minuto".
