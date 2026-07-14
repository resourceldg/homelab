# Runbook

Operational procedures for day-2 tasks.

## First-time provisioning

1. `make deps` — install collections and test tooling.
2. Edit `ansible/inventories/production/group_vars/all/main.yml`: SSH keys,
   `lan_cidr`, `caddy_base_domain`, `caddy_acme_email`, `duckdns_domains`.
   Role-specific knobs (`borg_repo`, retention, timers…) live in each role's
   `defaults/main.yml`; override them here only when they must differ.
   Use `ENV=staging` on any `make` target to act on the staging inventory.
3. `make vault-create`, then `make vault-edit` to fill real tokens.
4. Store the vault password in `~/.vault_pass` (gitignored, `chmod 600`).
5. `make dry-run` → review the diff.
6. `make apply`.
7. `sudo tailscale up --ssh --accept-routes` (one-time browser auth).
8. Mount the backup drive at `borg_repo`'s parent, then `make backups`.
9. `make verify && make test`.

## Add a new educational project

1. Copy `compose/apps/` to `compose/apps-<name>/`, rename the service.
2. Add a site block to `compose/proxy/Caddyfile`:
   ```
   <name>.{$CADDY_BASE_DOMAIN} {
       reverse_proxy <service>:<port>
   }
   ```
3. Attach the service to the external `edge` network (no published ports).
4. `make monitoring` (re-syncs and restarts the proxy + stacks).
5. Reachable at `https://<name>.<your-domain>`.

## Rotate a secret

```bash
make vault-edit          # change the value
make apply               # re-renders env files and restarts affected services
```

## Backups

- Manual run: `sudo borgmatic --verbosity 1`
- List archives: `sudo borgmatic list`
- Restore a path:
  ```bash
  sudo borgmatic extract --archive latest --path etc/ssh/sshd_config
  ```
- Check repo integrity: `sudo borgmatic check`
- Timer status: `systemctl status borgmatic.timer`

## Audit review

- Lynis score: `journalctl -t lynis` or `/var/log/lynis/lynis-report.dat`
  (`grep hardening_index`).
- AIDE changes: `journalctl -t aide`; investigate any "INTEGRITY CHANGES".
- After an intentional change, refresh the AIDE baseline:
  ```bash
  sudo aideinit -y -f && sudo systemctl restart aide-check.timer
  ```

## Firewall / connectivity troubleshooting

- `sudo ufw status verbose` — current rules.
- Locked out of SSH? Use the physical console or Tailscale SSH
  (`tailscale ssh ansible@homelab-01`).
- A container port is unexpectedly public → confirm `ufw-docker` installed and
  the service publishes on `127.0.0.1` only.

## Updates

- Host security patches apply automatically (`unattended-upgrades`), rebooting at
  `autoupdate_reboot_time` if needed. Review with `journalctl -u unattended-upgrades`.
- Container images: `cd /opt/homelab/stacks/<stack> && docker compose pull && docker compose up -d`
  (kept manual on purpose so a bad image never auto-breaks a running class demo).

## Disaster recovery outline

1. Re-install Ubuntu LTS, create the sudo user, add your SSH key.
2. Clone the repo, restore `.vault_pass` and the vault from your password manager.
3. `make apply`.
4. Mount the backup drive, `borgmatic extract` the Docker volumes and `/opt/homelab`.
5. `make monitoring` to bring services back.
