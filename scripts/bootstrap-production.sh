#!/usr/bin/env bash
#
# bootstrap-production.sh — guided, lockout-safe provisioning of the homelab
# server. Walks the day-1 checklist in order, pausing for confirmation before
# anything irreversible (SSH lockdown). Safe to re-run: every phase is idempotent
# and you can answer "n" to skip a phase you've already done.
#
#   Usage:   ./scripts/bootstrap-production.sh [ENV]
#   ENV defaults to "production". Run from anywhere inside the repo.
#
set -euo pipefail

ENV="${1:-production}"

# --- pretty output ---------------------------------------------------------
if [[ -t 1 ]]; then
  BOLD=$'\e[1m'; RED=$'\e[31m'; GRN=$'\e[32m'; YLW=$'\e[33m'; BLU=$'\e[36m'; RST=$'\e[0m'
else
  BOLD=""; RED=""; GRN=""; YLW=""; BLU=""; RST=""
fi
say()  { printf '%s\n' "${BLU}${BOLD}==>${RST} ${BOLD}$*${RST}"; }
ok()   { printf '%s\n' "${GRN}  ✓${RST} $*"; }
warn() { printf '%s\n' "${YLW}  !${RST} $*"; }
die()  { printf '%s\n' "${RED}  ✗ $*${RST}" >&2; exit 1; }
confirm() { # confirm "question"  -> returns 0 on yes
  local a; read -r -p "${YLW}?? ${RST}$* ${BOLD}[y/N]${RST} " a || true
  [[ "$a" =~ ^[yY]$ ]]
}
pause() { read -r -p "${YLW}   ↳ press ENTER when done…${RST} " _ || true; }

# --- locate the repo & inventory ------------------------------------------
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
ANSIBLE_DIR="$REPO/ansible"
INV="inventories/$ENV"
GV="$ANSIBLE_DIR/$INV/group_vars/all"
VAULT="$GV/vault.yml"
[[ -d "$ANSIBLE_DIR/$INV" ]] || die "No inventory at ansible/$INV — is ENV='$ENV' correct?"

say "Homelab provisioning — environment: ${BOLD}$ENV${RST}"
echo "   repo: $REPO"
echo

# ===========================================================================
say "Phase 0 — prerequisites"
command -v ansible-playbook >/dev/null || die "ansible-playbook not found. Run 'make deps' first (or install ansible-core)."
command -v git >/dev/null            || die "git not found."
ok "ansible-playbook: $(ansible-playbook --version | head -1)"

if [[ ! -f "$HOME/.vault_pass" ]]; then
  warn "Vault password file ~/.vault_pass is missing (ansible.cfg expects it)."
  if confirm "Create ~/.vault_pass now (you'll type the vault password)?"; then
    read -r -s -p "   vault password: " vp; echo
    printf '%s' "$vp" > "$HOME/.vault_pass"; chmod 600 "$HOME/.vault_pass"; unset vp
    ok "~/.vault_pass written (chmod 600)."
  else
    die "Cannot continue without ~/.vault_pass."
  fi
else
  ok "~/.vault_pass present."
fi
echo

# ===========================================================================
say "Phase 1 — relocate the vault to the per-environment path (if needed)"
OLD_VAULT="$ANSIBLE_DIR/group_vars/all/vault.yml"
if [[ -f "$OLD_VAULT" && ! -f "$VAULT" ]]; then
  warn "Found an old-layout vault at ansible/group_vars/all/vault.yml."
  if confirm "Move it to ansible/$INV/group_vars/all/vault.yml?"; then
    mkdir -p "$GV"
    git -C "$REPO" mv "$OLD_VAULT" "$VAULT" 2>/dev/null || mv "$OLD_VAULT" "$VAULT"
    ok "Vault relocated."
  fi
elif [[ -f "$VAULT" ]]; then
  ok "Vault already at the per-env path."
else
  warn "No vault yet. Create one with:  make vault-create ENV=$ENV  (then 'make vault-edit ENV=$ENV')."
  confirm "Continue anyway?" || die "Set up the vault first."
