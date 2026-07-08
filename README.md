# DAO Agent Portal

Personal agent configuration hub. Centrally manages **skills**, **plugins**, **commands**, and **configurations** for OpenCode and Claude Desktop — with a shared resource layer that keeps everything in sync across agents.

**Non-destructive by design.** No files are moved or deleted. Your existing agent config is only extended (not replaced). Your original setup acts as its own backup.

## Directory Structure

```
dao-agent-portal/
├── bootstrap.sh                  # Setup script (non-destructive)
├── .env / .env.example           # Local secrets (git-ignored)
├── .gitignore
│
├── shared/                       # Cross-agent shared resources
│   ├── skills/                   # All skills (flattened, vendor-ready)
│   ├── plugins/                  # OpenCode plugins
│   └── commands/                 # OpenCode custom commands
│
├── vendor/                       # Third-party skills (git submodule)
│   └── antfu-skills/
│
├── opencode/                     # OpenCode config (reference + template)
│   ├── opencode.json.template
│   ├── AGENTS.md
│   ├── memory-instructions.md
│   └── models.json
│
├── claude/                       # Claude Desktop config reference
│   ├── settings.json.template    # Compiled from .env by bootstrap
│   ├── settings.local.json       # Permission overrides
│   ├── claude_desktop_config.json
│   ├── statusline-command.sh
│   └── plugins/                  # Plugin marketplace metadata (backup)
│
└── scripts/
    ├── git-hooks/pre-commit      # Secret-leak prevention
    ├── add-repo-to-config.py     # Modify opencode.json safely
    └── sync-claude-skills.sh     # Sync repo skills → ~/.claude/skills
```

## Setup

```bash
# 1. Clone
git clone git@github.com:daosrc/dao-agent-portal.git
cd dao-agent-portal

# 2. Init submodules
git submodule init && git submodule update

# 3. Configure API keys
cp .env.example .env
# Edit .env — fill in QINIU_API_KEY and CONTEXT7_API_KEY

# 4. Run bootstrap
./bootstrap.sh
```

### What bootstrap.sh does

| Step | Action | Destructive? |
|------|--------|-------------|
| Compile config | Generate `opencode.json` from template | No |
| Init submodules | Pull `vendor/antfu-skills/` | No |
| Vendor symlinks | Create in-repo symlinks `shared/skills/antfu-*` | No |
| Git hooks | Install pre-commit secret scan | No |
| Modify config | Add `shared/skills/` path to `~/.config/opencode/opencode.json` | Config edited (reversible) |

⚠ Your original configuration files remain untouched. **No files are moved, deleted, or overwritten.**

## Restore Original Config

Since bootstrap never deletes anything, restoring is trivial:

```bash
# Edit ~/.config/opencode/opencode.json
# Find "skills.paths" and remove the line containing your-repo-path/shared/skills
```

The old config was never touched except for adding one line — removing it reverts everything.

If you used `--link` mode (optional full takeover):
```bash
rm ~/.config/opencode && cp -a ~/dotfiles-backup/opencode ~/.config/opencode
rm ~/.claude/skills && cp -a ~/dotfiles-backup/claude-skills ~/.claude/skills
```

## Sync Skills to Claude Code

Claude Code loads skills from `~/.claude/skills/` (no config key). To make repo skills available to Claude without replacing your existing setup:

```bash
# Link repo-unique skills (skips existing ones, non-destructive)
./scripts/sync-claude-skills.sh

# Force overwrite existing skills
./scripts/sync-claude-skills.sh --force

# Restore: remove only the symlinks that point to the repo
./scripts/sync-claude-skills.sh restore
```

The script respects existing skills — `image-ocr`, `hackernews`, `agent-browser` etc. are **skipped** unless you pass `--force`. Restore removes only repo-linked skills and leaves your originals intact.

## Secrets Protection

A pre-commit hook scans staged files and blocks commits containing API keys or tokens:

- **Protected by `.gitignore`**: `.env`, `opencode/opencode.json`, `node_modules/`
- **Protected by pre-commit hook**: scans for `sk-` (OpenAI/Qiniu), `ctx7sk-` (Context7), `ghp_`/`gho_` (GitHub), etc.
- **Hook location**: `scripts/git-hooks/pre-commit` (auto-installed by bootstrap)

If blocked:
```bash
git reset HEAD <file>
```

## Adding a New Skill

```bash
cp -r /path/to/new-skill shared/skills/
git add shared/skills/new-skill
git commit -m "feat: add new-skill"
```

## Updating Vendor Skills

```bash
git submodule update --remote vendor/antfu-skills
./bootstrap.sh    # Re-sync symlinks
```
