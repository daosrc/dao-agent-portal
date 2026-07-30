# Figma MCP Bridge

将 Figma Dev Mode MCP Server（SSE 传输）包装为标准 stdio MCP Server，供 opencode 直接使用。

## 原理

```
opencode → figma-mcp-bridge.mjs (stdio MCP Server) → Figma Dev Mode MCP Server (SSE, localhost:3845)
```

Figma Dev Mode MCP Server 使用 **SSE（Server-Sent Events）** 传输协议，opencode 的 MCP 客户端对 SSE 支持有限（`tools/call` 直接 POST 会超时或返回空）。本脚本作为中间层：

1. 通过 stdio 与 opencode 通信（opencode 原生支持的传输方式）
2. 内部维护 Figma MCP 的 SSE session（初始化、session ID 管理、请求/响应配对）
3. 将 opencode 的 `tools/call` 请求转发给 Figma MCP 并等待 SSE 响应后返回

## 前提

- Figma Dev Mode MCP Server 必须在本地运行（通常是 Figma 桌面应用启动的菜单栏服务），监听 `http://127.0.0.1:3845/mcp`
- Node.js >= 18（ESM 模块）

## 安装

### 1. 将脚本放到项目目录

```bash
cp figma-mcp-bridge.mjs ~/dao-agent-portal/plugins/figma/
# 或直接使用当前目录
```

### 2. 在 opencode.json 中注册

在 `mcp` 节点下添加：

```json
{
  "mcp": {
    "figma-bridge": {
      "type": "local",
      "command": [
        "node",
        "/path/to/dao-agent-portal/plugins/figma/figma-mcp-bridge.mjs"
      ],
      "enabled": true
    }
  }
}
```

### 3. 重启 opencode

重启后在会话中即可使用以下工具：

| 工具 | 说明 |
|------|------|
| `get_screenshot` | 获取 Figma 节点的截图（返回 base64 PNG） |
| `get_metadata` | 获取 Figma 节点的 XML 元数据（frame 结构、子节点布局） |
| `get_design_context` | 获取设计上下文（生成代码、设计 token、组件描述），**注意：可能耗时 2-3 分钟** |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `FIGMA_MCP_URL` | `http://127.0.0.1:3845/mcp` | Figma MCP 服务器地址 |

```bash
FIGMA_MCP_URL=http://127.0.0.1:3845/mcp node figma-mcp-bridge.mjs
```

## 使用示例

在 opencode 会话中：

```
用 get_screenshot 获取节点 3860-137451 的截图，文件 key 是 ihdaPKANduMnMVHlyMiERp
用 get_metadata 获取节点布局结构
用 get_design_context 获取设计 token 和生成代码（可加 disable_code_connect: true）
```

## 注意事项

- `get_design_context` 调用 Figma API 生成代码和截图，通常需要 2-3 分钟，请耐心等待
- `get_code_connect_suggestions` 不可用（需要 Figma Org/Enterprise 计划）
- 如果 Figma MCP 服务未运行，脚本启动后会因初始化超时而报错
- 本脚本不处理 Figma 文件认证——认证在 Figma Dev Mode MCP Server 中完成（需在 Figma 桌面应用中登录并打开目标文件）
