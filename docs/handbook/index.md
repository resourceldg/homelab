# Manual de Arquitectura del Homelab

> Un libro de estudio de **arquitectura de software aplicada al diseño IoT**:
> cómo se piensa, se construye y se cuida un sistema que conecta placas, mensajes,
> datos y pantallas. Usa como caso real el servidor del aula (este repositorio) y
> los proyectos de los equipos. Está escrito **para principiantes**: no asume que
> sabés nada, y cada sigla se explica la primera vez que aparece.
>
> **Autor:** Lucas D. Gómez, arquitecto de software · [Créditos y autoría](creditos.md)

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

**Aprendemos desde lo cercano.** Cada tema arranca por algo que ya conocés (un
grupo de WhatsApp, el tablero de un auto, una bici) o por un proyecto de un
compañero, y recién después aparece la palabra técnica. Ninguna sigla se da por
sabida: la primera vez se explica, y siempre está en el [Glosario](glosario.md).

No describimos archivos: explicamos **por qué existen**. Para cada decisión de
diseño respondemos:

- ¿Qué problema resuelve?
- ¿Cómo interactúa con lo demás?
- ¿Qué pasaría si no existiera?
- ¿Qué alternativas había y por qué se eligió ésta?

Cuando algo es una decisión mejorable, lo marcamos como **💡 Posible mejora
arquitectónica**.

## Índice del libro

El libro se lee en cuatro partes. Si sos alumno y querés **conectar tu placa ya**,
podés ir directo a la Parte III y volver a las otras cuando las necesites.

```mermaid
flowchart LR
  P1["Parte I<br/>Bases"] --> P2["Parte II<br/>La plataforma"] --> P3["Parte III<br/>IoT aplicado"] --> P4["Parte IV<br/>Operar y evolucionar"]
  P4 -. "lo que se aprende vuelve a empezar" .-> P1
```

### Parte I — Bases

| # | Capítulo | De qué trata |
|---|---|---|
| 1 | [Visión general](01-vision-general.md) | Qué es el laboratorio y sus "planos" (host, servicios, aula, IoT) |
| 2 | [Fundamentos](02-fundamentos.md) | Computación, Linux y redes desde cero |
| 3 | [Docker y contenedores](03-docker.md) | Imágenes, contenedores, Compose, redes, volúmenes |
| 4 | [Ansible e IaC](04-ansible-iac.md) | Infraestructura como código *(en desarrollo)* |

### Parte II — La plataforma

| # | Capítulo | De qué trata |
|---|---|---|
| 5 | [Los servicios uno por uno](05-servicios.md) | Caddy, Grafana, Tailscale, Postgres, el broker… *(en desarrollo)* |
| 6 | [Observabilidad](06-observabilidad.md) | Medir, guardar y mostrar *(en desarrollo)* |
| 7 | [Seguridad](07-seguridad.md) | Defensa en capas *(en desarrollo)* |
| 8 | [El pipeline](08-pipeline.md) | Git, revisión, pruebas automáticas *(en desarrollo)* |
| 9 | [La plataforma de aula](09-plataforma-aula.md) | `labctl`, aislamiento, servicios compartidos |
| — | [Guía práctica del equipo](guia-equipo.md) | **Tu día a día:** conectarte, tus puertos, MQTT, tu página web |

### Parte III — IoT aplicado

| # | Capítulo | De qué trata |
|---|---|---|
| 11 | [Arquitectura IoT del aula](11-arquitectura-iot.md) | **La columna del libro:** las 6 capas y las 9 decisiones de diseño |
| 12 | [Conectar tus sensores a Grafana](12-conectar-a-grafana.md) | Las 3 reglas del topic, ejemplos en MicroPython y Arduino |
| 13 | [Usar Grafana](13-usar-grafana.md) | Leer y editar el tablero de tu equipo |
| 14 | [Los proyectos de los equipos](14-proyectos-de-los-equipos.md) | El LED, la puerta y el enchufe como casos de diseño |

### Parte IV — Operar y evolucionar

| # | Capítulo | De qué trata |
|---|---|---|
| 10 | [Casos prácticos](10-casos-practicos.md) | Nueve problemas reales y cómo se resolvieron |
| 15 | [Ciclo de vida y madurez](15-ciclo-de-vida-y-madurez.md) | Cómo nace y crece el sistema, sus stacks y qué tan maduro está |

### Para consultar

| | | |
|---|---|---|
| — | [Glosario](glosario.md) | Todas las palabras y siglas, de la A a la Z |
| — | [Créditos y autoría](creditos.md) | Quién hizo qué |
| — | [Mejoras futuras](mejoras-futuras.md) | Lo que falta, anotado |

## Cómo verlo como libro

Este manual está preparado para **[MkDocs Material](https://squidfunk.github.io/mkdocs-material/)**:

```bash
pip install mkdocs-material
mkdocs serve       # abrí http://127.0.0.1:8000
```

También se lee directo en GitHub (los diagramas Mermaid se renderizan solos) y se
puede exportar a PDF.
