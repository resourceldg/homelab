# 4. Ansible e Infraestructura como Código

🎯 **Objetivo:** entender cómo se administra el servidor "como código" con Ansible,
y cómo está organizado este repositorio.

🧩 **Prerequisitos:** [cap. 2](02-fundamentos.md), [cap. 3](03-docker.md).

> 📝 **Capítulo en desarrollo.** Abajo está el temario y las ideas base; se
> ampliará con ejemplos del repo.

## Temario

- **¿Qué es IaC?** Definir la infraestructura en archivos versionables en vez de
  configurar a mano. Ventajas: reproducibilidad, revisión por PR, rollback.
- **Idempotencia:** aplicar el playbook dos veces da el mismo resultado. Por qué
  es seguro re-ejecutar.
- **Piezas de Ansible:**
  - *Playbook* (`site.yml`) — la receta que ordena los roles.
  - *Role* (`roles/*`) — unidad reutilizable (tasks, templates, handlers, defaults).
  - *Handler* — una tarea que corre solo si algo cambió (ej: reiniciar Caddy).
  - *Inventory* (`inventories/production`, `staging`) — a qué máquina y con qué
    variables.
  - *Vault* — secretos cifrados.
- **Las tres capas de variables** de este repo (defaults de rol → group_vars
  compartidos → group_vars por entorno).
- **Cómo se corre:** como usuario `homelab`, con el binario del venv y `-K`
  (sudo con contraseña). Por qué.

## Ideas clave (adelanto)
- El host se **describe**, no se toca a mano.
- Un rol por responsabilidad; `site.yml` los ordena por "planos".
- Idempotencia = re-aplicar es seguro.

*(Resumen, errores comunes, preguntas y ejercicios: al completar el capítulo.)*
