# DAO Agent Portal

个人 Agent 配置中心。统一管理 **skills**、**plugins**、**commands** 和 **configurations**，服务于 OpenCode 和 Claude Desktop。通过共享资源层，一处更新，多处生效。

**非破坏性设计。** 不移动、不删除任何文件。仅扩展（不替换）你现有的 agent 配置。原有配置本身就是备份。

## 目录结构

```
dao-agent-portal/
├── bootstrap.sh                  # 安装脚本（非破坏性）
├── .env / .env.example           # 本地 secrets（git 忽略）
├── .gitignore
│
├── shared/                       # 跨 agent 共享资源
│   ├── skills/                   # 所有技能（扁平存放，含 vendor 引用）
│   ├── plugins/                  # OpenCode 插件
│   └── commands/                 # OpenCode 自定义命令
│
├── vendor/                       # 第三方技能（git submodule）
│   └── antfu-skills/
│
├── opencode/                     # OpenCode 配置（参考 + 模板）
│   ├── opencode.json.template
│   ├── AGENTS.md
│   ├── memory-instructions.md
│   └── models.json
│
├── claude/                       # Claude Desktop 配置参考
│
└── scripts/
    ├── git-hooks/pre-commit      # 密钥泄漏防护
    └── add-repo-to-config.py     # 安全修改 opencode.json
```

## 首次启用

```bash
# 1. 克隆
git clone git@github.com:daosrc/dao-agent-portal.git
cd dao-agent-portal

# 2. 初始化子模块
git submodule init && git submodule update

# 3. 配置 API keys
cp .env.example .env
# 编辑 .env —— 填入 QINIU_API_KEY 和 CONTEXT7_API_KEY

# 4. 运行安装脚本
./bootstrap.sh
```

### bootstrap 做了什么

| 步骤 | 操作 | 破坏性？ |
|------|------|---------|
| 编译配置 | 从 template 生成 `opencode.json` | 否 |
| 初始化子模块 | 拉取 `vendor/antfu-skills/` | 否 |
| Vendor symlink | 在 repo 内创建 `shared/skills/antfu-*` 软链 | 否 |
| Git hooks | 安装提交前密钥扫描 | 否 |
| 修改配置 | 向 `~/.config/opencode/opencode.json` 添加 `shared/skills/` 路径 | 仅编辑一行（可逆） |

⚠ 你的原始配置文件保持不变。**没有文件被移动、删除、或覆盖。**

## 恢复原始配置

由于 bootstrap 从不删除任何东西，恢复非常简单：

```bash
# 编辑 ~/.config/opencode/opencode.json
# 找到 "skills.paths" 数组，删除包含 repo 路径的那一行即可
```

原始配置仅在 `skills.paths` 中添加了一行，移除它即完全恢复。

如果你使用了 `--link` 模式（可选的完全接管）：
```bash
rm ~/.config/opencode && cp -a ~/dotfiles-backup/opencode ~/.config/opencode
rm ~/.claude/skills && cp -a ~/dotfiles-backup/claude-skills ~/.claude/skills
```

## 密钥保护

Pre-commit hook 在提交前扫描暂存文件，发现密钥模式时阻止提交：

- **`.gitignore` 保护**：`.env`、`opencode/opencode.json`、`node_modules/`
- **Pre-commit hook 保护**：扫描 `sk-`（OpenAI/Qiniu）、`ctx7sk-`（Context7）、`ghp_`/`gho_`（GitHub）等模式
- **Hook 位置**：`scripts/git-hooks/pre-commit`（bootstrap 自动安装）

若被阻止：
```bash
git reset HEAD <file>
```

## 添加新技能

```bash
cp -r /path/to/new-skill shared/skills/
git add shared/skills/new-skill
git commit -m "feat: add new-skill"
```

## 更新第三方技能

```bash
git submodule update --remote vendor/antfu-skills
./bootstrap.sh    # 重新同步 symlink
```
