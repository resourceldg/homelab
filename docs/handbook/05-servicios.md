# 5. Los servicios uno por uno

🎯 **Objetivo:** conocer cada servicio del laboratorio: qué es, para qué sirve,
quién lo inicia, qué consume, qué expone, de qué depende y qué pasa si se cae.

🧩 **Prerequisitos:** [cap. 3](03-docker.md).

> 📝 **Capítulo en desarrollo.** Cada servicio se documentará con la misma ficha.

## Ficha por servicio (plantilla)
Para cada uno: *qué es · para qué sirve · quién lo inicia · dónde corre · qué
consume · qué expone · de qué depende · qué archivos usa · cómo monitorearlo ·
cómo detectar fallas · cómo reiniciarlo · qué pasa si se cae · alternativas.*

## Servicios a cubrir
- **Caddy** — proxy inverso + HTTPS automático (ACME + DuckDNS DNS-01) + login
  (forward_auth a Authelia) + publicación de apps de alumnos.
- **Prometheus** — recolecta y guarda métricas (ver [cap. 6](06-observabilidad.md)).
- **node-exporter** — métricas del host.
- **cAdvisor** — métricas por contenedor.
- **Grafana** — dashboards (detrás de Authelia, anónimo-Viewer).
- **Homepage** — el "launchpad" con enlaces a todo.
- **Tailscale** — red privada (tailnet) para acceso remoto.
- **DuckDNS** — dominio dinámico gratis.
- **dnsmasq** — Split DNS del operador (resuelve el dominio al tailnet).
- **PostgreSQL / Redis / Mailpit** — servicios de datos compartidos multi-tenant.
- **Authelia** — SSO (login único con grupos).
- **labctld** — el broker del aula (ver [cap. 9](09-plataforma-aula.md)).

*(Fichas completas: al desarrollar el capítulo.)*
