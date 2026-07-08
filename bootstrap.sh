#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔════════════════════════════════════════╗"
echo "║   DAO Agent Portal — Bootstrap        ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "  Repo: $REPO_DIR"
echo "  Mode: non-destructive — no files moved or deleted"
echo ""

# ──────────────────────────────────────────────
#  1.  .env
# ──────────────────────────────────────────────
if [ ! -f "$REPO_DIR/.env" ]; then
  cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
  echo "⚠  Created .env from .env.example"
  echo "   Edit $REPO_DIR/.env to configure API keys"
  echo "   (Skills will work without keys; only opencode.json compile needs them)"
  echo ""
fi

# ──────────────────────────────────────────────
#  2.  Compile opencode.json from template
# ──────────────────────────────────────────────
set -a; source "$REPO_DIR/.env"; set +a
echo "◆ Compiling opencode/opencode.json from template..."
sed -e "s/{{QINIU_API_KEY}}/${QINIU_API_KEY:-}/g" \
    -e "s/{{CONTEXT7_API_KEY}}/${CONTEXT7_API_KEY:-}/g" \
    "$REPO_DIR/opencode/opencode.json.template" \
    > "$REPO_DIR/opencode/opencode.json"
echo "  ✅ opencode/opencode.json generated"
echo ""

# ──────────────────────────────────────────────
#  3.  Compile claude/settings.json from template
# ──────────────────────────────────────────────
echo "◆ Compiling claude/settings.json from template..."
sed -e "s|{{ANTHROPIC_AUTH_TOKEN}}|${ANTHROPIC_AUTH_TOKEN:-}|g" \
    -e "s|{{ANTHROPIC_BASE_URL}}|${ANTHROPIC_BASE_URL:-}|g" \
    -e "s|{{ANTHROPIC_MODEL}}|${ANTHROPIC_MODEL:-}|g" \
    -e "s|{{ANTHROPIC_DEFAULT_SONNET_MODEL}}|${ANTHROPIC_DEFAULT_SONNET_MODEL:-}|g" \
    -e "s|{{ANTHROPIC_DEFAULT_HAIKU_MODEL}}|${ANTHROPIC_DEFAULT_HAIKU_MODEL:-}|g" \
    -e "s|{{ANTHROPIC_SMALL_FAST_MODEL}}|${ANTHROPIC_SMALL_FAST_MODEL:-}|g" \
    -e "s|{{HTTP_PROXY}}|${HTTP_PROXY:-}|g" \
    -e "s|{{HTTPS_PROXY}}|${HTTPS_PROXY:-}|g" \
    -e "s|{{NO_PROXY}}|${NO_PROXY:-}|g" \
    -e "s|{{REPO_DIR}}|${REPO_DIR}|g" \
    "$REPO_DIR/claude/settings.json.template" \
    > "$REPO_DIR/claude/settings.json"
echo "  ✅ claude/settings.json generated"
echo ""

# ──────────────────────────────────────────────
#  5.  Submodules
# ──────────────────────────────────────────────
if [ ! -f "$REPO_DIR/vendor/antfu-skills/skills/antfu/SKILL.md" ]; then
  echo "◆ Initializing git submodule (vendor/antfu-skills)..."
  cd "$REPO_DIR" && git submodule init && git submodule update && cd "$REPO_DIR"
  echo "  ✅ Submodule initialized"
  echo ""
fi

