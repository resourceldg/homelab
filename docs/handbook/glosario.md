# Glosario

Cada entrada tiene una **definición simple**, una **técnica** y **dónde aparece**
en este proyecto (en los términos centrales, **qué significa en el aula**). Ordenado alfabéticamente.

> La definición **simple** está pensada para leerla primero, sin saber nada de
> sistemas. La **técnica** es la que vas a encontrar en internet o en un libro.

### ACL (Access Control List)
- **Simple:** una lista de reglas de "quién puede hacer qué".
- **Técnica:** conjunto de reglas de autorización asociadas a un recurso.
- **Dónde:** las reglas SSH de Tailscale (modo `check` vs `accept`); las reglas de
  acceso por grupo de Authelia.

### ACME
- **Simple:** el protocolo para pedir certificados HTTPS automáticamente.
- **Técnica:** *Automated Certificate Management Environment*; lo usan Let's
  Encrypt y ZeroSSL.
- **Dónde:** Caddy lo usa (con el desafío DNS-01 de DuckDNS) para emitir/renovar
  los certificados solo.

### Actuador
- **Simple:** la parte que **hace** algo en el mundo físico cuando recibe una orden (los "músculos").
- **Técnica:** dispositivo que convierte una señal eléctrica en una acción: luz, movimiento, corte de corriente.
- **Dónde:** el LED de Mijael, el relé del enchufe de Jorge. Ver [cap. 11](11-arquitectura-iot.md).

### AIDE
- **Simple:** un "detector de cambios" en archivos del sistema.
- **Técnica:** *Advanced Intrusion Detection Environment*; guarda huellas de los
  archivos y avisa si cambian.
- **Dónde:** rol `audit`, corre por un timer.

### Ansible
- **Simple:** una herramienta para configurar servidores escribiendo archivos.
- **Técnica:** motor de automatización/IaC sin agente, declarativo e idempotente.
- **Dónde:** todo el plano del host. Ver [cap. 4](04-ansible-iac.md).

### API (Application Programming Interface)
- **Simple:** la "puerta acordada" por la que un programa le pide cosas a otro.
- **Técnica:** interfaz de programación: conjunto de operaciones, formatos y reglas que un componente expone a otros.
- **Dónde:** `POST /api/led` en el Node-RED de los equipos; el contrato de topics también funciona como API.

### AppArmor
- **Simple:** un "chaleco" que limita qué puede hacer cada programa.
- **Técnica:** módulo de seguridad del kernel (MAC) basado en perfiles por
  programa.
- **Dónde:** rol `apparmor`, en modo enforce.

