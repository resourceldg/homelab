# 8. El pipeline (Git, CI y tests)

🎯 **Objetivo:** entender cómo se cuida la calidad del proyecto de forma
automática, antes de que un cambio llegue al servidor.

🧩 **Prerequisitos:** [cap. 4](04-ansible-iac.md).

> 📝 **Capítulo en desarrollo.**

## Temario
- **Git y Pull Requests (PR):** trabajar en ramas, proponer cambios, revisarlos.
- **CI (Integración Continua):** GitHub Actions corre en cada push/PR.
- **Los chequeos:**
  - *yamllint / ansible-lint* — estilo y buenas prácticas.
  - *Playbook syntax check* — que el playbook parsea (en prod y staging).
  - *Molecule* — prueba roles en contenedores (Ubuntu 22.04 y 24.04).
  - *Tests unitarios* — el validador de política de Compose + los dashboards.
  - *Gitleaks* — busca secretos filtrados.
- **testinfra:** pruebas sobre el server ya provisionado (permisos, servicios…).
- **Idempotencia:** correr el playbook dos veces sin cambios.
- **staging vs. producción:** probar antes de tocar el server real.

## Ideas clave (adelanto)
- Los errores se cazan **antes** de tocar el server (shift-left).
- Nada se afirma "funciona" sin una prueba que lo demuestre.

*(Resumen, errores comunes, preguntas y ejercicios: al completar el capítulo.)*