# ──────────────────────────────────────────────
#  6.  Vendor symlinks (in-repo only)
# ──────────────────────────────────────────────
echo "◆ Syncing vendor skill symlinks..."
VENDOR_DIR="$REPO_DIR/vendor/antfu-skills/skills"
TARGET_DIR="$REPO_DIR/shared/skills"
count=0
for skill_dir in "$VENDOR_DIR"/*/; do
  base=$(basename "$skill_dir")
  link_name="antfu-$base"
  if [ ! -e "$TARGET_DIR/$link_name" ]; then
    ln -sf "../../$VENDOR_DIR/$base" "$TARGET_DIR/$link_name"
    echo "  ➕ $link_name"
    count=$((count + 1))
  fi
done
[ "$count" -eq 0 ] && echo "  ✓ All vendor symlinks up to date" \
                   || echo "  ✅ $count new symlinks created"
echo ""

# ──────────────────────────────────────────────
#  7.  Git pre-commit hook
# ──────────────────────────────────────────────
if git rev-parse --git-dir >/dev/null 2>&1; then
  git config core.hooksPath scripts/git-hooks
  echo "  ✅ Git pre-commit hook installed"
  echo ""
fi

# ──────────────────────────────────────────────
#  8.  Add repo skills to existing agent config
# ──────────────────────────────────────────────
ORIG_CONFIG="$HOME/.config/opencode/opencode.json"
MODIFIED=0

if [ -f "$ORIG_CONFIG" ]; then
  echo "◆ Detected existing OpenCode config at $ORIG_CONFIG"
  python3 "$REPO_DIR/scripts/add-repo-to-config.py" "$REPO_DIR" && MODIFIED=$?
  echo ""
fi

# ──────────────────────────────────────────────
#  9.  Summary
# ──────────────────────────────────────────────
echo "╔════════════════════════════════════════╗"
echo "║   Setup complete                       ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "  Repo skills:        $REPO_DIR/shared/skills/  (43 skills)"
echo "  Repo plugins:       $REPO_DIR/shared/plugins/"
echo "  Repo commands:      $REPO_DIR/shared/commands/"
echo ""

if [ "$MODIFIED" -eq 1 ]; then
  echo "  To revert, open $ORIG_CONFIG and remove this line:"
  echo "    \"$REPO_DIR/shared/skills\""
  echo "  from the \"skills.paths\" array."
  echo ""
fi

echo "─────────────────────────────────────────"
echo "  Restore original config at any time:"
echo ""
echo "  Edit ~/.config/opencode/opencode.json"
echo "  Remove the repo path from skills.paths"
echo "  Done — no files were moved or deleted."
echo "─────────────────────────────────────────"
echo ""

# ──────────────────────────────────────────────
#  --link  (optional full takeover)
# ──────────────────────────────────────────────
if [ "${1:-}" = "--link" ]; then
  echo "◆ --link mode: full takeover (destructive)"
  echo "  This replaces ~/.config/opencode with a symlink to the repo."
  echo "  Backup at: ~/dotfiles-backup/"
  echo ""
  read -r -p "  Proceed? (y/N) " reply
  if [ "$reply" != "y" ] && [ "$reply" != "Y" ]; then
    echo "  ✋ Aborted."; exit 0
  fi

  # Backup
  mkdir -p "$HOME/dotfiles-backup"
  [ -e "$HOME/.config/opencode" ] && cp -a "$HOME/.config/opencode" "$HOME/dotfiles-backup/opencode"
  [ -e "$HOME/.claude/skills" ] && cp -a "$HOME/.claude/skills" "$HOME/dotfiles-backup/claude-skills"

  # Replace
  rm -rf "$HOME/.config/opencode"
  ln -sf "$REPO_DIR/opencode" "$HOME/.config/opencode"
  [ -e "$HOME/.claude/skills" ] && rm -rf "$HOME/.claude/skills"
  ln -sf "$REPO_DIR/shared/skills" "$HOME/.claude/skills"

  echo ""
  echo "  ✅ Symlinks created"
  echo "  Backup at: ~/dotfiles-backup/"
  echo ""
  echo "  To restore:"
  echo "    rm ~/.config/opencode && cp -a ~/dotfiles-backup/opencode ~/.config/opencode"
  echo "    rm ~/.claude/skills && cp -a ~/dotfiles-backup/claude-skills ~/.claude/skills"
fi
