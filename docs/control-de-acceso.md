# Control de acceso (SSO con Authelia)

El acceso web está en **capas**, con un único login (Authelia) y **grupos**.

## Quién ve qué

| Grupo | Ve | Cómo |
|---|---|---|
| **operators** (vos) | Todo: dashboard, Grafana (Admin), Prometheus, cAdvisor | login SSO; en Grafana entrás como Admin |
| **students** (alumnos) | El dashboard y Grafana (solo lectura) + su app publicada | login SSO; Grafana los ve como Viewer |
| **family / público** | Solo las apps de alumnos que vos publiques | sin login (públicas) |

- **Authelia** es el portal de login (`auth.tudominio`). Protege con `forward_auth`
  en Caddy: `grafana`, `prometheus`, `cadvisor` y el dashboard raíz.
- **Prometheus/cAdvisor** → solo `operators`. **Grafana/dashboard** → `operators`
  + `students`. Las **apps publicadas** de alumnos quedan públicas (sin login).
- **Grafana** confía en Authelia: cualquiera que pase el login lo ve como
  **Viewer** (sin cuenta de Grafana); vos elevás a **Admin** iniciando sesión con
  el usuario admin de Grafana.

## Alta de usuarios SSO

1. Editá `inventories/production/group_vars/all/classroom.yml` → `sso_users`:
   ```yaml
   - { username: nuevo, displayname: "Nombre", groups: [students] }
   ```
   Grupos válidos: `operators`, `students`, `family`.
2. Poné su contraseña en el vault:
   ```bash
   ansible-vault edit inventories/production/group_vars/all/vault.yml
   #   vault_sso_passwords:
   #     nuevo: "su-contraseña"
   ```
3. Aplicá: `--tags auth -K`.

## Los 3 pasos manuales (una vez)

Para que todo funcione de punta a punta:

1. **Router → forward TCP 443** (y 80) a `192.168.100.48`. Así los alumnos/familia
   llegan desde Internet. (DuckDNS ya mantiene tu IP pública al día.)
2. **Vault → secretos de Authelia.** Generá 3 secretos largos y las contraseñas:
   ```bash
   for s in jwt session storage; do echo "$s: $(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 64)"; done
   ansible-vault edit inventories/production/group_vars/all/vault.yml
   #   vault_authelia_jwt_secret / _session_secret / _storage_key
   #   vault_sso_passwords: { operator: "...", jessi: "...", ... }
   ```
3. **Tailscale → Split DNS (solo para vos).** Para resolver el dominio a la IP del
   tailnet en todos tus dispositivos sin `/etc/hosts`: en
   https://login.tailscale.com/admin/dns activá **MagicDNS**, y en **Nameservers →
   Custom** agregá `100.110.123.76` con **"Restrict to domain"** = tu dominio. El
   rol `dns` ya corre un dnsmasq en el server que responde ese dominio con la IP
   del tailnet.

## Aplicar

```bash
# instalar la colección postgres si no está (una vez):
~/homelab/.venv/bin/ansible-galaxy collection install -r requirements.yml
# aplicar SSO + DNS + proxy:
cd ~/homelab/ansible
~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production --tags "auth,dns,services" -K
```

## Cómo entran

- **Vos y los alumnos:** entran a cualquier servicio protegido y Authelia les pide
  usuario/contraseña una vez (`https://auth.tudominio`). Después navegan libre
  según su grupo.
- **Familia/público:** abren directo la URL de una app publicada (sin login).

## Notas de seguridad

- Prometheus/cAdvisor no tienen auth propia: quedan **solo para operators** vía
  Authelia, seguros aun con el 443 abierto.
- Las contraseñas de Authelia se hashean (sha512crypt) al renderizar; el vault
  guarda las de texto plano solo para poder regenerarlas.
- Si perdés acceso al portal: entrás por Tailscale SSH como `ansible` y revisás
  `docker logs authelia`.
