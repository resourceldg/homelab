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
6. **SSH — phase 1 (safe, no lockout):** create the account + install keys
   without applying the restrictive `sshd_config` yet:
   ```
   ansible-playbook site.yml --tags ssh --skip-tags ssh-lockdown
   ```
   Then confirm key access from another terminal: `ssh <admin_user>@<host>`.
7. `make apply` — full converge. The **SSH lockdown** (`PasswordAuthentication
   no`, `AllowUsers`, sshd restart) now applies. A safety gate aborts the play
   if `admin_ssh_authorized_keys` is empty or still a `REPLACE_ME` placeholder,
   so you cannot lock yourself out by forgetting the key. Set
   `ssh_lockdown_enabled: false` to defer the hardening entirely.
8. `sudo tailscale up --ssh --accept-routes` (one-time browser auth).
9. Mount the backup drive at `borg_repo`'s parent, then `make backups`.
10. `make verify && make test`.

### User accounts

`extra_users` (in the environment's group_vars) defines the human accounts:

- **operator** — your account: in the `sudo` group (sudo asks for a password)
  and SSH-allowed. Set a login password once so `sudo` works:
  `sudo passwd operator`. Fill its real key before `make apply` (the SSH lockdown
  gate refuses to run while an SSH-enabled user still has a `REPLACE_ME` key).
- **familia** — daily-use account: no sudo, `ssh: false`, so it can log in at the
  desktop but never over SSH (not added to `AllowUsers`).
- **ansible** (`admin_user`) — automation only: passwordless sudo, key-based SSH.

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

## Replicate the whole thing to another machine

```bash
make new-site NAME=<sitio>   # clone the inventory template, then fill the REPLACE_ values
```

Full flow (one inventory = one site, several servers per site with host_vars) in
[replicar-y-escalar.md](replicar-y-escalar.md).

## Pañol IoT (access control)

The `panol` role owns the broker + audit DB + Node-RED; the brain (api, bridge,
scheduler) deploys from the `panol-iot` repo. Everything —credentials, rotation,
firewall, the test-data reset, the end-to-end walkthrough— lives in
[panol-iot.md](panol-iot.md). Quick ones:

```bash
make panol                                      # redeploy the plane
sudo cat /etc/panol/secrets/nodos.txt           # node credentials for flashing
systemctl status panol-reset-prueba.timer       # test-mode reset (temporary)
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
