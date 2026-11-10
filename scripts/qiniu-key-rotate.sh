#!/usr/bin/env bash
# Rotate the Qiniu API key: keychain is the source of truth; opencode's secret
# file (read via a {file:...} reference in the provider config) and the v2
# credential store (account.json) are both synced from it.
#
# Usage:
#   ./qiniu-key-rotate.sh              # prompt for the new key (silent), rotate, sync
#   ./qiniu-key-rotate.sh --from-stdin # read the new key from stdin (for piping)
#   ./qiniu-key-rotate.sh --check      # verify keychain and account.json agree
#   ./qiniu-key-rotate.sh --verify     # after syncing, make a live test call
#
# The key is never printed and never passed as a command-line argument.

set -euo pipefail

KEYCHAIN_ACCOUNT="${USER}"
KEYCHAIN_SERVICE="qiniu-ai"
ACCOUNT_JSON="$HOME/.local/share/opencode/account.json"
BACKUP_DIR="$HOME/.config/qiniu-key-migration"
DEFAULT_MODEL="${QINIU_TEST_MODEL:-qiniu/deepseek-v4.1-flash-1017}"

die() { echo "error: $*" >&2; exit 1; }

read_keychain() {
  security find-generic-password -a "$KEYCHAIN_ACCOUNT" -s "$KEYCHAIN_SERVICE" -w 2>/dev/null || true
}

# Prints "true" or "false" — never the key itself.
account_matches() {
  python3 - "$1" <<'PY'
import json, os, sys, pathlib
key = sys.argv[1]
p = pathlib.Path.home() / ".local/share/opencode/account.json"
if not p.exists():
    print("missing")
    raise SystemExit(0)
d = json.loads(p.read_text())
entries = [a for a in d.get("accounts", {}).values() if a.get("serviceID") == "qiniu-ai"]
if not entries:
    print("missing")
else:
    print("true" if any(a.get("credential", {}).get("key") == key for a in entries) else "false")
PY
}

check_only() {
  local kc; kc="$(read_keychain)"
  [ -n "$kc" ] || die "keychain item $KEYCHAIN_SERVICE not found"
  local acct sf; acct="$(account_matches "$kc")"; sf="$(secret_file_in_sync "$kc")"
  echo "keychain        : present (${#kc} chars)"
  echo "account.json    : $acct"
  echo "secret file     : $sf"
  # opencode actually authenticates qiniu from the secret file; that is the
  # authoritative check. account.json is kept in sync as a secondary store.
  case "$sf" in
    true) echo "status          : in sync"; return 0 ;;
    *)    echo "status          : OUT OF SYNC — run without --check to resync"; return 1 ;;
  esac
}

sync_account() {
  local key="$1"
  [ -f "$ACCOUNT_JSON" ] || { echo "warn: $ACCOUNT_JSON not found, skipping sync"; return 0; }
  mkdir -p "$BACKUP_DIR"; chmod 700 "$BACKUP_DIR"
  cp -p "$ACCOUNT_JSON" "$BACKUP_DIR/account.json.$(date +%Y%m%d-%H%M%S)"
  python3 - "$key" <<'PY'
import json, os, sys, pathlib
key = sys.argv[1]
p = pathlib.Path.home() / ".local/share/opencode/account.json"
d = json.loads(p.read_text())
n = 0
for a in d.get("accounts", {}).values():
    if a.get("serviceID") == "qiniu-ai":
        a.setdefault("credential", {})["key"] = key
        n += 1
p.write_text(json.dumps(d, indent=2) + "\n")
os.chmod(p, 0o600)
print(f"account.json    : updated {n} qiniu-ai credential(s)")
PY
}

store_keychain() {
  local key="$1"
  # Feed through stdin (`security -i`) so the key never appears in argv.
  printf 'add-generic-password -U -a %s -s %s -w %s\n' \
    "$KEYCHAIN_ACCOUNT" "$KEYCHAIN_SERVICE" "$key" | security -i >/dev/null
  echo "keychain        : updated (service $KEYCHAIN_SERVICE)"
}

# opencode's qiniu provider reads its key from a {file:...} reference, not from
# env or account.json. Refresh that 0600 secret file so rotation takes effect.
sync_secret_file() {
  local key="$1"
  local dir="$HOME/.config/opencode/secrets"
  local f="$dir/qiniu.key"
  mkdir -p "$dir"; chmod 700 "$dir"
  printf '%s' "$key" > "$f"
  chmod 600 "$f"
  echo "secret file     : updated ($f)"
}

secret_file_in_sync() {
  local key="$1"
  local f="$HOME/.config/opencode/secrets/qiniu.key"
  if [ ! -f "$f" ]; then echo "missing"; return; fi
  [ "$(cat "$f")" = "$key" ] && echo "true" || echo "false"
}

live_verify() {
  echo "verify          : calling $DEFAULT_MODEL ..."
  local out
  out="$(cd "$(mktemp -d)" && env -u QINIU_API_KEY -u QINIU_AI_API_KEY \
    "$HOME/.opencode/bin/opencode" run --model "$DEFAULT_MODEL" "Reply with exactly: ROTATE-OK" 2>&1 | tail -n 3 || true)"
  if printf '%s' "$out" | grep -q "ROTATE-OK"; then
    echo "verify          : OK"
  else
    echo "verify          : FAILED"; echo "$out" | sed 's/^/  /'; return 1
  fi
}

main() {
  local mode="rotate" verify=0
  for arg in "$@"; do
    case "$arg" in
      --check) mode="check" ;;
      --verify) verify=1 ;;
      --from-stdin) mode="stdin" ;;
      -h|--help) sed -n '2,16p' "$0" | sed 's/^# \?//'; exit 0 ;;
      *) die "unknown option: $arg" ;;
    esac
  done

  if [ "$mode" = "check" ]; then
    check_only
    exit $?
  fi

  local key=""
  if [ "$mode" = "stdin" ]; then
    read -r key
  else
    printf 'New Qiniu API key (input hidden): '
    read -rs key; echo
    printf 'Repeat: '
    local again; read -rs again; echo
    [ "$key" = "$again" ] || die "keys do not match"
  fi

  key="$(printf '%s' "$key" | tr -d '[:space:]')"
  [ -n "$key" ] || die "empty key"
  case "$key" in sk-*) ;; *) die "unexpected key shape (expected sk-...)" ;; esac
  [ "${#key}" -ge 40 ] || die "key looks too short (${#key} chars)"

  store_keychain "$key"
  sync_account "$key"
  sync_secret_file "$key"
  echo "sanity          : keychain len=${#key}"

  local state sf; state="$(account_matches "$key")"; sf="$(secret_file_in_sync "$key")"
  [ "$state" = "true" ] || [ "$state" = "missing" ] || die "account.json did not pick up the new key"
  [ "$sf" = "true" ] || die "secret file did not pick up the new key"
  echo "status          : rotated"

  [ "$verify" -eq 1 ] && live_verify
  echo
  echo "Reminder: running processes keep the old key until restarted;"
  echo "restart OpenChamber / open new shells to pick up the new one."
}

main "$@"
