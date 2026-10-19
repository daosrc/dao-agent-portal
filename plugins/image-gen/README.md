# Image Gen MCP

通过 Qiniu / Modelink 图片生成模型，将文本描述生成图片并保存到本地磁盘的 MCP 服务器。供 opencode 使用。

## 背景

Qiniu AI（现已改版为 **Modelink**）的图片生成模型可通过 OpenAI 兼容的 `/chat/completions` 接口调用，返回 base64 图片。该脚本包装为标准 stdio MCP Server，输出一个 `image_gen` 工具。

## 架构

```
opencode (stdio MCP) → image-gen-mcp.mjs → Modelink/Qiniu API (/v1/chat/completions)
```

## 前提

- Node.js >= 18
- 有效的 Modelink/Qiniu API Key（控制台创建）

## 安装

### 1. 注册 MCP（在 opencode.json 中）

```json
{
  "mcp": {
    "image-gen": {
      "type": "local",
      "command": [
        "node",
        "/path/to/dao-agent-portal/plugins/image-gen/image-gen-mcp.mjs"
      ],
      "timeout": 120000,
      "enabled": true
    }
  }
}
```

### 2. 重启 opencode

## 可用工具

| 工具 | 说明 |
|------|------|
| `image_gen` | **主工具** — 文本生成图片，保存到本地，返回绝对路径 |

## 参数说明

### image_gen

| 参数 | 必填 | 说明 |
|------|------|------|
| `prompt` | **是** | 图片的详细文本描述 |
| `model` | 否 | 模型 ID，默认 `google/gemini-3.1-flash-image` |
| `outDir` | 否 | 保存目录，默认 `~/Downloads` |
| `filename` | 否 | 文件名（如 `rain.png`），省略则自动生成 |
| `aspectRatio` | 否 | 宽高比，如 `16:9`、`1:1` |

## 环境变量

| 变量 | 说明 |
|------|------|
| `MODELINK_BASE_URL` | Modelink API 地址（优先），如 `https://api.qnaigc.com/v1` 或 `https://api.modelink.ai/v1` |
| `MODELINK_API_KEY` | Modelink API Key（优先） |
| `QINIU_BASE_URL` / `QINIU_API_KEY` | Qiniu 旧名称兜底 |
| `IMAGE_GEN_MODEL` | 默认模型 |
| `IMAGE_GEN_OUT_DIR` | 默认输出目录 |

未设置环境变量时，自动读取 `~/.config/opencode/opencode.json` 中 `provider.qiniu` 的 `baseURL` 与 `apiKey`。

## 接入点说明

Modelink（七牛 AI 新品牌）提供两个接入点，同一把 API Key 均可使用：

| 接入点 | 域名 |
|--------|------|
| 中国大陆 | `https://api.qnaigc.com/v1` |
| 海外/跨境 | `https://api.modelink.ai/v1` |

旧域名 `api.qnaigc.com` 仍可用。

## 使用示例

```text
用 image_gen 生成一张暴风雨夜的窗户图片，保存为 rain.png
```