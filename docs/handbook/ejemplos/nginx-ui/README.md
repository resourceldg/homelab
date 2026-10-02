# Ejemplo: UI propia con nginx (además de Node-RED)

Servís tu propia página (HTML/JS/CSS) con nginx, dentro de tu proyecto. nginx
además hace de **puente a tu Node-RED** en `/api/...` y `/ws/...`, así la página
y la API salen del mismo origen (sin CORS) y alcanza con un solo túnel extra.

Lo usó primero equipo-03: botón que prende el LED de la ESP32 y foco que muestra
en vivo lo que la placa confirma.

## Dónde va cada cosa (en el server, carpeta de tu equipo)

| Archivo | Ruta | Para qué |
|---|---|---|
| tu página | `/srv/classroom/equipo-NN/web/index.html` | lo que ve el navegador; editalo vos |
| config nginx | `/srv/classroom/equipo-NN/nginx/default.conf` | sirve `web/` y el puente a Node-RED |
| servicio | `/srv/classroom/equipo-NN/compose.yml` | agregá el servicio `web` (abajo) |

## Servicio a agregar en `compose.yml`

El puerto del host tiene que ser **distinto por equipo** (no se repiten en el
server): usá `80NN` (equipo-01 → `8081`, equipo-03 → `8083`).

```yaml
  web:
    image: nginx:1.27-alpine
    restart: unless-stopped
    depends_on: [nodered]
    ports:
      - "127.0.0.1:80NN:80"
    volumes:
      - ./web:/usr/share/nginx/html:ro
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
    logging:
      driver: json-file
      options: { max-size: "10m", max-file: "3" }
    deploy:
      resources:
        limits: { cpus: "0.25", memory: 64M, pids: 50 }
```

Después: `labctl validate && labctl up`.

## En Node-RED (los endpoints que usa la página)

- `http in` **POST** `/api/led` → `function` (convierte `{estado: 1}` en `"1"`) →
  `mqtt out` `equipo-NN/led` **y** `http response`.
- `http in` **GET** `/api/led` → `function` (devuelve `flow.get("estado")`) → `http response`.
- `mqtt in` `equipo-NN/led/estado` → `function` (`flow.set("estado", msg.payload)`) →
  `websocket out` (listener en `/ws/led`).

## Cómo entrar (desde tu compu, sobre Tailscale)

```
ssh -L 1880:localhost:<puerto-nodered> -L 8080:localhost:80NN <usuario>@100.110.123.76
```

Navegador → `http://localhost:8080` (tu UI) y `http://localhost:1880` (Node-RED).

> **No publicar** este nginx en internet si el puente `/api` o `/ws` llega a algo
> que modifique cosas: cualquiera podría prender tu LED. Y nunca hagas pasar el
> editor de Node-RED (`/`) por el puente: editor sin login = control total.
