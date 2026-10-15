# Sony IR — Control de relés (equipo-01)

Tablero de ThingsBoard del proyecto de **Dardo (equipo-01)**: una ESP32 que
recibe un control remoto infrarrojo Sony y, con las teclas 1, 2 y 3, alterna
dos relés y un relé de estado sólido. Esta carpeta tiene el **generador del
tablero** (`tablero.py`), sus copias en JSON y un **simulador**. El firmware
con la conexión WiFi + MQTT vive aparte, en el proyecto de Dardo.

## 1. Qué hace la aplicación (ingeniería inversa del código Rust)

`no_std`, ESP32-WROOM-32, `esp-hal` 1.1. **IMPLEMENTADO** en el código original:

| Pieza | Detalle |
|---|---|
| Entrada | Receptor IR en **GPIO27**. Lo lee el RMT (1 tick = 1 µs, reposo de 8 ms, 48 símbolos). Decodifica **Sony SIRC de 15 bits** y tiene 19 teclas con nombre |
| Salidas | **Relé 1 en GPIO18** y **Relé 2 en GPIO23**, activos en LOW. **SSR en GPIO19**, activo en HIGH. Las tres arrancan apagadas |
| Lógica | La tecla **1** (`0x4200`) alterna el Relé 1, la **2** (`0x4201`) el Relé 2 y la **3** (`0x4202`) el SSR. La tecla se da por soltada tras **150 ms** sin tramas y hay un mínimo de **200 ms** entre acciones. `0x4244` y `0x4245` se ignoran |
| Pantalla | OLED SSD1306 por I2C (SDA 21, SCL 22): muestra la tecla, el código y el estado de la salida |
| Logs | Por el puerto serie: tecla, cambio de cada salida, trama inválida y errores del RMT |
| **No tiene** | Red, sensores (fuera del IR), persistencia del estado ni alarmas propias |

El README original del proyecto dice 2 relés, 180 ms y 250 ms. **El código
tiene 3 salidas y usa 150 ms y 200 ms**: vale el código.

## 2. Conexión (agregada)

Para que ThingsBoard reciba datos se agregó **WiFi + MQTT con TLS al
firmware**, en una copia del proyecto (`sony_ir_reles_mqtt`), sin cambiar la
lógica del control:

- el bucle IR pasa a ser **asíncrono** (embassy, `esp-rtos`). Teclas, tiempos,
  relés y pantalla quedan **idénticos**;
- cada evento aceptado va a una cola. Una tarea aparte lo publica por MQTT 5
  sobre TLS 1.3 (`rust-mqtt` + `embedded-tls`), con reconexión automática;
- **si no hay WiFi o broker, el control y los relés funcionan igual**;
- al (re)conectar se publica el estado completo de las 3 salidas.

Versiones: `esp-radio` 0.18, `esp-rtos` 0.3, `embassy-net` 0.9.1,
`rust-mqtt` 0.6 y `embedded-tls` 0.19, todas atadas a `esp-hal ~1.1`.

### Contrato MQTT

Broker `homelab-01.tail4eda13.ts.net:10000` (TLS, Funnel), usuario `equipo_01`.
El puente del aula lo copia a ThingsBoard como el dispositivo **`equipo-01/sony_ir`**.

| Variable en el firmware | Topic `equipo-01/sony_ir/…` | Valor | Cuándo | Widget |
|---|---|---|---|---|
| arranque | `reinicio` | 1 | primer contacto tras prender | Reinicios (24 h) |
| `rele1_activo` | `rele1` | 0/1 | cada cambio y al reconectar | Relé 1 + línea de estado |
| `rele2_activo` | `rele2` | 0/1 | ídem | Relé 2 + línea de estado |
| `rele3_activo` | `ssr` | 0/1 | ídem | SSR + línea de estado |
| salida accionada | `accionamiento` | 1/2/3 | cada accionamiento | Accionamientos (24 h), barras |
| `codigo` aceptado | `tecla` | código decimal (16896 = 0x4200) | cada pulsación aceptada | Última tecla, Pulsaciones |
| `cantidad` (trama no válida) | `trama_invalida` | símbolos | cada trama inválida | Tramas inválidas, calidad |
| error del RMT | `error_rx` | 1 | cada error | Calidad, alarma |
| latido | `enlace` | 1 | cada 30 s | Conexión, alarma |
| `controller.rssi()` | `rssi` | dBm | cada 30 s | Señal WiFi |

En ThingsBoard, además: `active` y `lastActivityTime` (atributos del servidor) →
"Conexión de la placa" y "Última comunicación".

## 3. Tableros

`tablero.py` arma dos tableros desde la configuración por defecto de los widgets
de **la propia instancia** (ThingsBoard CE 4.3.1.6):

