# 13. Usar Grafana (manual rápido)

🎯 **Objetivo:** entrar al Grafana del aula, entender tu dashboard y
**modificarlo**: agregar gráficos, cambiarlos y guardarlos.

> 🚧 **Estado (octubre 2026): el Grafana del aula se está poniendo en marcha.**
> Todavía no está disponible: el profe avisa cuando lo esté. Mientras tanto ya
> podés **preparar tu placa** siguiendo las reglas de este capítulo: lo que
> publiques bien desde ahora va a aparecer solo cuando se active.

🧩 **Prerequisitos:** Tailscale conectado y tus datos llegando
([capítulo 12](12-conectar-a-grafana.md)).

## Primero, la idea: el tablero de un auto

El tablero de un auto te muestra velocidad, nafta y temperatura del motor de un
vistazo, con agujas y luces de colores. No maneja el auto: **te deja ver** cómo
anda. **Grafana** es eso para tus placas.

> **Palabras de este capítulo:**
>
> - **Dashboard (tablero):** una pantalla con varios gráficos.
> - **Panel:** cada cuadro del tablero (un gráfico, un número grande, una tabla).
> - **Consulta (*query*):** la pregunta que el panel le hace a la base de datos
>   ("dame la temperatura de la sala de las últimas 3 horas").
> - **Datasource (fuente de datos):** la base de datos a la que se le pregunta.
>   La tuya se llama **MQTT — equipo-NN** y solo tiene datos de tu equipo.
> - **PromQL:** el idioma en que se escriben esas consultas. No hace falta
>   aprenderlo entero: abajo hay un **recetario** para copiar.
> - **Serie temporal:** una lista de valores con su hora, como una planilla
>   "hora | valor".

---

## 1. Entrar

> 🚧 Mientras el Grafana del aula esté en puesta en marcha, esta dirección todavía
> no carga. Lo que sigue es cómo va a funcionar.

1. Con **Tailscale conectado**, abrí en el navegador:

    ```
    https://grafana-aula.lucasland.duckdns.org
    ```

2. Te pide **usuario y contraseña del aula** (los mismos de SSH). Entrás directo
   a Grafana, no hay otro login.

> Si el navegador dice que no encuentra la página: Tailscale no está conectado.

**Qué podés ver:** solo la carpeta de **tu equipo**. Las de los otros equipos no
aparecen.

---

## 2. Encontrar tu dashboard

Menú (☰ arriba a la izquierda) → **Dashboards** → carpeta **equipo-NN** →
**equipo-NN — sensores y actuadores**.

Un **dashboard** es una pantalla con varios **paneles** (cada cuadro es un panel).

---

## 3. Leer el dashboard

| Panel | Qué te dice |
|---|---|
| **Dispositivos reportando** | cuántas placas mandaron algo en los últimos 5 minutos. Verde = hay datos |
| **Último mensaje hace** | cuánto pasó desde el último dato. Rojo = hace más de 15 minutos que no llega nada |
| **Estado actual** | tabla con el último valor de cada dispositivo y magnitud |
| **Actuadores y estados** | barras de color en el tiempo: verde = ON/abierto, gris = OFF/cerrado |
| **Todas las magnitudes** | gráfico de líneas con la historia de cada valor |
| **Mensajes por minuto** | cuánto publica cada placa (sirve para detectar bucles) |

**Mover el tiempo** (arriba a la derecha):

- El reloj 🕒 elige el rango: *Last 15 minutes*, *Last 24 hours*, etc.
- Hacé **clic y arrastrá** sobre un gráfico para hacer zoom en ese tramo.
- La flecha circular ⟳ actualiza. El dashboard ya se actualiza solo cada 10 s.

**Pasá el mouse** sobre un gráfico: ves el valor exacto en ese momento.

---

## 4. Editar un panel

1. Pasá el mouse sobre el panel → menú **⋮** (arriba a la derecha del panel) →
   **Edit**.
2. Abajo está la **consulta** (*query*). Arriba, cómo se ve.
3. A la derecha, las **opciones** de visualización:
    - **Title:** el nombre del panel.
    - **Standard options → Unit:** la unidad (°C = *Temperature → Celsius*,
      % = *Misc → Percent (0-100)*).
    - **Thresholds:** colores según el valor (ej. rojo arriba de 30).
4. **Back to dashboard** (arriba) para volver.
5. **Save dashboard** (arriba a la derecha) para guardar. **Si no guardás, se pierde.**

---

