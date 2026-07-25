# Custom Caddy build:
#   - duckdns:    DNS-01 ACME (wildcard, sin puerto 80)
#   - ratelimit:  limitar peticiones por IP en la API del pañol expuesta a
#                 internet — frena fuerza bruta del token y abuso/DoS antes de
#                 que el request toque la aplicación.
FROM caddy:2-builder AS builder
RUN xcaddy build \
    --with github.com/caddy-dns/duckdns \
    --with github.com/mholt/caddy-ratelimit

FROM caddy:2
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
