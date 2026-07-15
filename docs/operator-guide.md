# Guía del operador

Cómo administrar la plataforma de laboratorio. Todo es Ansible; los cambios se
declaran y se re-aplican.

## Aplicar cambios del laboratorio

```bash
cd ~/homelab/ansible
~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production --tags classroom -K
```

> Como corrés como `homelab` (sudo con password), va `-K`. `ansible-playbook`
> está en `~/homelab/.venv/bin`, no en el PATH.

**Si agregaste una colección nueva** a `requirements.yml`, instalala primero:
```bash
~/homelab/.venv/bin/ansible-galaxy collection install -r requirements.yml
```

## Alta / baja de alumnos y equipos

Editá el registro en `inventories/production/group_vars/all/classroom.yml`:

```yaml
classroom_teams:
  - name: equipo-01
    members: [jessi]
  - name: equipo-06          # equipo nuevo
    members: [nombre1, nombre2]
```

Re-aplicá `--tags classroom`. Ansible crea el usuario, la pertenencia al grupo,
el directorio (2770 + loopback de cuota), el slice systemd, y la base + usuario
de Postgres del equipo, con su `.shared-services.env`.

**Baja:** quitá al integrante de la lista (o el equipo entero) y re-aplicá. Los
datos del equipo quedan en su loopback (`/var/lib/classroom/loopbacks/`) por si
hay que archivarlos.

## Publicar un proyecto de alumno

Los alumnos **nunca** exponen puertos. Para hacer visible un proyecto, editá
`student_exposures` en el mismo `classroom.yml`:

```yaml
student_exposures:
  - team: equipo-01
    hostname: equipo01.lucasland.duckdns.org
    service: web           # nombre del servicio en el compose del equipo
    port: 8080             # puerto del contenedor
    enabled: true          # nada es público hasta poner esto en true
```

Re-aplicá `--tags publish`. Se renderiza un vhost de Caddy y se recarga. Caddy
llega al contenedor porque `labctld` lo conecta a la red del equipo en el `up`
(el proyecto tiene que estar levantado).

## Servicios compartidos

- Requieren `vault_postgres_superuser_password` en el vault
  (`ansible-vault edit inventories/production/group_vars/all/vault.yml`).
- Los passwords por equipo se generan una vez y viven en
  `/etc/classroom/secrets/*.pgpass` (root). Cada equipo recibe su
  `.shared-services.env`.
- Contrato para alumnos: [servicios-compartidos.md](servicios-compartidos.md).

## Observabilidad

Grafana (detrás de Caddy) → carpeta *Homelab*: **Classroom Overview**,
**Team Detail**, **Capacity Planning**. Mirá **Capacity Planning** para decidir
si entra otro equipo sin quedarte sin RAM.

## Verificación

```bash
cd ~/homelab
~/homelab/.venv/bin/py.test -v --hosts=local:// tests/test_classroom.py tests/test_labctl.py tests/test_shared_services.py
```

## Auditoría y troubleshooting

- Auditoría de despliegues: `sudo tail -f /var/log/labctl/audit.log`.
- Estado del broker: `systemctl status labctld`.
- Un equipo consume de más: `systemctl status classroom-equipoNN.slice` (verás
  RAM/tasks vs. el tope).
- `labctl` no responde: reiniciá `sudo systemctl restart labctld`.

## Seguridad (recordatorio)

Caddy es el único ingress público; Prometheus/cAdvisor/node-exporter privados;
Grafana detrás de Caddy. Los alumnos no tienen Docker/sudo/socket. Cada
despliegue se valida por política y se audita.
