# Replicar y escalar el homelab

El repo está pensado para levantar **el mismo servidor endurecido en cualquier
máquina**, y para manejar **varios sitios** (una casa, un colegio, otro colegio)
desde el mismo código. Este documento explica el modelo y el paso a paso.

## El modelo en una frase

**Un inventario = un sitio.** El código (roles, `site.yml`, línea base) es común
a todos; lo que cambia de un sitio a otro —hostname, red, dominio, secretos—
vive en `inventories/<sitio>/`. Replicar es crear un inventario nuevo; el código
no se toca.

```
ansible/
├── site.yml                     # el QUÉ se instala — igual en todos los sitios
├── roles/                       # el CÓMO — igual en todos los sitios
├── group_vars/all/main.yml      # línea base: lo idéntico en TODOS los sitios
└── inventories/
    ├── _template/               # plantilla para clonar un sitio nuevo
    ├── production/              # tu sitio actual (homelab-01)
    ├── staging/                 # un sitio de pruebas descartable
    └── <sitio-nuevo>/           # se crea copiando _template
```

Qué va en cada capa de variables (de menor a mayor precedencia):

| Capa | Qué contiene | Ejemplo |
|---|---|---|
| `roles/<rol>/defaults` | perillas del rol, con default sano | `ufw_default_incoming: deny` |
| `group_vars/all` (raíz) | lo idéntico en **todos** los sitios | `admin_user: ansible` |
| `inventories/<sitio>/group_vars/all` | identidad del **sitio** | `caddy_base_domain`, `lan_cidr` |
| `inventories/<sitio>/host_vars/<host>` | lo propio de **un servidor** del sitio | `server_hostname` |

## Replicar: un sitio nuevo

```bash
make new-site NAME=colegio-norte
```

Eso copia la plantilla a `inventories/colegio-norte/`. Después:

1. **Editar la identidad** — `inventories/colegio-norte/hosts.ini` y
   `group_vars/all/main.yml`. Están marcados con `REPLACE_`: hostname, `lan_cidr`
   (¡el real, verificado con `ip -4 addr`!), tu clave SSH, dominio y email.
2. **Cargar los secretos** — `make vault-create ENV=colegio-norte`, y editar con
   `make vault-edit ENV=colegio-norte` (token de DuckDNS, contraseñas, etc.).
3. **Revisar sin aplicar** — `make dry-run ENV=colegio-norte`.
4. **Aplicar** — `make apply ENV=colegio-norte`.

El playbook es idempotente y ya lo cubren los tests de CI (syntax-check y lint
corren contra `production` y `staging`), así que un sitio bien completado
levanta igual que el original.

## Escalar: varios servidores en un mismo sitio

Un inventario puede tener más de un servidor. Lo común al sitio (dominio, red,
vault) queda en `group_vars/all`; lo propio de cada máquina va en
`host_vars/<hostname>.yml`:

```ini
# inventories/colegio-norte/hosts.ini
[homeserver]
nodo-a ansible_host=100.x.x.x
nodo-b ansible_host=100.x.x.y
```

```yaml
# inventories/colegio-norte/host_vars/nodo-a.yml
server_hostname: "nodo-a"
```

`site.yml` corre contra el grupo `homeserver`, así que aplica a todos los
servidores del sitio de una vez. Para ir de a uno mientras probás, usá
`--limit`:

```bash
cd ansible && ansible-playbook site.yml -i inventories/colegio-norte --limit nodo-a
```

Para que un despliegue grande no se caiga entero si un paso falla en una
máquina, se puede agregar `serial: 1` en `site.yml` (aplica host por host).

## Qué NO se replica

- **Los secretos.** Cada sitio tiene su propio `vault.yml` cifrado; nunca se
  copian entre sitios. La plantilla trae `vault.yml.example` con placeholders.
- **El estado en el servidor.** Las claves del pañol (`/etc/panol/secrets`), los
  volúmenes de Docker y los backups viven en cada máquina, no en el repo. Se
  regeneran solos en la primera converge.

## Checklist de un sitio sano

```bash
make dry-run  ENV=<sitio>     # ni un cambio inesperado
make apply    ENV=<sitio>
make verify   ENV=<sitio>     # aserciones de postura
make idempotence ENV=<sitio>  # una segunda corrida no cambia nada
```
