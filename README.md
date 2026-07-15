# Homelab — Secure Ubuntu Home & Dev Server (IaC)

[![CI](https://github.com/resourceldg/homelab/actions/workflows/ci.yml/badge.svg)](https://github.com/resourceldg/homelab/actions/workflows/ci.yml)

Reproducible, modular infrastructure-as-code for an **Ubuntu Desktop LTS** box that
doubles as a **development server** and **hosting platform for educational projects**.

Built by a two-plane design:

- **Host plane → Ansible** — OS config, CIS hardening, SSH, firewall, Fail2ban,
  AppArmor, auto-updates, Lynis/AIDE auditing, Tailscale, DuckDNS, Docker.
- **Service plane → Docker Compose** — Caddy reverse proxy (auto-HTTPS),
  Prometheus + Grafana monitoring, and your projects.

| Requirement | Implementation |
|---|---|
| IaC | Ansible roles + Docker Compose |
| Hardening (CIS) | Ubuntu Security Guide `usg` (CIS L1 Server) + custom controls |
| SSH | keys only, no root, LAN/Tailscale only |
| Remote access | Tailscale (SSH never exposed to WAN) |
| Firewall | UFW + `ufw-docker` (closes the Docker bypass) |
| Brute-force defense | Fail2ban (systemd backend, UFW ban action) |
| MAC | AppArmor, all profiles enforcing |
| Auto-updates | `unattended-upgrades` (security only) |
| Auditing | Lynis (weekly) + AIDE (daily FIM) |
| Dynamic DNS | DuckDNS (systemd timer) |
| Monitoring | Prometheus + Grafana (auto-provisioned dashboard) + node-exporter + cAdvisor |
| Backups | Borg via borgmatic (encrypted, local repo, retention) |
| Tests / CI | ansible-lint, idempotence, testinfra, verify playbook, Molecule matrix (Ubuntu 22.04 + 24.04) via GitHub Actions |

A **multi-user Docker Compose teaching lab** runs on top of this server — 5
student teams deploy isolated stacks via `labctl`, with no Docker/sudo/socket
access. See [docs/classroom-architecture.md](docs/classroom-architecture.md) and
the guides ([student](docs/student-guide.md), [operator](docs/operator-guide.md),
[labctl](docs/labctl.md), [policy](docs/docker-compose-policy.md),
[resources](docs/resource-model.md), [shared services](docs/servicios-compartidos.md)).

See [docs/architecture.md](docs/architecture.md) for the diagrams and the full
rationale behind each decision, and
**[docs/deployment-guide.md](docs/deployment-guide.md)** for the exhaustive,
pedagogical deploy walkthrough — the access model, every gotcha, and break-glass
recovery. Read that one before deploying (or re-deploying after a while).

## Repository layout

```
homelab/
├── ansible/
│   ├── site.yml                 # orchestrator (tagged roles)
│   ├── ansible.cfg              # defaults to inventories/production
│   ├── group_vars/all/main.yml  # cross-role constants (same in every env)
│   ├── inventories/
│   │   ├── production/
│   │   │   ├── hosts.ini
│   │   │   └── group_vars/all/  # prod identity/network/domain + vault
│   │   └── staging/
│   │       ├── hosts.ini
│   │       └── group_vars/all/  # staging overrides + vault
│   └── roles/                   # each role owns its defaults/main.yml
│       ├── bootstrap/ users_ssh/ tailscale/ ddns/
│       ├── firewall/ fail2ban/ apparmor/ hardening/ auto_updates/ audit/
│       └── docker/ monitoring/ backups/
├── compose/
│   ├── proxy/                   # Caddy (custom build w/ DuckDNS DNS-01)
│   ├── dashboard/               # Homepage launchpad (links every service)
│   ├── monitoring/              # Prometheus + Grafana + exporters
│   └── apps/                    # example educational project
├── tests/                       # testinfra + verify playbook
├── docs/                        # architecture, runbook, diagrams
└── Makefile                     # operator interface
```

## Quickstart

Prerequisites: fresh Ubuntu **24.04 LTS** (primary target; 22.04 and a future
26.04 also supported), a sudo user, a DuckDNS token, and your SSH public key.

> Ubuntu Pro is **optional** and off by default (`usg_enabled: false`). It only
> unlocks the `usg` CIS tooling; all the complementary hardening (sysctl,
> pwquality, core dumps, AppArmor, Fail2ban…) applies without it. Enable it only
> if you have a Pro token.

```bash
# 0. Clone onto the server (or a control node with SSH access).
git clone <this-repo> homelab && cd homelab

# 1. Install dependencies.
make deps

# 2. Fill in your settings for the target environment (production by default).
$EDITOR ansible/inventories/production/group_vars/all/main.yml  # keys, domain, LAN CIDR…
make vault-create                            # create + encrypt secrets for ENV
echo "your-vault-password" > ~/.vault_pass && chmod 600 ~/.vault_pass

# 3. Preview everything (no changes made).
make dry-run                                 # add ENV=staging to target staging

# 4. Converge.
make apply                                   # or: make apply ENV=staging

# 5. Authenticate Tailscale once (interactive, one time only).
sudo tailscale up --ssh --accept-routes

# 6. Verify.
make verify        # in-Ansible posture assertions
make test          # testinfra smoke tests
make idempotence   # proves a second run changes nothing
```

Grafana is then at `https://grafana.<your-domain>`, your demo app at
`https://demo.<your-domain>`.

## Safety notes

- **Run `make dry-run` first.** Hardening changes SSH and the firewall; make sure
  you have Tailscale or console access before locking down remote SSH.
- **`.vault_pass` and `vault.yml` are gitignored.** Never commit decrypted secrets.
- **Router port-forwarding**: only 80/443 → server are needed, and only if you
  want the projects reachable from the public internet. Everything else stays
  private over Tailscale.
- Losing `vault_borg_passphrase` means losing the backups — store it in a
  password manager.
- **Fresh 26.04**: if the Docker or Tailscale apt repo 404s because the vendor
  hasn't published the new codename yet, set `apt_repo_release: "noble"` in
  `main.yml` to pin to the previous LTS until they catch up.

## Common operations

| Task | Command |
|---|---|
| Apply only security controls | `make harden` |
| Re-deploy containers | `make monitoring` |
| Edit secrets | `make vault-edit` |
| Run a backup now | `make backups` |
| Lint | `make lint` |

More in [docs/runbook.md](docs/runbook.md).
