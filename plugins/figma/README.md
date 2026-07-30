# Figma MCP Bridge

将 Figma Desktop MCP Server（Streamable HTTP）包装为标准 stdio MCP Server，供 opencode 使用。

## 背景

Figma 提供两种 MCP Server：

| 方式 | 地址 | 认证 | 写 canvas | 适用场景 |
|------|------|------|-----------|----------|
| **Remote MCP** | `https://mcp.figma.com/mcp` | OAuth（客户端白名单） | ✅ | 推荐方式，但 opencode 未在白名单中 |
| **Desktop MCP** | `http://127.0.0.1:3845/mcp` | 桌面应用本地鉴权 | ❌ | 仅读操作，opencode 可用 |

Remote MCP 需要客户端在白名单内（VS Code、Cursor、Claude Code 等），opencode 暂不支持。因此使用 **Desktop MCP + 桥接** 方案实现读取设计。

## 架构

```
opencode (stdio MCP) → figma-mcp-bridge.mjs → Figma Desktop MCP (HTTP, localhost:3845)
```

桥接脚本将 opencode 的 stdio 协议转为对 Figma Desktop MCP 的 HTTP 请求。

## 前提

- Figma Desktop 应用已运行，打开了一个设计文件
- Dev Mode 中已启用 **MCP server**（底栏 → Dev Mode → 右侧 Inspect panel → MCP server → Enable）
- Image source 建议设为 **Local server**（不需写磁盘，零配置）
- Node.js >= 18

## 安装

### 1. 放置桥接脚本

```bash
cp figma-mcp-bridge.mjs ~/dao-agent-portal/plugins/figma/
```

### 2. 在 opencode.json 中注册

```json
{
  "mcp": {
    "figma": {
      "type": "local",
      "command": [
        "node",
        "/path/to/dao-agent-portal/plugins/figma/figma-mcp-bridge.mjs"
      ],
      "timeout": 30000,
      "enabled": true
    }
  }
}
```

### 3. 重启 opencode

## 可用工具

| 工具 | 说明 |
|------|------|
| `get_design_context` | **主工具** — 获取节点设计上下文，返回生成代码 + 设计 token + 组件说明。耗时约 2-3 分钟 |
| `get_metadata` | 获取节点 XML 结构树（frame 层级、子节点、位置、尺寸） |
| `get_variable_defs` | 获取节点用到的设计变量（颜色 tokens、字体样式、行高、间距） |
| `get_screenshot` | 获取节点截图（base64 PNG） |
| `get_motion_context` | 获取节点动画关键帧数据 |
| `get_figjam` | 为 FigJam 节点生成 UI 代码 |

## 运行设置

在 Figma Desktop Dev Mode 的 MCP server settings 中：

| 设置 | 说明 |
|------|------|
| **Image source → Local server** | 图片由 Figma 本地 HTTP 服务托管（`http://localhost:3845/assets/xxx.svg`），无需写磁盘 |
| **Image source → Download** | 图片下载到本地文件夹，需先添加允许目录 |
| **Allowed directories** | 仅在 Download 模式下需要，Figma 限制了可写入的目录 |
| **Enable Code Connect** | 启用后生成代码会匹配代码库组件（需配置 Code Connect） |

**建议使用 Local server 模式**，更简洁。

## 使用示例

```text
用 get_design_context 获取节点 49522:656900 的设计信息
用 get_screenshot 查看当前选中节点的截图
用 get_metadata 查看节点 49522:656900 的布局结构
用 get_variable_defs 查看该节点的设计变量
```

## 参数说明

### get_design_context

| 参数 | 必填 | 说明 |
|------|------|------|
| `nodeId` | 推荐 | 节点 ID，格式 `123:456`。不传则使用当前选中 |
| `clientLanguages` | 推荐 | 目标语言，如 `html,css` |
| `clientFrameworks` | 推荐 | 目标框架，如 `vue`、`react` |
| `dirForAssetWrites` | Download 模式必填 | 图片下载目录，需在允许目录列表中 |
| `artifactType` | 可选 | 制品类型，如 `COMPONENT_WITHIN_A_WEB_PAGE_OR_APP_SCREEN` |
| `skillNames` | 可选 | 技能名称，如 `figma-design-to-code` |

## 常见问题

### get_design_context 返回 "Cannot write to this directory"

Image source 为 **Download** 模式时，传入的 `dirForAssetWrites` 目录需先在 Figma Dev Mode MCP settings 的 Allowed directories 中添加。建议切到 **Local server** 模式，无需此参数。

### Remote MCP 认证失败

opencode 不在 Figma Remote MCP 的 OAuth 客户端白名单内，会返回 `403 Forbidden`。需要等待 Figma 开放第三方客户端注册，或改用白名单内的工具（VS Code、Cursor 等）。

### get_design_context 返回 "Components missing Code Connect mappings"

设计中的组件未配置 Code Connect。如果不需要，在调用时忽略即可。如果需要配置，请使用远程 MCP 的白名单客户端。

### get_code_connect_suggestions 不可用

该工具仅远程 MCP 提供，Desktop MCP 不支持。

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FIGMA_MCP_URL` | `http://127.0.0.1:3845/mcp` | Figma MCP 服务器地址 |

```bash
FIGMA_MCP_URL=http://127.0.0.1:3845/mcp node figma-mcp-bridge.mjs
```
