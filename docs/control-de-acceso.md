# Control de acceso (SSO con Authelia)

El acceso web está en **capas**, con un único login (Authelia) y **grupos**.

## Quién ve qué

| Grupo | Ve | Cómo |
|---|---|---|
| **operators** (vos) | Todo: dashboard, Grafana de operación (infra + auditoría del pañol), Grafana del aula, Prometheus, cAdvisor, panel del pañol | login SSO |
| **students** (alumnos) | El dashboard y el **Grafana del aula** (cada equipo edita su carpeta) + su app publicada | login SSO |
| **family / público** | Solo las apps de alumnos que vos publiques | sin login (públicas) |

- **Authelia** es el portal de login (`auth.tudominio`). Protege con `forward_auth`
  en Caddy cada subdominio según su regla (en
  `ansible/roles/authelia/templates/configuration.yml.j2`).
- **Solo `operators`:** Prometheus, cAdvisor, el panel del pañol (actúa sobre una
  puerta real) y el **Grafana de operación** (`grafana.`), que muestra la auditoría
  de quién entró al pañol.
- **`operators` + `students`:** el dashboard raíz y el **Grafana del aula**
  (`grafana-aula.`). Ese Grafana crea a cada alumno con el usuario que llega de
  Authelia y lo pone en su equipo: ve y edita solo su carpeta (**en puesta en
  marcha**: todavía no está activo en el servidor). Detalle en
  [aula-iot.md](aula-iot.md).
- Las **apps publicadas** de alumnos quedan públicas (sin login).

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

1. **Router → forward TCP 443** (y 80) a la IP LAN del server (`hostname -I`; la
   red cambió varias veces, hoy `192.168.8.x`). **Hoy no está configurado:** todo
   se usa por Tailscale. Así los alumnos/familia
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
