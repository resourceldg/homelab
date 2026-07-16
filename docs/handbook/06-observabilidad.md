# 6. Observabilidad

🎯 **Objetivo:** entender qué significa "observar" un sistema y cómo se hace acá
con Prometheus y Grafana.

🧩 **Prerequisitos:** [cap. 3](03-docker.md), [cap. 5](05-servicios.md).

> 📝 **Capítulo en desarrollo.**

## Temario
- **¿Qué es observar?** Saber qué está pasando adentro del sistema desde afuera.
  Los tres pilares: **métricas**, **logs** y **traces** (acá se usan métricas y
  logs).
- **Métrica y serie temporal:** un número medido a lo largo del tiempo, con
  etiquetas (ej: RAM del contenedor `equipo-01-web-1`).
- **Exporters:** `node-exporter` (host) y `cAdvisor` (contenedores) exponen
  métricas; **Prometheus** las "scrapea" (las va a buscar) y las guarda.
- **PromQL:** el lenguaje para consultarlas. Ejemplo de agregación por equipo con
  `label_replace` sobre el nombre del contenedor.
- **Grafana y dashboards:** paneles que consultan Prometheus. Los 3 dashboards del
  aula (Overview, Team Detail, Capacity) y cómo leerlos.

## Ideas clave (adelanto)
- Prometheus **guarda**, Grafana **muestra**.
- Todo se agrega por equipo a partir del nombre `equipo-NN-*`.

*(Resumen, errores comunes, preguntas y ejercicios: al completar el capítulo.)*
