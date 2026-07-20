# Architecture & Design Decisions

## 1. Two-plane model

The core decision is separating the **host plane** from the **service plane**.

```mermaid
flowchart TB
    subgraph Control["Control (IaC)"]
        A[Ansible site.yml] -->|configures OS| HOST
        A -->|lays down compose + .env| SVC
    end
    subgraph HOST["Host plane (Ansible-managed)"]
        direction LR
        H1[SSH / users] --- H2[CIS hardening]
        H2 --- H3[UFW + Fail2ban]
        H3 --- H4[AppArmor]
        H4 --- H5[auto-updates]
        H5 --- H6[Lynis / AIDE]
        H6 --- H7[Tailscale / DuckDNS]
        H7 --- H8[Docker engine]
    end
    subgraph SVC["Service plane (Docker Compose)"]
        direction LR
        S1[Caddy proxy] --> S2[Grafana]
        S1 --> S3[Educational apps]
        S4[Prometheus] --> S2
        S5[node-exporter] --> S4
        S6[cAdvisor] --> S4
    end
    HOST --> SVC
```

**Why:** the host changes rarely and wants declarative convergence; services
change often and want the fast Compose loop. Installing apps with Ansible `apt`
would couple them and make rollbacks painful. Ansible *deposits* compose files
and renders `.env` from Vault, Docker *runs* them.

## 2. Network & access model

```mermaid
flowchart LR
    Internet(("Internet")) -->|"80/443 only (port-forward)"| Router
    Router -->|"deny SSH"| X[[UFW default deny]]
    Router --> Caddy
    Laptop["Operator laptop"] -. Tailscale (WireGuard) .-> TS[tailscale0]
    TS -->|SSH allowed| SSHD[sshd]
    LAN["Home LAN"] -->|SSH allowed| SSHD
    Caddy -->|reverse proxy| Grafana & Apps
    subgraph Server
        X --- SSHD
        Caddy
        Grafana
        Apps
    end
```

- **SSH is never exposed to the internet.** UFW allows port 22 only from the LAN
  CIDR and the Tailscale CGNAT range (`100.64.0.0/10`); remote admin goes through
  Tailscale's WireGuard tunnel. This removes public brute-force surface entirely.
- **Only Caddy is public** (80/443). Backends bind to `127.0.0.1` or the internal
  `edge`/`monitoring` Docker networks — never a public host port.

## 3. The Docker × UFW trap (and the fix)

```mermaid
sequenceDiagram
    participant U as UFW rules
    participant D as Docker (iptables)
    participant P as Published port
    Note over U,P: Without ufw-docker
    D->>P: inserts ACCEPT in DOCKER chain
    U--xP: UFW deny is bypassed ❌
    Note over U,P: With ufw-docker
    D->>U: traffic routed via DOCKER-USER
    U->>P: UFW verdict wins ✅
```

Docker programs iptables directly and **bypasses UFW**, so `docker run -p 8080:80`
is reachable even when UFW denies 8080. We mitigate two ways: publish backends on
`127.0.0.1` + front them with Caddy, and install `ufw-docker` so the `DOCKER-USER`
chain honours UFW. Without this, the firewall is cosmetic.

## 4. Hardening: why CIS **Level 1**, not Level 2

`usg` (Ubuntu Security Guide) applies CIS benchmarks. We pick **Level 1 Server**
deliberately:

- This is a **Desktop LTS** used interactively. Level 2 / STIG remounts `/tmp`,
  disables kernel modules and GDM features, and enforces auditd rules that break
  a GUI workstation.
- Level 1 gives strong, low-friction wins. We then **add** targeted controls
  `usg` doesn't cover well: sysctl network/kernel hardening, `pwquality`,
  `login.defs` aging, strict file perms, module blacklist, core-dump disabling.

Everything is auditable: `usg audit` runs report-only in the play; `usg fix`
applies remediation and is idempotent.

## 5. Defence-in-depth layers

```mermaid
flowchart TB
    L1[Tailscale overlay: no public SSH] --> L2[UFW: default deny + DOCKER-USER]
    L2 --> L3[Fail2ban: ban brute-force]
    L3 --> L4[SSH: keys only, strong crypto]
    L4 --> L5[CIS L1 + sysctl/PAM hardening]
    L5 --> L6[AppArmor: MAC enforce]
    L6 --> L7[Auto security updates]
    L7 --> L8[Lynis posture + AIDE integrity]
    L8 --> L9[Borg encrypted backups]
```

Each layer is independent: compromise of one does not defeat the others.

## 6. Backups

Borg via **borgmatic** to a local encrypted, deduplicated repository (external
drive / NAS mount at `/mnt/backup`). The borgmatic config uses the flat schema
(borgmatic ≥ 1.8, Ubuntu 24.04+). Retention 7 daily / 4 weekly / 6 monthly,
pruned after each run; integrity checks every two weeks. Docker volumes, `/etc`,
`/opt/homelab` and the admin home are included. For databases, borgmatic dumps
them consistently *before* the filesystem snapshot (hook stubs in the config).

> Off-site is the one gap of a local-only repo. `borgmatic` can add a second
> `repositories:` entry (e.g. an SSH target or rclone remote) with no host changes.

## 7. Monitoring

Prometheus scrapes **node-exporter** (host metrics) and **cAdvisor** (per-container
metrics); Grafana visualises them with a pre-provisioned Prometheus datasource
**and a pre-provisioned "Homelab Overview" dashboard** (uptime, running
containers, memory/disk gauges, CPU, network I/O, per-container CPU & memory) that
loads automatically on first boot — no manual import. Grafana is the only
monitoring component reachable externally, and only through Caddy over HTTPS.
Prometheus binds to loopback.

Dashboards live in `compose/monitoring/grafana/provisioning/dashboards/json/`;
drop any additional `*.json` there and it is picked up within 30s.

## 8. Idempotency & testing strategy

Three levels, wired into the Makefile:

1. **Static** — `yamllint` + `ansible-lint` (production profile).
2. **Idempotence** — `make idempotence` runs the play twice and fails if the
   second run reports any `changed`.
3. **Behavioural** — `tests/verify.yml` (in-Ansible asserts) and
   `tests/test_homelab.py` (testinfra: sshd config, UFW active, Fail2ban jail,
   AppArmor enforce, sysctl values, timers enabled, containers running).

## 9. Secrets

Ansible Vault (`inventories/<env>/group_vars/all/vault.yml`, one per
environment) holds the Ubuntu Pro token, DuckDNS token, Grafana password and
Borg passphrase. It renders directly into systemd env files and compose `.env`
at deploy time; nothing secret is committed. Chosen over SOPS/age for zero extra
dependencies in a single-operator homelab.

## 10. Variable layering

Configuration is resolved in three precedence layers (lowest to highest):

1. **`roles/<role>/defaults/main.yml`** — each role owns its tunables and ships
   sane defaults, so a role is self-contained and reusable.
2. **`group_vars/all/main.yml`** — cross-role constants identical in every
   environment (`admin_user`, `ssh_port`, `apt_repo_release`, `stacks_root`).
3. **`inventories/<env>/group_vars/all/`** — per-environment identity, network,
   domain and secrets. This is the only layer that differs between prod and
   staging, and it wins over the two below it.

Select an environment with `-i inventories/production` or `-i inventories/staging`
(`make apply ENV=staging`).
