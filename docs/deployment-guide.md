# Deployment Guide — Homelab Server

> **Read this first if you're coming back after a while.** This guide captures
> the *why* behind every decision and the non-obvious gotchas discovered while
> actually deploying this server — the things that are easy to forget in six
> months. It is meant to be read top-to-bottom the first time, then used as a
> reference.

**Audience:** the operator (you) and anyone learning infrastructure-as-code from
this repo as a pedagogical example.

---

## Table of contents

1. [What this server is](#1-what-this-server-is)
2. [The access model (read this before touching SSH)](#2-the-access-model)
3. [Repository layout & variable layering](#3-repository-layout--variable-layering)
4. [Where everything lives on the box](#4-where-everything-lives-on-the-box)
5. [Deploying from scratch — the safe procedure](#5-deploying-from-scratch)
6. [The SSH anti-lockout design](#6-the-ssh-anti-lockout-design)
7. [Gotchas & lessons (the "future you" section)](#7-gotchas--lessons)
8. [Day-2 operations](#8-day-2-operations)
9. [Backups (deferred setup)](#9-backups)
10. [Verification & health checks](#10-verification--health-checks)
11. [Troubleshooting](#11-troubleshooting)
12. [Break-glass recovery](#12-break-glass-recovery)

---

## 1. What this server is

A single Ubuntu **24.04 LTS** box (hostname `homelab-01`) that is both a **home
server** and a **hosting platform for educational projects**. It is managed
entirely as code, in two planes:

- **Host plane → Ansible.** OS config, users/SSH, firewall, Fail2ban, AppArmor,
  kernel hardening, unattended-upgrades, Lynis/AIDE auditing, Tailscale, DuckDNS,
  Docker install.
- **Service plane → Docker Compose.** Caddy reverse proxy (auto-HTTPS via the
  DuckDNS DNS-01 challenge), Prometheus + Grafana monitoring with node-exporter
  and cAdvisor, and your project containers.

**Not using Ubuntu Pro.** The CIS/USG tooling stays off (`usg_enabled: false`);
all the *complementary* hardening (sysctl, pwquality, AppArmor, Fail2ban, module
blacklists, login hardening) still applies without a Pro token. Target is 24.04
today, with an eventual move to 26.04 (the `apt_repo_release` escape hatch exists
for when vendor repos lag on a fresh release).

---

## 2. The access model

**This is the single most important section. Internalise it before running any
SSH-related task, because it's what keeps you from locking yourself out.**

There are **three ways in**, and they are independent:

| Path | User | Auth mechanism | Affected by OpenSSH hardening? |
|---|---|---|---|
| **Local console** (physical / desktop) | `homelab` | desktop login | **No** — always works |
| **Tailscale SSH** | `ansible` (from your notebook) | Tailscale identity/ACL | **No** — bypasses system `sshd` |
| **Direct OpenSSH** (LAN or WAN) | `ansible`, `homelab` | SSH public key | **Yes** |

### Why this matters

The Ansible SSH hardening (`PasswordAuthentication no`, `AllowUsers`, strong
crypto) only governs the **system OpenSSH daemon** — i.e. the *Direct OpenSSH*
row. **Tailscale SSH is served by `tailscaled`, not `sshd`**, so it authenticates
over the tailnet regardless of `/etc/ssh/sshd_config`. That's why you can harden
OpenSSH aggressively without losing your day-to-day Tailscale access — and why,
in the worst case, you still have the console and Tailscale SSH as safety nets.

### The accounts

- **`ansible`** — the automation account. **Passwordless sudo** (a
  `/etc/sudoers.d` NOPASSWD drop-in) because Ansible needs unattended privilege
  escalation. This is the identity you use for Tailscale SSH from the notebook.
- **`homelab`** — your personal / desktop account. **sudo WITH a password** (in
  the `sudo` group, no NOPASSWD). This is who you log in as at the console, and
  who owns the git checkout. In `AllowUsers` so it can also SSH directly with a
  key.
- **`familia`** — (optional, not created yet) a daily-use account for family:
  no sudo, `ssh: false`, so it can log in at the desktop but never over SSH.

### The keys

Your **notebook** (`zen-precision-3561`, user `zen`) holds an ed25519 **private**
key. Its **public** key is committed in the production group_vars and installed
by Ansible into `authorized_keys` for both `ansible` and `homelab`. Public keys
are safe to commit; the private key never leaves the notebook.

> Tailscale SSH does **not** use `authorized_keys` at all — the traditional key
> is your **fallback** for direct OpenSSH (e.g. if Tailscale is ever down).

---

## 3. Repository layout & variable layering

Configuration resolves in **three precedence layers** (lowest → highest):

```
roles/<role>/defaults/main.yml         # 1. role-owned tunables (sane defaults)
group_vars/all/main.yml                # 2. cross-role constants, same everywhere
inventories/<env>/group_vars/all/      # 3. per-environment identity/net/secrets
```

- A role ships working defaults, so it's self-contained and reusable.
- `group_vars/all` holds only what several roles share and never changes between
  environments (`admin_user`, `ssh_port`, `apt_repo_release`, `stacks_root`).
- `inventories/production/` and `inventories/staging/` each carry their own
  `hosts.ini`, a `group_vars/all/main.yml` (identity, network, domain), and an
  encrypted `vault.yml` (secrets). Select one with `-i inventories/<env>` or
  `make <target> ENV=staging`.

```
ansible/
├── site.yml                     # orchestrator (roles tagged by plane)
├── ansible.cfg                  # defaults to inventories/production
├── group_vars/all/main.yml      # shared constants
├── inventories/
│   ├── production/{hosts.ini, group_vars/all/{main,vault}.yml}
│   └── staging/{hosts.ini, group_vars/all/{main,vault}.yml}
└── roles/                       # each role owns defaults/ tasks/ meta/ [templates/ molecule/]
```

---

## 4. Where everything lives on the box

**These paths bit us during deployment — write them into memory.**

| Thing | Location | Note |
|---|---|---|
| Git checkout | `/home/homelab/homelab` | inside the `homelab` **user's home**, not `/home/homelab` |
| Python venv w/ Ansible | `/home/homelab/homelab/.venv` | created by `make deps` |
| `ansible-playbook` binary | `~/homelab/.venv/bin/ansible-playbook` | **not on `$PATH`** — call it by full path or activate the venv |
| Vault password file | `~/.vault_pass` (i.e. `/home/homelab/.vault_pass`) | `ansible.cfg` points at `~/.vault_pass`; per-user |
| Encrypted vault | `ansible/inventories/production/group_vars/all/vault.yml` | moved here from the old `ansible/group_vars/all/vault.yml` |
| Compose stacks (deployed) | `/opt/homelab/stacks` | `stacks_root` |
| Borg backup repo | `/mnt/backup/borg-repo` | needs a **mounted** drive (see §9) |

**Run Ansible as the `homelab` user**, from the checkout, using the venv binary.
Because `homelab` has **password sudo**, you must pass `-K` (`--ask-become-pass`)
so Ansible can escalate — `ansible.cfg` sets `become_ask_pass = False`, so
without `-K` a run fails with "sudo: a password is required". (The `ansible`
account has passwordless sudo, but the repo lives in `homelab`'s home, so
`homelab` + `-K` is the practical way.)

---

## 5. Deploying from scratch

The golden rule: **never harden SSH before you've proven you can still get in.**
Keep a **console session open** the whole time as the ultimate fallback.

### 5.0 Prerequisites
- Ubuntu 24.04, the `homelab` user with sudo, Tailscale installed & authed.
- Your notebook's ed25519 **public** key (generate with `ssh-keygen -t ed25519`
  if you don't have one; the private key stays on the notebook).

### 5.1 Get the code up to date
```bash
cd ~/homelab            # /home/homelab/homelab
git status              # expect "clean" (the untracked vault.yml is fine — see 5.2)
git pull
```

### 5.2 Migrate the vault (one-time, old layout → per-env)
The encrypted vault used to live at `ansible/group_vars/all/vault.yml`; the new
layout expects it per-environment. It's gitignored at the new path, so move it:
```bash
mv ansible/group_vars/all/vault.yml \
   ansible/inventories/production/group_vars/all/vault.yml
```
> After `git pull` the old-path vault shows as **untracked** (the new `.gitignore`
> only ignores the per-env path). Don't `git add` it — just move it.

### 5.3 Set the REAL values in production group_vars
Edit `ansible/inventories/production/group_vars/all/main.yml`:
- `lan_cidr` — **your actual LAN subnet** (find it with `hostname -I`). Getting
  this wrong silently firewalls you off your own LAN (see §7).
- `admin_ssh_authorized_keys` — the notebook's real public key (for `ansible`).
- `extra_users` — your account (`homelab`, `ssh: true`, in `sudo`, real key).
- `server_timezone` / `server_locale` — e.g. `America/Argentina/Buenos_Aires`,
  `es_AR.UTF-8`.

No `REPLACE_ME` may remain in any `ssh: true` account, or the safety gate aborts.

### 5.4 Ensure tooling is present
```bash
make deps               # creates .venv, installs ansible-core + collections + tools
```

### 5.5 SSH — phase 1: create users + keys, WITHOUT locking down
```bash
cd ~/homelab/ansible
~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production \
    --tags ssh --skip-tags ssh-lockdown -K
```
This creates/ensures the accounts and installs keys but leaves `sshd` untouched.

### 5.6 Fix the firewall so your real LAN is allowed
If the box was previously provisioned with a wrong `lan_cidr`, UFW is still
blocking your LAN. Apply the firewall role to add the correct rule **before**
testing direct SSH:
```bash
~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production \
    --tags firewall -K
```

### 5.7 PROVE access before hardening (do not skip)
From the **notebook**, over the LAN (hits OpenSSH, not Tailscale SSH):
```bash
ssh homelab@<server-LAN-ip>      # e.g. ssh homelab@192.168.100.48
ssh ansible@<server-LAN-ip>
```
Both must succeed with the key. If a user gets `Permission denied (publickey)`
but you *reach* the banner, it's an `AllowUsers` issue in the **currently live**
`sshd_config`, fixed by the next step (§5.8). A **timeout** instead means the
firewall is still blocking your LAN — recheck `lan_cidr` and re-run §5.6.

### 5.8 SSH — phase 2: apply the hardened config
```bash
~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production \
    --tags ssh -K
```
The safety gates run first (real key present, no placeholder, key file on disk),
then the hardened `sshd_config` is written (validated with `sshd -t`) and `sshd`
is restarted. **Existing sessions are not dropped.** Re-test §5.7 — the account
that was denied should now work.

### 5.9 Full converge (everything else)
No backup drive yet? Skip backups (the mount guard would correctly abort):
```bash
~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production \
    --skip-tags backups -K
```
This applies hardening, Fail2ban, AppArmor, audit (AIDE db init — **can take
several minutes**), auto-updates, Docker, and redeploys the monitoring/proxy
stacks. Set `operator`'s login password so password-sudo works: `sudo passwd homelab`.

### 5.10 Tailscale & verification
```bash
sudo tailscale up --ssh --accept-routes    # if not already up
make verify && make test                   # posture asserts + testinfra smoke tests
```

---

## 6. The SSH anti-lockout design

The `users_ssh` role is split into two stages so a first run can't lock you out:

- **Stage 1 (bootstrap, tags `ssh`,`bootstrap`)** — create the admin/automation
  account, create `extra_users`, install every key, configure sudo. **Never
  restricts login.** Always safe to run.
- **Stage 2 (lockdown, tag `ssh-lockdown`)** — write the restrictive
  `sshd_config` and restart `sshd`. Guarded by:
  - `ssh_lockdown_enabled` (default true; set false to defer hardening entirely),
  - a **safety gate** that asserts `admin_ssh_authorized_keys` is a real key (no
    `REPLACE_ME`) and that `/home/<admin>/.ssh/authorized_keys` exists non-empty,
  - a second gate asserting every `ssh: true` entry in `extra_users` has a real,
    non-placeholder key — so you can never add an unreachable account to
    `AllowUsers`.

`AllowUsers` is **computed**: `admin_user` plus every `extra_users` entry with
`ssh: true`. Skip the whole lockdown on a risky first run with
`--skip-tags ssh-lockdown`.

---

## 7. Gotchas & lessons

**The five things that cost us time — check these first when something's weird.**

1. **`lan_cidr` must match your real LAN.** The default was `192.168.1.0/24` but
   the actual LAN is `192.168.100.0/24`. A mismatch makes UFW drop SSH from your
   own laptop → **connection *timeout*** (not "refused"). It also narrows the
   `sshd` `Match Address` block. Confirm with `hostname -I`.
2. **Tailscale SSH ≠ OpenSSH.** Hardening `sshd_config` does **not** affect
   Tailscale SSH (served by `tailscaled`). This is why the automation account
   stayed reachable throughout, and why it's a reliable safety net. Corollary:
   testing the *OpenSSH key* path requires connecting to the **LAN IP**, not the
   tailnet `100.x` IP (which would be intercepted by Tailscale SSH).
3. **`AllowUsers` denies before keys are even tried.** A correct key + correct
   permissions still yields `Permission denied (publickey)` if the user isn't in
   the live `sshd_config`'s `AllowUsers`. A previously-applied (stale) config can
   list only `ansible`; re-applying the current config fixes it.
4. **Run as `homelab` with `-K`.** `ansible-playbook` isn't on `$PATH` (it's in
   `~/homelab/.venv/bin`), and `homelab` has password sudo, so every run needs
   `-K`. The `ansible` account is passwordless but can't read the checkout in
   `homelab`'s home.
5. **The vault moved.** It's now per-environment at
   `inventories/production/group_vars/all/vault.yml`. After a `git pull` on an
   old checkout, move it there once (§5.2). It's gitignored at the new path.

Non-blocking notes:
- `DEPRECATION WARNING: INJECT_FACTS_AS_VARS` appears on every run — harmless
  (ansible-core deprecating top-level `ansible_distribution`). Cleanup someday.
- "connection is not using a post-quantum key exchange" is an OpenSSH client
  notice, not an error.

---

## 8. Day-2 operations

Everything runs through tags on `site.yml`. As the `homelab` user, prefix with
the venv path and add `-K`; the `make` targets assume the venv is on `PATH`
(via `make`), so they also need a passwordless context or an edited invocation.

| Task | Command |
|---|---|
| Preview all changes | `ansible-playbook site.yml -i inventories/production --check --diff -K` |
| Apply only security plane | `... --tags security -K` |
| Apply only the firewall | `... --tags firewall -K` |
| Re-deploy monitoring + proxy | `... --tags "services,docker" -K` |
| Re-apply SSH (bootstrap+lockdown) | `... --tags ssh -K` |
| Edit secrets | `ansible-vault edit inventories/production/group_vars/all/vault.yml` |
| Prove idempotence | run the full converge twice; second run = `changed=0` |

Tags available: `base, bootstrap, ssh, ssh-lockdown, users, network, tailscale,
ddns, security, firewall, fail2ban, apparmor, hardening, cis, updates, audit,
docker, services, monitoring, backups`.

---

## 9. Backups

Backups are **deferred** until a dedicated drive is mounted. The `backups` role
**refuses to run** unless `/mnt/backup` is its own mounted filesystem
(`borg_require_mounted: true`) — this prevents silently writing "backups" onto
the root disk with no real off-disk copy.

To enable later:
1. Attach the external drive / NAS and mount it at `/mnt/backup` (add an
   `/etc/fstab` entry so it persists across reboots).
2. Confirm: `mountpoint -q /mnt/backup && echo OK`.
3. Run just the backups role:
   ```bash
   ~/homelab/.venv/bin/ansible-playbook site.yml -i inventories/production --tags backups -K
   ```
4. `borgmatic` initialises the repo and installs a systemd timer.
   **Store `vault_borg_passphrase` in a password manager — losing it loses the
   backups.**

---

## 10. Verification & health checks

```bash
# Ansible posture asserts + testinfra smoke tests
make verify
make test

# Manual spot checks
sudo ufw status verbose                    # active, deny incoming, your LAN allowed
sudo grep -E '^AllowUsers|^Match' /etc/ssh/sshd_config
docker ps --format '{{.Names}}'            # caddy prometheus grafana node-exporter cadvisor
sudo fail2ban-client status sshd
sudo aa-status | tail -1                   # profiles in enforce mode
tailscale status
```

testinfra also verifies the **Docker/UFW bypass is closed** (ufw-docker block
present, internal ports loopback-only, no container binding `0.0.0.0` except
Caddy).

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ssh user@lan-ip` **times out** | UFW blocking your LAN (`lan_cidr` wrong/stale) | Fix `lan_cidr`, re-run `--tags firewall -K` |
| `Permission denied (publickey)` but banner shows | User not in live `sshd_config` `AllowUsers` | Re-run `--tags ssh -K` |
| `sudo: a password is required` mid-run | Ran as `homelab` without `-K` | Add `-K` |
| `Command 'ansible-playbook' not found` | venv not on `$PATH` | Use `~/homelab/.venv/bin/ansible-playbook` |
| Play aborts at "Safety gate … usable admin key" | `REPLACE_ME` still in a key | Put the real key in group_vars |
| Play aborts at "backup target must be … mounted" | `/mnt/backup` not mounted | Mount the drive, or `--skip-tags backups` |
| `Error … vault password file … not found` | `~/.vault_pass` missing | `echo <pw> > ~/.vault_pass && chmod 600 ~/.vault_pass` |
| Vault won't decrypt | Wrong `~/.vault_pass`, or vault at old path | Fix password; ensure vault at per-env path |

---

## 12. Break-glass recovery

If you ever can't SSH in at all:

1. **Console.** Sit at the machine (or use its hypervisor/IPMI console). The
   `homelab` desktop login always works — OpenSSH hardening never affects it.
2. **Tailscale SSH.** From any tailnet device: `ssh ansible@homelab-01` (or the
   `100.x` IP). Unaffected by `sshd` hardening as long as `tailscaled` is up.
3. From either, undo a bad SSH change:
   ```bash
   sudo cp /etc/ssh/sshd_config /root/sshd_config.bak
   sudo sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
   sudo sshd -t && sudo systemctl restart ssh
   ```
   or re-run the playbook with `-e ssh_lockdown_enabled=false` to back the
   hardening out cleanly, then re-converge once fixed.
4. If Tailscale itself is the problem: `sudo tailscale up --ssh --accept-routes`.

> The design goal is that **no single change can lock you out**: console +
> Tailscale SSH + a key-based OpenSSH fallback are three independent doors.
