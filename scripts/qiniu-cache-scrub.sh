#!/usr/bin/env bash
# Remove copies of the current Qiniu API key from OpenChamber's Electron HTTP cache.
#
# OpenChamber caches responses from the local opencode server, and some of those
# responses (provider list, session content) carry the resolved credential. Each
# new session can re-add such copies, so run this periodically or on quit.
#
# Usage:
#   ./qiniu-cache-scrub.sh          # report only; refuses if OpenChamber is running
#   ./qiniu-cache-scrub.sh --force  # delete even while OpenChamber is running (cache misses only)
#   ./qiniu-cache-scrub.sh --dry-run

set -euo pipefail

KEYCHAIN_ACCOUNT="${USER}"
KEYCHAIN_SERVICE="qiniu-ai"
CACHE_DIR="$HOME/Library/Application Support/OpenChamber/Cache/Cache_Data"

die() { echo "error: $*" >&2; exit 1; }

mode="report"
for arg in "$@"; do
  case "$arg" in
    --force) mode="force" ;;
    --dry-run) mode="dry" ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) die "unknown option: $arg" ;;
  esac
done

[ -d "$CACHE_DIR" ] || die "cache dir not found: $CACHE_DIR"

key="$(security find-generic-password -a "$KEYCHAIN_ACCOUNT" -s "$KEYCHAIN_SERVICE" -w 2>/dev/null || true)"
[ -n "$key" ] || die "keychain item $KEYCHAIN_SERVICE not found"

running=0
# `pgrep -f` on macOS does not reliably match the main Electron process here,
# so look at the full command lines instead.
if ps -Ao command= | grep -Fq "/Applications/OpenChamber.app/Contents/MacOS/OpenChamber"; then
  running=1
fi

echo "cache dir       : $CACHE_DIR"
echo "OpenChamber     : $([ "$running" -eq 1 ] && echo running || echo stopped)"

if [ "$running" -eq 1 ] && [ "$mode" = "report" ]; then
  echo
  echo "Refusing to delete while OpenChamber is running."
  echo "Quit it first, or re-run with --force (deleting cache files only causes cache misses)."
  exit 2
fi

KEY="$key" CACHE_DIR="$CACHE_DIR" MODE="$mode" python3 - <<'PY'
import os, pathlib

key = os.environ["KEY"].encode()
root = pathlib.Path(os.environ["CACHE_DIR"])
mode = os.environ["MODE"]

hits = []
for f in root.rglob("*"):
    try:
        if not f.is_file() or f.is_symlink() or f.stat().st_size > 64 * 1024 * 1024:
            continue
        if key in f.read_bytes():
            hits.append(f)
    except Exception:
        continue

print(f"files with key  : {len(hits)}")
if not hits or mode == "dry":
    raise SystemExit(0)

removed = 0
for f in hits:
    try:
        f.unlink()
        removed += 1
    except Exception as e:
        print(f"  failed: {f.name}: {e}")

print(f"deleted         : {removed}")
PY

if [ "$mode" != "dry" ]; then
  echo "note            : the cache will re-fill on use; key copies can come back after new sessions."
fi
