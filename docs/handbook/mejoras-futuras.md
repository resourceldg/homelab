# Mejoras futuras del manual

Registro honesto de lo que **falta** o se puede **mejorar** en esta documentación.
Mantenerlo al día evita "documentación fantasma".

## Capítulos por completar
- **Cap. 4 (Ansible/IaC):** desarrollar con ejemplos reales de roles del repo.
- **Cap. 5 (Servicios):** completar la ficha de cada servicio.
- **Cap. 6 (Observabilidad):** ejemplos de PromQL y lectura de los 3 dashboards.
- **Cap. 7 (Seguridad):** desarrollar cada capa con referencias al código.
- **Cap. 8 (Pipeline):** recorrer un PR real de punta a punta.
- **Cap. 10 (Casos prácticos):** sumar los casos listados (disco lleno,
  Prometheus caído, unhealthy, DuckDNS, sin Internet).

## Diagramas por agregar
- Flujo de despliegue de Ansible (paso a paso).
- Flujo de métricas (exporter → Prometheus → Grafana) en detalle.
- Flujo de backups (Borg/borgmatic).
- Flujo completo de un login SSO (navegador → Caddy → Authelia → servicio).

## Glosario
- Revisar que **todo** término en negrita del libro tenga entrada.
- Agregar: namespace, WireGuard, DERP, forward-auth, argon2/sha512crypt, loopback,
  RSS/RES (memoria), recording rule, alerta.

## 💡 Posibles mejoras arquitectónicas (marcadas en el libro)
- Rotación de los secretos de Authelia/SSO (se generaron en sesión).
- Alertas en Grafana/Prometheus (hoy hay dashboards, no alertas).
- Cuota de disco por-contenedor además de por-equipo.
- SMTP real para el reset de contraseñas de Authelia (hoy es file notifier).
- Tests de exposición de puertos más exhaustivos.

## Formato / publicación
- Verificar el build con `mkdocs build --strict`.
- Exportar a PDF (por ejemplo con el plugin `mkdocs-with-pdf`).
- Portada, licencia y numeración de figuras para la versión libro.

> ¿Encontraste algo mal explicado o faltante? Anotalo acá con una línea; es parte
> del mantenimiento del manual.