fi
echo

# ===========================================================================
say "Phase 2 — real identity & keys"
echo "   Edit ${BOLD}ansible/$INV/group_vars/all/main.yml${RST} and set the REAL values:"
echo "     • admin_ssh_authorized_keys   (key for the 'ansible' automation account)"
echo "     • extra_users                 (operator + familia: real usernames and keys)"
echo "   Secrets (tokens, passwords) go in the encrypted vault: make vault-edit ENV=$ENV"
echo
MAIN_GV="$GV/main.yml"
if grep -q 'REPLACE_ME' "$MAIN_GV" 2>/dev/null; then
  warn "Placeholders (REPLACE_ME) still present in group_vars — SSH keys not set yet."
  if confirm "Open $MAIN_GV in \$EDITOR now?"; then "${EDITOR:-vi}" "$MAIN_GV"; fi
else
  ok "No REPLACE_ME placeholders left in group_vars."
fi
echo

# ===========================================================================
say "Phase 3 — install Ansible collections / tooling (optional)"
if confirm "Run 'make deps' now?"; then ( cd "$REPO" && make deps ); ok "deps installed."; fi
echo

# ===========================================================================
say "Phase 4 — SSH phase 1: create users + keys WITHOUT locking SSH down"
echo "   This creates the accounts and installs keys but leaves password auth on,"
echo "   so you can safely verify access before the hardening step."
if confirm "Run the safe SSH bootstrap now (--tags ssh --skip-tags ssh-lockdown)?"; then
  ( cd "$ANSIBLE_DIR" && ansible-playbook site.yml -i "$INV" --tags ssh --skip-tags ssh-lockdown )
  ok "Users and keys created; SSH still open."
fi
echo

# ===========================================================================
say "Phase 5 — CONFIRM SSH ACCESS (do not skip)"
echo "   ${BOLD}From another terminal${RST}, verify you can log in with your key, e.g.:"
echo "       ${BLU}ssh operator@<host>${RST}      ${BLU}ssh ansible@<host>${RST}"
warn "The next phase disables password auth and restricts AllowUsers."
pause
confirm "Did key-based SSH work for the account(s) you need?" \
  || die "Stopping before lockdown. Fix keys in group_vars, re-run Phase 4, and retry."
echo

# ===========================================================================
say "Phase 6 — set a login password for the operator account (for sudo)"
echo "   'operator' uses sudo WITH a password, so it needs a UNIX password set."
if confirm "Set operator's password now (sudo passwd operator)?"; then
  sudo passwd operator || warn "passwd failed — set it manually later."
fi
echo

# ===========================================================================
say "Phase 7 — full converge (applies the SSH lockdown + everything else)"
echo "   A safety gate inside the play still refuses to harden SSH if any"
echo "   SSH-enabled account has an empty/REPLACE_ME key."
if confirm "Show the dry-run diff first (recommended)?"; then
  ( cd "$ANSIBLE_DIR" && ansible-playbook site.yml -i "$INV" --check --diff ) || warn "dry-run reported changes/errors — review above."
fi
if confirm "Apply the full converge now (make apply ENV=$ENV)?"; then
  ( cd "$REPO" && make apply ENV="$ENV" )
  ok "Converge complete."
else
  warn "Skipped converge. Run it later with:  make apply ENV=$ENV"
fi
echo

# ===========================================================================
say "Phase 8 — Tailscale + backups + verification"
if confirm "Bring up Tailscale now (sudo tailscale up --ssh --accept-routes)?"; then
  sudo tailscale up --ssh --accept-routes || warn "tailscale up failed — run it manually."
fi
echo "   Mount the backup drive at the borg repo's parent before running backups."
if confirm "Run the verification suite (verify + test + idempotence)?"; then
  ( cd "$REPO" && make verify ENV="$ENV" && make test && make idempotence ENV="$ENV" ) \
    || warn "Some checks failed — review the output above."
fi
echo

say "${GRN}Done.${RST} Server '$ENV' provisioned. Re-run this script anytime; it's idempotent."
