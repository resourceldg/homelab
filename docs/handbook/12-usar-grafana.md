# 12. Usar Grafana (manual rápido)

🎯 **Objetivo:** entrar al Grafana del aula, entender tu dashboard y
**modificarlo**: agregar gráficos, cambiarlos y guardarlos.

🧩 **Prerequisitos:** Tailscale conectado y tus datos llegando
([manual 11](11-conectar-a-grafana.md)).

---

## 1. Entrar

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

Tus datos se llaman siempre **`mqtt_valor`** y tienen dos etiquetas:
`dispositivo` y `magnitud` (las partes 2 y 3 de tu topic).

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
