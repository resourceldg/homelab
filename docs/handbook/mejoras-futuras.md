# Mejoras futuras del manual

Registro honesto de lo que **falta** o se puede **mejorar** en esta documentación.
Mantenerlo al día evita "documentación fantasma".

## Hecho en la revisión de octubre 2026
- Parte III (IoT aplicado): capítulos 11 a 14, y capítulo 15 (ciclo de vida y madurez).
- Capítulo 10: seis casos reales de las placas y la red.
- Glosario: vocabulario IoT, MQTT y ciclo de vida.
- Guía del equipo: puertos por equipo, Tailscale, broker del aula.
- Créditos y autoría.

## Hecho en la segunda tanda (octubre 2026)
- Capítulos 4 a 8 completos (Ansible, servicios, observabilidad, seguridad, pipeline).
- Pasada de lenguaje en los capítulos 2, 3 y 9: cada sigla explicada, partiendo de lo cercano.
- Documentos de operación traducidos al español y actualizados (`README`,
  `architecture`, `deployment-guide`, `runbook`).
- El CI ahora corre también los tests de `shared-data` y `aula-iot`.

## Pendiente
- **Anclas en GitHub:** los enlaces a secciones (`#...`) del manual siguen el
  formato de MkDocs (sin acentos). En el sitio funcionan; leyendo el `.md` directo
  en GitHub, los de títulos con acentos o rayas no saltan a la sección.
- **Capítulo 10:** sumar los casos listados (disco lleno, Prometheus caído,
  contenedor `unhealthy`, DuckDNS, servidor sin internet) a medida que pasen.

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
- Alertas en Grafana/Prometheus (hoy hay dashboards, no alertas). Primera: "la
  placa del equipo X no publica hace 15 minutos".
- Tablero público para la muestra (salida filtrada, ver `docs/aula-iot.md`).
- Cuota de disco por-contenedor además de por-equipo.
- SMTP real para el reset de contraseñas de Authelia (hoy es file notifier).
- Tests de exposición de puertos más exhaustivos.

## Formato / publicación
- Verificar el build con `mkdocs build --strict`.
- Exportar a PDF (por ejemplo con el plugin `mkdocs-with-pdf`).
- Portada, licencia y numeración de figuras para la versión libro.

> ¿Encontraste algo mal explicado o faltante? Anotalo acá con una línea; es parte
> del mantenimiento del manual.
