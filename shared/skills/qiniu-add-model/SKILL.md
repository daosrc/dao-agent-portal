---
name: qiniu-add-model
description: 按模型名称把 Qiniu(Modelink) 模型写入 opencode 配置。当用户说“把这个模型加到 qiniu / 加到配置 / 新增模型 / 配置 XX 模型 / add model to qiniu”等，需要把某个模型名写入 opencode 的 provider.qiniu.models 时使用。只处理 qiniu 服务商。
---

# Qiniu 模型配置助手 (qiniu-add-model)

把用户给的模型名，去 Modelink 模型广场查询 → 模糊匹配 → 写入 opencode 配置的 `provider.qiniu.models`。

**只针对 qiniu 服务商**，其他 provider 不处理。

## 数据来源

- **Modelink 模型广场** `https://modelink.ai/zh-CN/models` —— 权威元数据（模型 id、名称、aliases、输入/输出模态、能力、上下文长度）。当前约 200 个模型，含最新的 `openai/gpt-6-astra`、`anthropic/claude-opus-5`、`deepseek/deepseek-v4.1-flash` 等。
- **Qiniu `/v1/models`** `https://api.qnaigc.com/v1/models` —— 交叉核对实际可用清单，补齐广场里没有的 id。

结果缓存到 `~/.cache/qiniu_add_model_models.json`（TTL 12 小时，`--refresh` 强制刷新）。

## 脚本位置

```
scripts/qiniu_add_model.py
```

## 用法

```bash
python3 scripts/qiniu_add_model.py <模型名> [选项]
```

### 常用命令

```bash
# 查询并写入（唯一命中时直接写）
python3 scripts/qiniu_add_model.py claude-opus-5

# 只看候选，不写配置
python3 scripts/qiniu_add_model.py opus --list

# 预览要写入的内容（不落盘）
python3 scripts/qiniu_add_model.py gpt-6-astra --dry-run

# 命中多个时，指定确切的模型 id 再写
python3 scripts/qiniu_add_model.py opus --pick anthropic/claude-opus-5

# 额外写入 reasoning=false（修复 qiniu chat/completions + 工具调用的报错）
python3 scripts/qiniu_add_model.py gpt-6-astra --reasoning false

# 只写某一个配置文件
python3 scripts/qiniu_add_model.py kimi-k3 --config ~/opencode.json
```

### 全部选项

| 选项 | 说明 |
|------|------|
| 位置参数 | 模型名称 / 关键词（可以是别名、id、部分名字） |
| `--pick <id>` | 直接指定确切的模型 id（消歧用） |
| `--key <key>` | 写入 `models` 的键，默认取 id 末段（如 `gpt-6-astra`） |
| `--reasoning true\|false` | 额外写入 `"reasoning"` 字段 |
| `--with-limits` | 额外写入 `limit.context` / `limit.output` |
| `--dry-run` | 只预览，不写文件 |
| `-y, --yes` | 多个候选时自动取最佳（不提示） |
| `--list` | 只列出候选/预览，不写入 |
| `--json` | 以 JSON 输出（供 agent 解析） |
| `--refresh` | 强制刷新模型目录缓存 |
| `--config PATH` | 目标配置文件，可重复；默认写下面三个 |

### 目标配置文件（默认全部写入）

1. `~/opencode.json` —— home 会话生效
2. `~/dao-agent-portal/opencode/opencode.json` —— dao-agent-portal 项目
3. `~/.config/opencode/opencode.json` —— 全局

若某个文件没有 `provider.qiniu`（如全局配置迁移后为空），脚本会自动创建
`qiniu` provider 块（`npm` / `baseURL` / `apiKey`）。

## 退出码与消歧流程（给 agent 用）

| 退出码 | 含义 | agent 该做什么 |
|--------|------|----------------|
| `0` | 唯一命中并已写入 | 汇报写入结果 |
| `1` | 没匹配到 | 让用户换个关键词 |
| `2` | **命中多个候选** | 把候选列表展示给用户，请其选择，然后用 `--pick <id>` 重跑 |

当命中多个时，stdout 会列出候选，例如：

```
“opus” 匹配到多个模型，请选择（用 --pick <id>）：
  anthropic/claude-opus-5  (Claude-Opus-5)  [66分]  ...
  anthropic/claude-4.8-opus  (Claude-4.8-Opus)  [66分]  ...
```

**Agent 处理方式**：把上面的候选（去掉“分”等噪声）以带序号的列表呈现给用户，让用户选一个，然后用
`--pick "<所选 id>"` 重新执行脚本。终端是 TTY 时脚本也会直接交互让你选序号。

## 写入内容

每个模型条目形如（与现有 qiniu 条目风格一致）：

```json
"claude-opus-5.5": {
  "name": "Claude Opus 5.5 (Qiniu)",
  "id": "anthropic/claude-opus-5.5",
  "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }
}
```

- `id` = Modelink 的模型 id（也是发给 qiniu 的 API 模型名）
- `name` = 由模型名美化 + `(Qiniu)`
- `modalities` = 由 Modelink 的 `inputModalities`/`outputModalities` 映射（`file` → `pdf`）
- 已存在且 id 相同 → 不动；id 不同 → 更新

## 注意事项

- **配置不热更新**：写入后必须**完全重启 opencode** 才生效。
- 写入用 `json.dump(indent=2, ensure_ascii=False)`，会重排缩进但不丢字段；配置需是合法 JSON。
  （若配置里有注释，脚本会跳过并提示——改用 JSONC 手改。）
- `--reasoning false`：qiniu 的 `/v1/chat/completions` 不允许「`reasoning_effort` + function tools」同时出现，
  对会触发推理参数的模型（如 `gpt-6-astra`）需要显式关掉。
- 默认只写 `name` / `id` / `modalities`，与其他 qiniu 条目一致；需要更多元数据用
  `--reasoning` / `--with-limits`。
