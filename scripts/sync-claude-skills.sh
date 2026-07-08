#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_SKILLS_DIR="$HOME/.claude/skills"
REPO_SKILLS_DIR="$REPO_DIR/shared/skills"

echo "╔════════════════════════════════════════╗"
echo "║   Sync repo skills → ~/.claude/skills ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "  Repo:  $REPO_SKILLS_DIR"
echo "  Claude: $CLAUDE_SKILLS_DIR"
echo ""

MODE="${1:-link}"

if [ "$MODE" = "restore" ]; then
  echo "◆ Restore: removing repo symlinks from ~/.claude/skills..."
  count=0
  for entry in "$CLAUDE_SKILLS_DIR"/*; do
    name=$(basename "$entry")
    [ "$name" = ".DS_Store" ] && continue
    if [ -L "$entry" ]; then
      target=$(readlink "$entry")
      if [[ "$target" == *"$REPO_DIR"* ]]; then
        rm "$entry"
        echo "  ✗ $name"
        count=$((count + 1))
      fi
    fi
  done
  [ "$count" -eq 0 ] && echo "  No repo symlinks found." \
                     || echo "  ✅ Removed $count symlinks."
  exit 0
fi

FORCE=0
if [ "$MODE" = "--force" ] || [ "${2:-}" = "--force" ]; then
  FORCE=1
fi

mkdir -p "$CLAUDE_SKILLS_DIR"

linked=0
skipped=0
forced=0

for skill_dir in "$REPO_SKILLS_DIR"/*/; do
  name=$(basename "$skill_dir")
  [ "$name" = ".DS_Store" ] && continue

  target="$CLAUDE_SKILLS_DIR/$name"

  if [ -e "$target" ]; then
    if [ "$FORCE" -eq 1 ]; then
      rm -rf "$target"
      ln -sf "$skill_dir" "$target"
      echo "  🔄 $name (overwritten)"
      forced=$((forced + 1))
    else
      echo "  — $name (exists, skipped)"
      skipped=$((skipped + 1))
    fi
  else
    ln -sf "$skill_dir" "$target"
    echo "  ➕ $name"
    linked=$((linked + 1))
  fi
done

echo ""
echo "  ✅ Linked: $linked   Skipped: $skipped   Forced: $forced"
echo ""

if [ "$skipped" -gt 0 ] && [ "$FORCE" -eq 0 ]; then
  echo "  Tip: re-run with --force to overwrite existing skills"
  echo ""
fi

echo "─────────────────────────────────────────"
echo "  To restore: $0 restore"
echo "─────────────────────────────────────────"
