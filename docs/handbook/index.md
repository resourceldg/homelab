# Manual de Arquitectura del Homelab

> Un libro de estudio de **Linux, Docker, Observabilidad, DevSecOps e
> Infraestructura como Código**, usando un servidor real (este repositorio) como
> caso de estudio. Está escrito **para principiantes**: no asume que sabés nada.

## ¿Para quién es este manual?

Está pensado para tres tipos de lectores:

1. **Alguien que nunca vio Docker ni un servidor.** Empezá por el principio y leé
   en orden. Cada concepto se explica desde cero.
2. **Alguien que conoce Linux pero no entiende cómo encaja todo.** Podés saltear
   los fundamentos e ir a los capítulos de arquitectura y servicios.
3. **Alguien con experiencia que quiere entender el diseño rápido.** Leé la
   [Visión general](01-vision-general.md) y los "resúmenes" y diagramas de cada
   capítulo.

## Cómo leerlo

Cada capítulo tiene siempre la misma estructura, para que sepas qué esperar:

- 🎯 **Objetivo** — qué vas a poder hacer/entender al terminar.
- 🧩 **Prerequisitos** — qué conviene haber leído antes.
- 🆕 **Conceptos nuevos** — las palabras nuevas que aparecen.
- 📖 **Desarrollo** — la explicación, con dibujos.
- 🧠 **Ideas clave** — lo que no te tenés que olvidar.
- ⚠️ **Errores comunes** — en qué se tropieza todo el mundo.
- ❓ **Preguntas de repaso** — para chequear que entendiste.
- 🛠️ **Ejercicios** — para practicar.

> **Convención:** cuando veas una palabra en **negrita** por primera vez, casi
> siempre está también en el [Glosario](glosario.md) con una definición simple y
> una técnica.

## Filosofía del manual

No describimos archivos: explicamos **por qué existen**. Para cada decisión de
diseño respondemos:

- ¿Qué problema resuelve?
- ¿Cómo interactúa con lo demás?
- ¿Qué pasaría si no existiera?
- ¿Qué alternativas había y por qué se eligió ésta?

Cuando algo es una decisión mejorable, lo marcamos como **💡 Posible mejora
arquitectónica**.

## Índice del libro

| # | Capítulo | De qué trata |
|---|---|---|
| 1 | [Visión general](01-vision-general.md) | Qué es el laboratorio y sus "planos" (host, servicios, aula) |
| 2 | [Fundamentos](02-fundamentos.md) | Computación, Linux y redes desde cero |
| 3 | [Docker y contenedores](03-docker.md) | Imágenes, contenedores, Compose, redes, volúmenes, cgroups |
| 4 | [Ansible e IaC](04-ansible-iac.md) | Infraestructura como código, playbooks, roles, idempotencia |
| 5 | [Los servicios uno por uno](05-servicios.md) | Caddy, Prometheus, Grafana, Tailscale, Postgres, Authelia… |
| 6 | [Observabilidad](06-observabilidad.md) | Métricas, PromQL, dashboards |
| 7 | [Seguridad](07-seguridad.md) | Defensa en profundidad: SSH, firewall, AppArmor, SSO |
| 8 | [El pipeline](08-pipeline.md) | Git, PR, CI, lint, tests, idempotencia |
| 9 | [La plataforma de aula](09-plataforma-aula.md) | `labctl`, aislamiento, política, cuotas |
| 10 | [Casos prácticos](10-casos-practicos.md) | Recorridos paso a paso ante problemas reales |
| — | [Guía práctica del equipo](guia-equipo.md) | Cómo trabajar en tu proyecto: conectarte, config, base compartida, salir a la web |
| — | [Glosario](glosario.md) | Todas las palabras y siglas, de la A a la Z |
| — | [Mejoras futuras](mejoras-futuras.md) | Deuda de documentación y mejoras propuestas |

## Cómo verlo como libro

Este manual está preparado para **[MkDocs Material](https://squidfunk.github.io/mkdocs-material/)**:

```bash
pip install mkdocs-material
mkdocs serve       # abrí http://127.0.0.1:8000
```

También se lee directo en GitHub (los diagramas Mermaid se renderizan solos) y se
puede exportar a PDF.
