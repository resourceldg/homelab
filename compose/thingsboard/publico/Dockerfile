# Proxy PÚBLICO de los tableros (tableros-proxy). Misma receta que el Caddy
# principal (compose/proxy) pero con versiones fijas y solo el módulo que hace
# falta acá: rate_limit. No necesita DuckDNS: el TLS lo termina Tailscale Funnel.
FROM caddy:2.11.7-builder-alpine AS builder
RUN xcaddy build \
    --with github.com/mholt/caddy-ratelimit@5625512f24f6f59d6f64fb3aafe5eecff0b286db

FROM caddy:2.11.7-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