### Autenticación
- **Simple:** probar **quién sos** (usuario y contraseña, una clave).
- **Técnica:** verificación de identidad de un usuario o sistema.
- **En el aula:** hay cuatro puertas, cada una con su llave: Tailscale, SSH, el login web y el usuario MQTT. Ver [las 4 capas](red-y-accesos.md#5-por-que-me-autentico-tantas-veces).

### Authelia
- **Simple:** el portal de login único (SSO) del laboratorio.
- **Técnica:** servidor de autenticación/forward-auth con reglas por grupo.
- **Dónde:** stack `auth`, integrado a Caddy con `forward_auth`. Ver
  [cap. 7](07-seguridad.md).

### Autorización
- **Simple:** decidir **qué podés hacer** una vez que se sabe quién sos.
- **Técnica:** control de permisos sobre recursos para una identidad ya autenticada.
- **En el aula:** solo tu carpeta, solo tus topics `equipo-NN/...`, solo el Grafana de tu equipo. Ver [Red y accesos](red-y-accesos.md#las-4-capas).

### Backup
- **Simple:** una copia de seguridad de los datos.
- **Técnica:** respaldo versionado y cifrado (aquí, con Borg/borgmatic).
- **Dónde:** rol `backups`; requiere un disco montado en `/mnt/backup`.

### Bind mount
- **Simple:** montar una carpeta del server dentro de un contenedor.
- **Técnica:** mapeo directo de una ruta del host a una ruta del contenedor.
- **Dónde:** los alumnos guardan datos así (obligatorio por la política).

### Broker (MQTT)
- **Simple:** el "cartero" que recibe los mensajes y se los reparte a quien los quiere (como el servidor de WhatsApp).
- **Técnica:** servidor intermediario del modelo publicar/suscribir: recibe publicaciones y las entrega a los suscriptores de cada topic.
- **En el aula:** `mqtt-aula`. Tu ESP32 y tu Node-RED se conectan a él; él reparte cada mensaje a quien esté suscripto (Telegraf, tu Node-RED, MQTT Explorer). Ver [Seguí un dato](11-arquitectura-iot.md#segui-un-dato-de-punta-a-punta-247-c).

### Caddy
- **Simple:** el portero web: recibe todo y reparte, con HTTPS automático.
- **Técnica:** servidor web / proxy inverso con gestión automática de TLS.
- **Dónde:** stack `proxy`; única entrada web. Ver [cap. 5](05-servicios.md).

### cAdvisor
- **Simple:** mide cuánto consume cada contenedor.
- **Técnica:** *Container Advisor*; exporta métricas por contenedor a Prometheus.
- **Dónde:** stack `monitoring`.

### cgroup
- **Simple:** un mecanismo para limitar recursos de un grupo de procesos.
- **Técnica:** *control group* del kernel (v2); limita CPU/RAM/PIDs.
- **Dónde:** límites de compose + slices de systemd por equipo.

### CI (Integración Continua)
- **Simple:** robots que revisan tu código cada vez que subís cambios.
- **Técnica:** pipeline automatizado (lint, tests) en cada push/PR.
- **Dónde:** GitHub Actions (`.github/workflows/ci.yml`). Ver [cap. 8](08-pipeline.md).

### Ciclo de vida
- **Simple:** el recorrido de un sistema: se necesita, se diseña, se construye, se usa, se mira y se mejora, una y otra vez.
- **Técnica:** SDLC (*Software Development Life Cycle*): etapas iterativas de desarrollo y operación de un sistema.
- **Dónde:** [cap. 15](15-ciclo-de-vida-y-madurez.md).

### Commit
- **Simple:** una "foto" de los cambios de un proyecto, con un mensaje que explica por qué se hicieron.
- **Técnica:** registro atómico en la historia de Git (cambios + autor + fecha + mensaje).
- **Dónde:** cada cambio de este repositorio. Ver [cap. 8](08-pipeline.md).

### Compose (Docker Compose)
- **Simple:** describir contenedores en un archivo y prenderlos juntos.
- **Técnica:** herramienta para definir apps multi-contenedor en YAML.
- **Dónde:** todo el plano de servicios (`compose/`).

### Contenedor
- **Simple:** una imagen en ejecución, aislada.
- **Técnica:** proceso(s) aislados con namespaces + cgroups.
- **En el aula:** cada servicio del servidor corre en uno: `mqtt-aula`, `grafana-aula`, y el Node-RED de tu equipo (`equipo-04-nodered-1`). Los levantás con `labctl up`. Ver [cap. 3](03-docker.md).

### Contrato (de mensajes)
- **Simple:** el acuerdo escrito de "cómo nos vamos a hablar": qué nombre tiene cada mensaje y qué formato lleva.
- **Técnica:** especificación de la interfaz entre productores y consumidores (estructura de topics, formato y semántica del payload).
- **Dónde:** `equipo-NN/dispositivo/magnitud`. Ver [cap. 12](12-conectar-a-grafana.md#las-3-reglas).

### CPU (Central Processing Unit)
- **Simple:** el "cocinero" de la computadora: el que hace las cuentas y sigue las instrucciones.
- **Técnica:** unidad central de procesamiento; cada núcleo ejecuta instrucciones en paralelo.
- **Dónde:** el servidor tiene 4 núcleos. Ver [cap. 2](02-fundamentos.md).

### Credencial
- **Simple:** lo que usás para probar quién sos: un usuario con su contraseña, una clave, un token.
- **Técnica:** dato secreto que autentica a un usuario o sistema.
- **En el aula:** tenés cuatro distintas (tailnet, aula, MQTT del equipo, WiFi). Ver [la tabla](red-y-accesos.md#tus-credenciales-en-una-tabla).

### Daemon
- **Simple:** un servicio que corre de fondo, permanente.
- **Técnica:** proceso en segundo plano (suele terminar en `d`).
- **Dónde:** `dockerd`, `sshd`, `tailscaled`, `labctld`, `dnsmasq`.

### Dashboard
- **Simple:** un tablero con gráficos.
- **Técnica:** conjunto de paneles de visualización (en Grafana).
- **En el aula:** hay dos tipos: el de **Node-RED** (`localhost:1880/dashboard`, para controlar en vivo) y el de **Grafana** (para ver la historia). Ver [¿Node-RED, Grafana o ambos?](node-red-o-grafana.md).

### Datasource (fuente de datos)
- **Simple:** la base de datos a la que un panel de Grafana le hace preguntas.
- **Técnica:** conexión configurada en Grafana hacia un origen de datos.
- **En el aula:** la tuya es **MQTT — equipo-NN**: consulta VictoriaMetrics y solo ve los datos de tu equipo. Ver [cap. 13](13-usar-grafana.md).

### DDNS / DuckDNS
- **Simple:** mantener un dominio apuntando a tu casa aunque cambie tu IP.
- **Técnica:** DNS dinámico; DuckDNS es un proveedor gratuito.
- **Dónde:** rol `ddns`, con un timer que actualiza la IP.

### Defensa en profundidad
- **Simple:** varias medidas de seguridad independientes, para que romper una no alcance (como en un boliche: puerta, patovica, pulsera, cámaras).
- **Técnica:** estrategia de seguridad en capas con controles redundantes e independientes.
- **Dónde:** las 9 capas del [cap. 7](07-seguridad.md).

### Deuda técnica
- **Simple:** lo que se hizo rápido "para salir del paso" y algún día hay que rehacer bien.
- **Técnica:** costo futuro acumulado por elegir una solución rápida en lugar de la adecuada; genera "intereses" en forma de trabajo y riesgo.
- **Dónde:** los flows de Node-RED armados a mano. Ver [cap. 15](15-ciclo-de-vida-y-madurez.md).

### DevSecOps
- **Simple:** desarrollar, asegurar y operar, todo integrado y automatizado.
- **Técnica:** cultura/práctica que integra seguridad en el ciclo Dev+Ops.
- **Dónde:** el pipeline (CI, lint, tests, gitleaks). Ver [cap. 8](08-pipeline.md).

### DNS
- **Simple:** la guía telefónica que traduce nombres a IPs.
- **Técnica:** *Domain Name System*.
- **En el aula:** `homelab-01.tail4eda13.ts.net` (el nombre que usa tu placa) y `grafana-aula.lucasland.duckdns.org` (el que usás vos) se traducen a direcciones IP. Dentro del tailnet, el segundo apunta a la IP privada del servidor (Split DNS).

### Docker
- **Simple:** empaquetar y correr apps en contenedores.
- **Técnica:** plataforma de contenedores (engine + CLI + formatos).
- **Dónde:** el corazón del plano de servicios y de aula. Ver [cap. 3](03-docker.md).

### Drift (deriva)
- **Simple:** cuando el servidor real ya no es lo que dicen los archivos, porque alguien cambió algo a mano.
- **Técnica:** divergencia entre el estado declarado (IaC) y el estado real de la infraestructura.
- **Dónde:** el broker del aula existió unos días solo en el servidor. Ver [cap. 4](04-ansible-iac.md).

### Endpoint
- **Simple:** una "puerta" con dirección a la que un programa le manda pedidos.
- **Técnica:** URL o dirección de un servicio que acepta peticiones.
- **En el aula:** `POST /api/led` en el Node-RED de los equipos con página propia; para el broker, `homelab-01.tail4eda13.ts.net:10000`.

### ESP32
- **Simple:** una placa chiquita y barata, con WiFi, que se programa para leer sensores y manejar actuadores.
- **Técnica:** microcontrolador de Espressif con WiFi/Bluetooth, doble núcleo, programable en C++ (Arduino) o MicroPython.
- **Dónde:** las placas de todos los equipos.

### Exporter
- **Simple:** un programita que "traduce" métricas a un formato que Prometheus
  entiende.
- **Técnica:** endpoint HTTP que expone métricas en formato Prometheus.
- **Dónde:** `node-exporter` (host), `cAdvisor` (contenedores).

### Fail2ban
- **Simple:** el que echa por un rato a quien prueba contraseñas una y otra vez.
- **Técnica:** servicio que analiza logs y bloquea IPs con demasiados intentos fallidos.
- **Dónde:** 4 intentos en 10 min → bloqueo de 1 h. Ver [cap. 7](07-seguridad.md).

### Filesystem
- **Simple:** cómo se organizan los archivos en el disco.
- **Técnica:** estructura jerárquica desde `/`.
- **Dónde:** `/opt/homelab/stacks`, `/srv/classroom`, loopbacks de cuota.

### Firmware
- **Simple:** el programa que vive **adentro** de un aparato (la placa).
- **Técnica:** software grabado en la memoria no volátil de un dispositivo embebido.
- **Dónde:** el `main.py` de MicroPython o el `.ino` de Arduino.

### Flujo (flow)
- **Simple:** en Node-RED, un dibujo de cajitas conectadas que dice "cuando pasa esto, hacé aquello".
- **Técnica:** grafo de nodos que procesa mensajes en Node-RED.
- **En el aula:** el flujo del interruptor del LED: `ui-switch` → `mqtt out`. Ver [¿Node-RED, Grafana o ambos?](node-red-o-grafana.md).

### Funnel (Tailscale Funnel)
- **Simple:** un "portero" en internet que recibe a las placas y las hace pasar al servidor sin abrir puertas del router.
- **Técnica:** servicio de Tailscale que publica un puerto local en internet (443, 8443 o 10000) mediante una conexión saliente, con TLS.
- **Dónde:** `homelab-01.tail4eda13.ts.net:10000` → `mqtt-aula`; `:8443` → API del pañol.

### Git
- **Simple:** el programa que guarda la historia de un proyecto: cada cambio, quién, cuándo y por qué.
- **Técnica:** sistema de control de versiones distribuido.
- **Dónde:** todo el repositorio. Ver [cap. 8](08-pipeline.md).

### GPIO (General Purpose Input/Output)
- **Simple:** las patitas de la placa: cada una puede **leer** si hay corriente o **dar** corriente.
- **Técnica:** pines digitales de entrada/salida de propósito general de un microcontrolador.
- **Dónde:** `Pin(2, Pin.OUT)` (LED), `Pin(27, Pin.IN, Pin.PULL_UP)` (reed).

### Grafana
- **Simple:** la app que muestra los gráficos de las métricas.
- **Técnica:** plataforma de visualización de series temporales.
- **Dónde:** stack `monitoring`, detrás de Authelia.

### Handler (Ansible)
- **Simple:** una tarea que corre solo si otra avisó que algo cambió ("si cambió la config, reiniciá").
- **Técnica:** tarea notificada que se ejecuta al final si hubo cambios.
- **Dónde:** reiniciar Caddy si cambió el Caddyfile. Ver [cap. 4](04-ansible-iac.md).

### Hardening (endurecimiento)
- **Simple:** sacar o ajustar todo lo que un sistema trae "por si acaso" y no hace falta.
- **Técnica:** reducción de la superficie de ataque mediante configuración segura (p. ej., guía CIS).
- **Dónde:** rol `hardening`. Ver [cap. 7](07-seguridad.md).

### HTTPS / TLS
- **Simple:** la web con candado (cifrada).
- **Técnica:** HTTP sobre TLS; requiere un certificado válido.
- **Dónde:** lo maneja Caddy automáticamente.

### IaC (Infraestructura como Código)
- **Simple:** definir la infraestructura en archivos de texto versionables.
- **Técnica:** gestionar servidores/servicios de forma declarativa y reproducible.
- **Dónde:** todo el repo (Ansible + Compose).

### Idempotencia
- **Simple:** aplicar algo dos veces da el mismo resultado que una.
- **Técnica:** propiedad que garantiza convergencia sin efectos acumulativos.
- **Dónde:** todos los playbooks de Ansible.

### Imagen
- **Simple:** la plantilla de una app (molde).
- **Técnica:** artefacto de solo lectura en capas.
- **Dónde:** cada `image:` de los compose.

### inode
- **Simple:** la ficha interna de un archivo en el disco.
- **Técnica:** estructura del filesystem con metadatos y punteros a los datos.
- **Dónde:** el bug del Caddyfile (bind mount al inode viejo). Ver [cap. 10](10-casos-practicos.md).

### Inventario (Ansible)
- **Simple:** la lista de a qué servidores se aplica la configuración y con qué datos propios.
- **Técnica:** definición de hosts y variables por grupo/entorno.
- **Dónde:** `inventories/production` y `staging`. Ver [cap. 4](04-ansible-iac.md).

### IoT (Internet of Things)
- **Simple:** Internet de las Cosas: objetos físicos conectados a una red que miden o hacen algo.
- **Técnica:** red de dispositivos físicos con sensores/actuadores y conectividad que intercambian datos con otros sistemas.
- **Dónde:** todos los proyectos de placas del aula. Ver [cap. 11](11-arquitectura-iot.md).

### JSON
- **Simple:** una forma de escribir datos ordenados con nombre y valor, que entienden casi todos los programas: `{"temp": 22.1}`.
- **Técnica:** *JavaScript Object Notation*: formato de texto para datos estructurados (objetos, listas, números, textos).
- **Dónde:** mensajes con varios valores a la vez (cap. 12, regla 2).

### labctl / labctld
- **Simple:** la única herramienta con la que los alumnos manejan sus contenedores.
- **Técnica:** cliente + daemon broker (Python) que valida y ejecuta compose.
- **Dónde:** roles `labctl`. Ver [cap. 9](09-plataforma-aula.md).

### LAN
- **Simple:** tu red local (casa, aula).
- **Técnica:** *Local Area Network*, con IPs privadas.
- **Dónde:** `lan_cidr: 192.168.100.0/24`.

### Last Will (último deseo)
- **Simple:** lo que el broker publica **por vos** si tu placa se desconecta de golpe: "avisen que me quedé sin batería".
- **Técnica:** mensaje que el cliente MQTT registra al conectarse y el broker publica si la conexión se pierde sin desconexión limpia.
- **Dónde:** `equipo-NN/<placa>/conexion` = `offline`. Ver [cap. 12](12-conectar-a-grafana.md).

### Lint
- **Simple:** revisar el código buscando errores de estilo o cosas sospechosas, sin ejecutarlo (como sacarle la pelusa a la ropa).
- **Técnica:** análisis estático de código o configuración.
- **Dónde:** yamllint y ansible-lint en el CI. Ver [cap. 8](08-pipeline.md).

### Log (registro)
- **Simple:** el cuaderno donde un programa anota lo que va pasando.
- **Técnica:** flujo de eventos con marca de tiempo emitido por un proceso, usado para diagnóstico y auditoría.
- **Dónde:** `docker logs mqtt-aula` (quién se conectó y si lo rechazó). Ver [cap. 10](10-casos-practicos.md).

### Loki
- **Simple:** el archivo de logs: guarda los registros de todos los contenedores para buscarlos desde Grafana.
- **Técnica:** sistema de agregación de logs de Grafana Labs, indexado por etiquetas.
- **Dónde:** stack `logs`, prendido a pedido (`make logs-on`).

### Madurez
- **Simple:** qué tan confiable y cuidada está una parte del sistema, del 0 (idea) al 5 (mejora sola).
- **Técnica:** grado de estabilidad, reproducibilidad, verificación y operación de un componente.
- **Dónde:** [cap. 15](15-ciclo-de-vida-y-madurez.md).

### Mermaid
- **Simple:** una forma de escribir diagramas con texto.
- **Técnica:** lenguaje para diagramas embebibles en Markdown.
- **Dónde:** todos los diagramas de este manual.

### Métrica
- **Simple:** un número medido en el tiempo (uso de CPU, RAM…).
- **Técnica:** serie temporal con nombre y etiquetas.
- **Dónde:** Prometheus las guarda; Grafana las muestra.

### MicroPython
- **Simple:** una versión chica de Python que corre adentro de la placa.
- **Técnica:** implementación de Python 3 para microcontroladores.
- **Dónde:** las placas de Mijael y Jessi (versión 1.29).

### Mínimo privilegio
- **Simple:** darle a cada persona o programa solo el permiso que necesita, y nada más.
- **Técnica:** principio de seguridad de asignar los permisos mínimos necesarios.
- **Dónde:** Telegraf solo lee; los alumnos sin sudo. Ver [cap. 7](07-seguridad.md).

### MQTT
- **Simple:** un idioma liviano para que aparatos chicos se manden mensajes cortos, tipo grupo de WhatsApp.
- **Técnica:** *Message Queuing Telemetry Transport*: protocolo publicar/suscribir sobre TCP, pensado para dispositivos con pocos recursos.
- **Dónde:** todo el aula habla MQTT con `mqtt-aula`. Ver [cap. 11](11-arquitectura-iot.md).

### MQTT Explorer
- **Simple:** un programa para tu compu que se conecta al broker y te muestra los mensajes de tus topics en vivo.
- **Técnica:** cliente MQTT de escritorio con vista en árbol de topics.
- **En el aula:** la herramienta clave para saber si tu dato llegó al servidor. Ver [Diagnóstico](diagnostico.md#la-herramienta-clave-escuchar-el-broker-desde-tu-compu).

### Namespace
- **Simple:** las "anteojeras" de un contenedor: deciden qué puede ver (sus archivos, sus procesos, su red).
- **Técnica:** mecanismo del kernel Linux que aísla la vista de recursos de un grupo de procesos.
- **Dónde:** base del aislamiento de Docker. Ver [cap. 3](03-docker.md).

### NAT
- **Simple:** el router comparte una IP pública entre muchos dispositivos.
- **Técnica:** *Network Address Translation*.
- **Dónde:** por eso hace falta port-forward para el acceso público.

### nginx
- **Simple:** un programa que le entrega páginas web al navegador.
- **Técnica:** servidor web y proxy inverso de alto rendimiento.
- **Dónde:** el servicio `web` de equipo-03 y equipo-04 (sus páginas propias).

### node-exporter
- **Simple:** mide el estado del server (CPU, RAM, disco).
- **Técnica:** exporter de métricas del host para Prometheus.
- **Dónde:** stack `monitoring`.

### Node-RED
- **Simple:** una herramienta para armar lógica conectando cajitas en vez de escribir código.
- **Técnica:** entorno de programación por flujos (*flow-based*) sobre Node.js.
- **Dónde:** el Node-RED de cada equipo (interruptores, `/api/led`).

### OOM (Out Of Memory)
- **Simple:** cuando se acaba la memoria y el kernel mata procesos.
- **Técnica:** *Out Of Memory killer* del kernel.
- **Dónde:** lo previenen los límites de RAM por equipo.

### Organización (Grafana)
- **Simple:** un Grafana aparte adentro del mismo Grafana, con sus propios tableros y fuentes de datos.
- **Técnica:** unidad de aislamiento de Grafana: usuarios, tableros y fuentes de una organización no existen para las otras.
- **En el aula:** cada equipo tiene la suya (`equipo-NN`); la del profe se llama "Aula — operador". Ver [cap. 13](13-usar-grafana.md).

### Payload (carga)
- **Simple:** el **contenido** de un mensaje: `23.5`, `ON`, `abierto`.
- **Técnica:** datos útiles transportados por un mensaje MQTT, sin los encabezados del protocolo.
- **En el aula:** lo que tu placa manda en cada mensaje: `24.7`, `ON`, `abierto` o un JSON. Telegraf lo convierte en número para Grafana. Ver [regla 2](12-conectar-a-grafana.md#regla-2-el-mensaje-es-un-numero-una-palabra-de-estado-o-un-json).

### Playbook
- **Simple:** la "receta" de Ansible: qué configurar y en qué orden.
- **Técnica:** archivo YAML que orquesta roles/tareas sobre un inventario.
- **Dónde:** `ansible/site.yml`.

### PostgreSQL
- **Simple:** una base de datos.
- **Técnica:** motor de base de datos relacional.
- **Dónde:** servicio compartido multi-tenant (una DB por equipo).

### Prometheus
- **Simple:** el que junta y guarda las métricas.
- **Técnica:** base de datos de series temporales + scraper + PromQL.
- **Dónde:** stack `monitoring`. Ver [cap. 6](06-observabilidad.md).

### PromQL
- **Simple:** el idioma para consultar las métricas de Prometheus.
- **Técnica:** lenguaje de consulta de series temporales.
- **Dónde:** las queries de los dashboards.

### Proxy inverso
- **Simple:** un portero que recibe todo y reparte a los servicios.
- **Técnica:** proxy del lado del servidor (single entry point).
- **En el aula:** **Caddy** es la puerta web: recibe `https://grafana-aula…`, pide el login del aula y te deriva a Grafana. Tu Node-RED **no** pasa por Caddy (no tiene login): se llega por túnel. Ver [Red y accesos](red-y-accesos.md#por-que-grafana-no-necesita-tunel-y-node-red-si).

### Publicar / suscribir
- **Simple:** mandar un mensaje a un "grupo con nombre" / anotarse para recibir lo de ese grupo.
- **Técnica:** patrón *publish/subscribe*: productores y consumidores desacoplados a través de un broker.
- **Dónde:** toda la comunicación de las placas. Ver [cap. 11](11-arquitectura-iot.md).

### Puerto
- **Simple:** el "interno" de un servicio dentro de una IP.
- **Técnica:** número (0-65535) que identifica un endpoint TCP/UDP.
- **En el aula:** tu placa usa el `10000` (el broker, por Funnel); tu Node-RED escucha en un puerto propio del equipo (`1882`, `1884`…), y lo traés a tu compu con el túnel. Ver [guía, paso 1.2](guia-equipo.md#12-el-tunel-ssh-traer-tus-servicios-a-tu-compu).

### Pull request (PR)
- **Simple:** pedir formalmente "sumen mis cambios a la versión principal", para que se revisen antes.
- **Técnica:** solicitud de merge de una rama, con revisión y pruebas automáticas.
- **Dónde:** flujo de cambios del repositorio. Ver [cap. 8](08-pipeline.md).

### Pull y push (métricas)
- **Simple:** **pull:** alguien pasa a buscar los datos (como leer el medidor de luz). **Push:** cada uno avisa cuando pasa algo.
- **Técnica:** modelos de recolección: el colector consulta al origen (pull) o el origen envía al colector (push).
- **Dónde:** Prometheus hace pull; las placas hacen push por MQTT. Ver [cap. 6](06-observabilidad.md).

### QoS (Quality of Service)
- **Simple:** cuánto esfuerzo pone MQTT en que un mensaje llegue (como el doble tilde).
- **Técnica:** nivel de garantía de entrega MQTT: 0 (como mucho una vez), 1 (al menos una vez), 2 (exactamente una vez).
- **Dónde:** Telegraf usa QoS 0; las órdenes de Node-RED, QoS 1.

### RAM (Random Access Memory)
- **Simple:** la "mesada" de la computadora: donde está lo que se usa ahora. Es rápida, chica y se vacía al apagar.
- **Técnica:** memoria principal volátil de acceso aleatorio.
- **Dónde:** el servidor tiene 15 GiB. Ver [cap. 2](02-fundamentos.md).

### Rama (branch)
- **Simple:** una línea de trabajo aparte, para probar cambios sin tocar lo que funciona.
- **Técnica:** puntero a una línea de commits en Git.
- **Dónde:** `feat/aula-iot`, `main`. Ver [cap. 8](08-pipeline.md).

### Relé
- **Simple:** un interruptor que se acciona con una señal eléctrica chiquita y puede prender o cortar un aparato grande.
- **Técnica:** conmutador electromecánico o de estado sólido controlado por una señal de baja potencia.
- **Dónde:** el enchufe de Jorge (simulado con un LED en GPIO 5).

### Retenido (mensaje)
- **Simple:** un mensaje "fijado": el broker guarda el último y se lo da a quien llega después.
- **Técnica:** *retained message*: el broker conserva el último mensaje con la marca *retain* de cada topic y lo entrega a nuevos suscriptores.
- **Dónde:** `equipo-04/enchufe/estado`: al reconectarse, el dashboard ve el último estado.

### Role (Ansible)
- **Simple:** una carpeta con todo lo necesario para configurar una cosa.
- **Técnica:** unidad reutilizable de tareas/plantillas/variables.
- **Dónde:** `ansible/roles/*`.

### root
- **Simple:** el usuario que puede todo.
- **Técnica:** superusuario, UID 0.
- **Dónde:** se evita; los servicios usan cuentas sin privilegios.

### Scrape
- **Simple:** cuando Prometheus pasa a "leer el medidor" de un servicio.
- **Técnica:** consulta periódica HTTP de Prometheus al endpoint `/metrics` de un target.
- **Dónde:** cada 15 s a node-exporter y cAdvisor. Ver [cap. 6](06-observabilidad.md).

### Sensor
- **Simple:** la parte que **mide** algo del mundo físico (los "sentidos").
- **Técnica:** transductor que convierte una magnitud física en una señal eléctrica legible.
- **Dónde:** el reed switch de Jessi. Ver [cap. 11](11-arquitectura-iot.md).

### Serie temporal
- **Simple:** una lista de valores con su hora, como una planilla "hora | temperatura".
- **Técnica:** secuencia de muestras (timestamp, valor) identificada por un nombre y etiquetas.
- **Dónde:** `mqtt_valor{equipo, dispositivo, magnitud}` en VictoriaMetrics.

### Servicio
- **Simple:** un programa que está siempre corriendo, esperando pedidos (el "cocinero de guardia").
- **Técnica:** proceso de larga duración que ofrece una función a otros.
- **En el aula:** el broker, Grafana, tu Node-RED: cada uno es un servicio en su contenedor. Ver [cap. 5](05-servicios.md).

### Shift-left
- **Simple:** buscar los errores lo antes posible, cuando arreglarlos es más barato.
- **Técnica:** práctica de mover las pruebas y controles a etapas tempranas del ciclo de desarrollo.
- **Dónde:** tests en la compu y en el CI antes del servidor. Ver [cap. 8](08-pipeline.md).

### Socket
- **Simple:** un "enchufe" para que dos programas se hablen; en la misma máquina es un archivo especial.
- **Técnica:** extremo de comunicación entre procesos (Unix domain socket o de red).
- **Dónde:** `/run/labctld.sock` entre `labctl` y `labctld`. Ver [cap. 9](09-plataforma-aula.md).

### Split DNS
- **Simple:** el mismo nombre responde una dirección distinta según desde dónde preguntes.
- **Técnica:** resolución DNS condicionada a la red de origen.
- **Dónde:** `*.lucasland.duckdns.org` → IP de Tailscale dentro del tailnet. Ver [cap. 5](05-servicios.md).

### SSH
- **Simple:** entrar a la terminal de otra máquina de forma segura.
- **Técnica:** *Secure Shell*; acceso remoto cifrado, normalmente con claves.
- **Dónde:** administración del server (rol `users_ssh`).

### SSO (Single Sign-On)
- **Simple:** loguearte una sola vez y entrar a todo lo que tenés permitido.
- **Técnica:** inicio de sesión único federado entre aplicaciones.
- **Dónde:** Authelia. Ver [cap. 7](07-seguridad.md).

### Stack
- **Simple:** el conjunto de tecnologías con que está hecho un sistema, una arriba de otra.
- **Técnica:** pila tecnológica: lenguajes, servicios, bases de datos y plataformas que componen una solución.
- **Dónde:** [cap. 15](15-ciclo-de-vida-y-madurez.md#los-stacks-con-que-esta-hecho).

### Staging
- **Simple:** un servidor de ensayo, para probar antes del "estreno" en el servidor real.
- **Técnica:** entorno de preproducción que replica producción.
- **Dónde:** `inventories/staging`. Ver [cap. 8](08-pipeline.md).

### Superficie de ataque
- **Simple:** todo lo que alguien de afuera podría intentar atacar.
- **Técnica:** conjunto de puntos de entrada expuestos de un sistema.
- **Dónde:** se achica sin SSH público (solo Tailscale). Ver [cap. 7](07-seguridad.md).

### systemd
- **Simple:** el que prende y cuida los servicios del sistema.
- **Técnica:** init/manager de servicios (PID 1).
- **Dónde:** timers, slices, `labctld`, `dnsmasq`.

### Tailscale / Tailnet
- **Simple:** tu red privada propia para llegar al server desde cualquier lado.
- **Técnica:** red mesh basada en WireGuard; el *tailnet* es tu red.
- **En el aula:** la red privada del aula: el servidor (`100.110.123.76`) y las compus de alumnos y profe. Las ESP32 **no** están (usan Funnel). Ver [Red y accesos](red-y-accesos.md#2-el-camino-de-las-personas-tailscale-una-red-privada).

### TCP
- **Simple:** enviar datos por red de forma confiable.
- **Técnica:** protocolo de transporte con control de entrega/orden.
- **Dónde:** web, SSH, bases de datos.

### Telegraf
- **Simple:** el "traductor y escribano": lee los mensajes, los pasa a números y los anota con la hora.
- **Técnica:** agente de recolección de métricas (InfluxData) con entradas, procesadores y salidas configurables.
- **Dónde:** `aula-telegraf`: de `mqtt-aula` a VictoriaMetrics.

### Template (Ansible)
- **Simple:** un archivo de configuración con "huecos" que se completan solos.
- **Técnica:** plantilla Jinja2 (`.j2`) renderizada con variables.
- **Dónde:** `telegraf.conf.j2` arma un topic por equipo. Ver [cap. 4](04-ansible-iac.md).

### Test (prueba)
- **Simple:** un programita que comprueba que otro hace lo que debe.
- **Técnica:** verificación automatizada del comportamiento de un componente.
- **Dónde:** `tests/`, corridos por el CI. Ver [cap. 8](08-pipeline.md).

### Topic
- **Simple:** el "nombre del grupo" al que se manda un mensaje MQTT. Se escribe como una ruta: `equipo-04/enchufe/estado`.
- **Técnica:** cadena jerárquica separada por `/` que identifica el canal de un mensaje MQTT; admite comodines `+` y `#` al suscribirse.
- **En el aula:** la "dirección" de cada mensaje, con el contrato `equipo-NN/dispositivo/magnitud` (ej. `equipo-04/enchufe/estado`). El broker solo te deja usar los que empiezan con tu equipo. Ver [las 3 reglas](12-conectar-a-grafana.md#las-3-reglas).

### Túnel
- **Simple:** un pasillo privado y cifrado entre tu compu y el servidor: lo que entra por una punta sale por la otra.
- **Técnica:** canal que encapsula tráfico dentro de otra conexión (p. ej. reenvío de puertos por SSH).
- **En el aula:** `ssh -L 1880:localhost:1884 …` trae tu Node-RED a `localhost:1880`. Ver [Red y accesos](red-y-accesos.md#4-el-tunel-llegar-a-lo-que-no-esta-publicado).

### UFW
- **Simple:** el firewall (decide qué puertos se abren).
- **Técnica:** *Uncomplicated Firewall*, front-end de iptables.
- **Dónde:** rol `firewall` (default deny).

### Vault (Ansible Vault)
- **Simple:** una caja fuerte para las contraseñas dentro del repo.
- **Técnica:** archivo cifrado que Ansible descifra al aplicar.
- **Dónde:** `inventories/*/group_vars/all/vault.yml`.

### VictoriaMetrics
- **Simple:** la base de datos que guarda el historial de los sensores (15 días).
- **Técnica:** base de datos de series temporales compatible con Prometheus.
- **Dónde:** `aula-victoriametrics`, consultada por el Grafana del aula.

### VPN (Virtual Private Network)
- **Simple:** una red privada que viaja por adentro de internet, cifrada: como estar en la misma sala aunque estés lejos.
- **Técnica:** red privada virtual: enlaza dispositivos remotos en una red lógica cifrada.
- **En el aula:** Tailscale es la VPN del aula. Ver [Red y accesos](red-y-accesos.md#2-el-camino-de-las-personas-tailscale-una-red-privada).

### WebSocket
- **Simple:** una conexión que queda **abierta** para que los datos lleguen solos, como una llamada en vez de cartas.
- **Técnica:** protocolo de comunicación bidireccional y persistente sobre una conexión HTTP.
- **Dónde:** `/ws/led`: la página de Mijael ve el LED en vivo.

### WireGuard
- **Simple:** el sistema de túneles cifrados que usa Tailscale por adentro.
- **Técnica:** protocolo VPN moderno basado en criptografía de curva elíptica.
- **Dónde:** debajo de Tailscale.

### YAML
- **Simple:** un formato de texto para configuraciones, sensible a la sangría.
- **Técnica:** lenguaje de serialización legible por humanos.
- **Dónde:** compose, playbooks, inventarios, dashboards.

---

> ¿Falta un término? Está anotado en [Mejoras futuras](mejoras-futuras.md) para
> agregarlo. Este glosario crece con el manual.