## 5. Agregar un gráfico nuevo

1. Arriba → **Add** → **Visualization**.
2. En **Data source** elegí **MQTT — equipo-NN** (el de tu equipo).
3. En la consulta, cambiá a modo **Code** y escribí qué querés ver. Usá el
   **recetario** de abajo.
4. Elegí el tipo de gráfico a la derecha (arriba de las opciones):

| Tipo | Para qué |
|---|---|
| **Time series** | valores que cambian en el tiempo (temperatura, humedad) |
| **Stat** | un número grande (temperatura actual) |
| **Gauge** | un reloj de aguja (nivel de tanque, %) |
| **State timeline** | encendido/apagado en el tiempo (relé, puerta) |
| **Table** | lista de valores |

5. Ponele título, **Back to dashboard** y **Save dashboard**.

---

## 6. Recetario de consultas

Tus datos se llaman siempre **`mqtt_valor`** y tienen dos **etiquetas** (datos
que acompañan a cada valor para poder filtrarlo, como las columnas de una
planilla): `dispositivo` y `magnitud`, que son las partes 2 y 3 de tu topic.

Cómo se lee una consulta: `mqtt_valor{dispositivo="sala"}` quiere decir "los
valores **cuyo** dispositivo sea `sala`". Las llaves `{}` son el filtro.
`avg_over_time(...[1h])` quiere decir "el **promedio** (*average*) de la última
hora".

| Quiero ver… | Consulta |
|---|---|
| todo lo de mi equipo | `mqtt_valor` |
| una magnitud de un dispositivo | `mqtt_valor{dispositivo="sala", magnitud="temperatura"}` |
| todo lo de un dispositivo | `mqtt_valor{dispositivo="sala"}` |
| el promedio de la última hora | `avg_over_time(mqtt_valor{magnitud="temperatura"}[1h])` |
| el máximo del día | `max_over_time(mqtt_valor{magnitud="temperatura"}[24h])` |
| cuántas veces se abrió la puerta hoy | `changes(mqtt_valor{magnitud="reed"}[24h]) / 2` |
| hace cuánto llegó el último dato (s) | `time() - tlast_over_time(mqtt_valor{dispositivo="sala"}[15d])` |
| si la placa está conectada (1/0) | `mqtt_valor{magnitud="conexion"}` |

Para que la leyenda diga algo útil en vez de todas las etiquetas: en **Options →
Legend** poné `{{dispositivo}} · {{magnitud}}`.

---

## 7. Buenas prácticas

- **Antes de cambiar mucho, hacé una copia:** ⚙️ (Settings) → **Save as** →
  ponele otro nombre. Si rompés algo, tenés el original.
- **Guardá seguido.** Grafana guarda versiones: ⚙️ → **Versions** te deja volver
  a una anterior.
- **Un panel = una idea.** Mejor varios paneles chicos que uno con 20 líneas.
- **Poné unidades.** "23.5" no dice nada; "23.5 °C" sí.

---

## 8. Preguntas frecuentes

**No veo mi carpeta.** Puede ser que todavía no entraste nunca a Grafana o que
te cambiaron de equipo. Avisale al profe.

**El panel dice "No data".** Revisá que la placa esté publicando (tabla
**Estado actual**) y que la consulta tenga bien escritos `dispositivo` y
`magnitud` (son en minúsculas, con `_` en vez de espacios o guiones).

**Me equivoqué y borré un panel.** Si no guardaste: recargá la página sin
guardar. Si ya guardaste: ⚙️ → **Versions** → elegí la anterior → **Restore**.

**¿Puedo prender el LED desde Grafana?** No: Grafana es para **ver**. Las
órdenes se mandan desde Node-RED o tu página.

---

## Ahora deberías entender

- Qué es un **dashboard**, un **panel**, una **consulta** y un **datasource**.
- Que Grafana **consulta lo guardado** (no recibe los mensajes directo): por eso
  muestra historia, y por eso no prende LEDs.

**Seguí por acá:**

- Si un panel dice **"No data"** → [Diagnóstico, paso 9](diagnostico.md#paso-9-grafana-consulta-lo-correcto).
- Si querés graficar un valor **calculado** (no lo manda la placa) → [Caso C](node-red-o-grafana.md#caso-c-los-dos-node-red-procesa-grafana-muestra).
- Si querés entender **de dónde salen** los datos que ves → [Seguí un dato](11-arquitectura-iot.md#segui-un-dato-de-punta-a-punta-247-c).