**Sony IR — Control de relés (equipo-01)**, el completo:

| Bloque | Widgets |
|---|---|
| Cabecera | Descripción del proyecto · Conexión de la placa · Última comunicación · Señal WiFi (dBm) |
| Indicadores | Relé 1 · Relé 2 · SSR (ENCENDIDO/APAGADO con color) · Última tecla (nombre de la tecla) |
| Últimas 24 h | Accionamientos · Pulsaciones IR · Tramas inválidas · Reinicios |
| Tiempo real | Línea de estado de cada salida (ventana del tablero: 6 h) |
| Histórico | Pulsaciones y accionamientos por hora · Calidad de recepción por hora |
| Eventos y alarmas | Historial de eventos · Alarmas activas |

**Sony IR — Control de relés · Exhibición:** lo mismo **sin** la información
técnica (tramas, reinicios, calidad, historial y alarmas), pensado para mostrar.
**No está publicado.** Para publicarlo: en ThingsBoard, *Hacer público*, y
compartir el link cambiando el host por `tableros.tail4eda13.ts.net`.

**No hay controles.** La aplicación no tiene control remoto por red, y las
salidas pueden manejar cargas de 220 V: no se agregan botones que accionen
relés desde internet.

### Alarmas (`--alarmas`)

| Alarma | Severidad | Se activa | Se borra |
|---|---|---|---|
| Sony IR: placa sin conexión | MAJOR | ThingsBoard marca el dispositivo inactivo (sin datos durante el tiempo de inactividad) | sola, al volver los datos |
| Sony IR: error del receptor infrarrojo | WARNING | llega `error_rx` | a mano (reconocer/borrar) |

ThingsBoard 4.3 **no trae** el nodo *Device Profile* en la cadena raíz, que es
el que evalúa estas reglas. El script lo agrega al principio de la cadena raíz
**del tenant de Dardo**, guardando antes una copia de la cadena
(`~/tb-cadena-raiz-<id>-antes.json`, en la máquina donde corre).

## 4. Instalar y actualizar

```bash
# En homelab-01 (las credenciales de Dardo no salen del server):
sudo TB_URL=http://127.0.0.1:18080 TB_USUARIO=dardo@isft238.local \
     TB_CLAVE_ARCHIVO=/etc/thingsboard/secrets/tb-usuario-dardo.pass \
     python3 tablero.py --crear --alarmas          # primera vez
sudo ... python3 tablero.py --crear --reemplazar  # después de cambiar tablero.py
```

- Sin opciones, solo regenera `tablero.json` y `tablero-exhibicion.json`.
- **Nunca pisa un tablero hecho a mano:** solo actualiza los que llevan su
  marca en la descripción.
- Para importarlo a mano: *Tableros → Añadir tablero → Importar tablero* →
  `tablero.json`.

## 5. Validación (15/10/2026)

| Prueba | Resultado |
|---|---|
| Tablero con datos simulados (réplica local, no producción) | Los 19 widgets muestran datos; sin errores de consola en escritorio ni en celular |
| Alarma "placa sin conexión" | Se crea a los 60 s sin datos (inactividad de prueba) y se borra sola al llegar un latido |
| Alarma "error del receptor" | Se crea al llegar `error_rx` |
| Firmware | **Compila** para ESP32 (xtensa): RAM ~82 KB de variables + 96 KB de pila, flash ~660 KB |
| Cliente MQTT del firmware (mismo código, en la PC) | TLS 1.3 con SNI → MQTT 5 con usuario y clave → las 10 variables del contrato llegaron bien a un Mosquitto con TLS |
| Producción (tenant de Dardo) | Los dos tableros cargan sin errores; quedan vacíos hasta que la placa tenga el firmware nuevo |

**No verificado todavía:** el firmware **en la placa real** (no había hardware
para probar) y la conexión por **Funnel** desde la placa. Se prueba al grabarlo.

## 6. Simulador

`simulador.py` publica el contrato imitando el comportamiento real, solo para
pruebas. Por defecto usa el dispositivo `equipo-01/sony_ir_simulado`, para no
mezclar datos falsos con los reales. `--como-real` solo en un entorno de prueba.

## 7. Limitaciones y mejoras posibles

- Las publicaciones son **QoS 0**. Un evento que ocurre justo durante un corte
  se pierde, pero el estado de las salidas se republica al reconectar.
- La cola guarda 32 eventos sin red; los que excedan se descartan (y se loguea).
- El estado no persiste en la placa: al reiniciar, todo arranca apagado (es lo
  que hace el código original).
- Sin verificación del certificado TLS, igual que las placas Arduino del aula
  (`setInsecure`).
- Mejora posible: medir el tiempo real de encendido de cada salida (hoy los
  datos son eventos; un promedio no representaría tiempo encendido).
