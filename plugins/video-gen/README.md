# Video Gen MCP

通过 Modelink（七牛 AI 新品牌）视频生成模型，将文本描述（或参考图/参考视频）生成视频并保存到本地磁盘的 MCP 服务器。供 opencode 使用。

## 背景

Modelink 的视频生成有两种后端协议，本脚本**按模型 ID 自动分流**：

| 后端 | 模型 | 接口 | 认证 | 说明 |
|------|------|------|------|------|
| **Seedance**（豆包/即梦） | `bytedance/doubao-seedance-2-0-mini-260615`（**默认**）、`doubao-seedance-2.0`、`doubao-seedance-2.5`、`byteplus/dreamina-seedance-2-5-260628` | `POST /queue/bytedance/seedance-{2.5\|2.0\|2.0/mini}/{text\|image\|reference}-to-video` | `Authorization: Key {key}` | **Fal 队列**，路径不带 `/v1`；变体与路由按模型 ID + 输入自动选择 |
| **Kling / Sora** | `kling-video-o1`、`kling-v2-1`、`kling-v2-5-turbo`、`sora-*` | `POST /videos` + `GET /videos/:id` | `Authorization: Bearer {key}` | OpenAI Videos API 风格，路径带 `/v1` |

两种后端都是**异步任务**：提交后拿到任务 ID，轮询直到完成，再下载视频（远程 URL 有效 7 天）。脚本自动完成「提交 → 轮询 → 下载」，输出一个 `video_gen` 工具。

## 架构

```
opencode (stdio MCP) → video-gen-mcp.mjs ──┬─ Seedance: POST /queue/bytedance/seedance-2.0/mini/{text|image|reference}-to-video
                                            │            GET  创建响应里的 status_url（轮询）
                                            └─ Kling:    POST /videos
                                                         GET  /videos/:id + 下载 MP4
```

## 前提

- Node.js >= 18
- 有效的 Modelink/Qiniu API Key（控制台创建）

## 安装

### 1. 注册 MCP（在 opencode.json 中）

```json
{
  "mcp": {
    "video-gen": {
      "type": "local",
      "command": [
        "node",
        "/path/to/dao-agent-portal/plugins/video-gen/video-gen-mcp.mjs"
      ],
      "timeout": 900000,
      "enabled": true
    }
  }
}
```

### 2. 重启 opencode

## 可用工具

| 工具 | 说明 |
|------|------|
| `video_gen` | **主工具** — 文本生成视频（或图生视频/视频生视频），轮询到完成并下载 MP4，返回绝对路径 |

## 支持的模型

### Seedance 系列（Fal 队列，`Key` 认证）

模型 ID 决定**队列变体**，输入参数决定**路由**（文生 / 图生 / 多模态参考生）：

| 变体 | 匹配的模型 ID | 队列路径 | 分辨率 | 时长 |
|------|---------------|----------|--------|------|
| **2.0 Mini**（默认） | `bytedance/doubao-seedance-2-0-mini-260615`、`doubao-seedance-2.0-mini` | `/queue/bytedance/seedance-2.0/mini` | `480p`/`720p`（默认 `720p`） | 4–15s |
| 2.0 Fast | `doubao-seedance-2.0-fast` | `/queue/bytedance/seedance-2.0/fast` | `480p`/`720p` | 4–15s |
| 2.0 | `doubao-seedance-2.0` | `/queue/bytedance/seedance-2.0` | `480p`/`720p`/`1080p`/`4k` | 4–15s |
| 2.5 | `doubao-seedance-2.5`、`bytedance/doubao-seedance-2-5-260628`、`byteplus/dreamina-seedance-2-5-260628` | `/queue/bytedance/seedance-2.5` | `480p`/`720p`/`1080p`（不支持 `4k`） | 4–30s |

> 上表的分辨率/时长上限取自 Modelink OpenAPI 规范（`docs.modelink.ai/openapi.json`）。

路由（`seedanceMode` 为 `auto` 时自动判定，也可显式指定）：

| 路由 | 触发条件 | 请求体关键字段 |
|------|----------|----------------|
| `text-to-video` | 无 `imageUrls`/`videoUrls` | `prompt` |
| `image-to-video` | 1 张图（首帧），或 2 张图（首帧 + 末帧） | `image_url`、`end_image_url` |
| `reference-to-video` | ≥3 张图，或任意 `videoUrls` | `image_urls`（≤9）、`video_urls`（≤3） |

> 超出模型范围的分辨率/时长会自动收敛（如 mini 传 `1080p` → `720p`，传 `30` 秒 → `15` 秒）。
> 注意 Fal 队列在任务失败时**同样返回 `COMPLETED`**，真正原因在 `detail` 字段，脚本已据此抛错而不是当成成功下载。

### Kling / Sora 系列（OpenAI 风格，Bearer 认证）

| 模型 ID | 说明 |
|---------|------|
| `kling-video-o1` | 可灵 O1，支持文生/图生/视频生/首尾帧全功能 |
| `kling-v2-1` | 图生视频及首尾帧（不支持文生） |
| `kling-v2-5-turbo` | 全功能，性价比高 |
| `sora-*` | OpenAI Sora 系列 |

## 参数说明

### video_gen

| 参数 | 必填 | 适用 | 说明 |
|------|------|------|------|
| `prompt` | **是** | 全部 | 视频详细描述（场景、动作、风格、光线、氛围），≤2500 字符 |
| `model` | 否 | 全部 | 模型 ID，默认 `bytedance/doubao-seedance-2-0-mini-260615`；传 seedance 相关 ID 自动切 Fal 队列 |
| `seconds` | 否 | 全部 | 时长（字符串秒）。Kling：`5`/`10`；Seedance：`4`–`15`（Mini / Fast / 2.0）/ `4`–`30`（2.5），或 `auto`。越界自动收敛 |
| `size` | 否 | 全部 | 分辨率 `宽x高`，如 `1920x1080`、`1280x720`。按**短边**映射为 resolution，并推导 aspect_ratio |
| `resolution` | 否 | Seedance | `480p`/`720p`（Mini、Fast）、`480p`/`720p`/`1080p`（2.5）、`480p`/`720p`/`1080p`/`4k`（2.0）。覆盖 size 推导值 |
| `aspectRatio` | 否 | Seedance | `21:9`/`16:9`/`4:3`/`1:1`/`3:4`/`9:16`。覆盖 size 推导值 |
| `seedanceMode` | 否 | Seedance | `auto`（默认）/ `text-to-video` / `image-to-video` / `reference-to-video`。显式指定路由，用于消解「2 张图是首尾帧还是两张参考」的歧义 |
| `mode` | 否 | Kling | `std`（720P）/ `pro`（1080P），默认 `std`。Seedance 忽略 |
| `generateAudio` | 否 | Seedance | 是否生成同步音频 |
| `imageUrls` | 否 | 全部 | 参考图（URL 或原始 base64）。Seedance：1 张 = 首帧，2 张 = 首帧 + 末帧，≥3 张 = 多模态参考（≤9） |
| `videoUrls` | 否 | 全部 | 参考视频 URL（MP4/MOV）。Seedance：切换到多模态参考（≤3） |
| `outDir` | 否 | 全部 | 保存目录，默认 `~/Downloads` |
| `filename` | 否 | 全部 | 文件名（如 `cicada.mp4`），省略则自动生成 |
| `pollIntervalMs` | 否 | 全部 | 轮询间隔，默认 `10000` ms |
| `pollTimeoutMs` | 否 | 全部 | 最长等待，默认 `900000`（15 min） |

## 环境变量

| 变量 | 说明 |
|------|------|
| `MODELINK_BASE_URL` | Modelink API 地址（优先），如 `https://api.qnaigc.com/v1` 或 `https://api.modelink.ai/v1` |
| `MODELINK_API_KEY` | Modelink API Key（优先） |
| `QINIU_BASE_URL` / `QINIU_API_KEY` | Qiniu 旧名称兜底 |
| `VIDEO_GEN_MODEL` | 默认模型（未设置时为 `bytedance/doubao-seedance-2-0-mini-260615`） |
| `VIDEO_GEN_OUT_DIR` | 默认输出目录 |

未设置环境变量时，自动读取 `~/.config/opencode/opencode.json` 中 `provider.qiniu` 的 `baseURL` 与 `apiKey`。

## 接入点说明

| 接入点 | 域名 | 说明 |
|--------|------|------|
| 中国大陆 | `https://api.qnaigc.com/v1` | 兼容 OpenAI `/v1` 前缀 |
| 海外/跨境 | `https://api.modelink.ai/v1` | 兼容 OpenAI `/v1` 前缀 |
| 混合兼容 | `https://xapi.qnaigc.com` | 多协议识别 |

> 注意：Seedance 的 Fal 队列路径在**根域名**下（不带 `/v1`），脚本已自动剥离 baseURL 的 `/v1` 后缀，无需手动处理。

## 使用示例

```text
用 video_gen 生成一段夏日午后窗外大树上蝉鸣的视频，保存为 summer_cicada.mp4
用 video_gen 生成一段海边日落延时视频，720p、5 秒（不传 model，默认走 Seedance 2.0 Mini）
用 video_gen 生成一段夏天下雨天的视频，用 doubao-seedance-2.5 模型，720p，6 秒
用 video_gen 拿这两张图做首尾帧，生成一段镜头推进的视频（传 2 个 imageUrls）
```

## 常见问题

### 传 seedance 模型报 400「model must start with 'sora' or 'kling'」

这是把 seedance 模型误发到了 `/videos` 接口（该接口只认 `sora`/`kling` 前缀）。Seedance 必须走 Fal 队列接口。确认 `model` 参数含 `seedance`/`dreamina` 关键字（如 `bytedance/doubao-seedance-2-0-mini-260615`），脚本会自动分流。

### 传 seedance 模型报 400「unsupported model: xxx」

模型 ID 里的版本号无法映射到已知队列变体（`2.0/mini`、`2.0`、`2.5`）时，会落到 2.5。若出现该报错，说明版本号写法超出了脚本的识别范围；查看返回文案里的 `Seedance xxx job created` 确认实际使用的变体，必要时把 `model` 换成上表中的标准模型 ID。

### 传 `size` 但出片分辨率不符合预期

`size` 按**短边**判定分辨率级别（`1280x720` → `720p`，`1920x1080` → `1080p`，`1080x1080` → `1080p`），再收敛到模型支持的档位；低一档的模型（如 Mini）会把 `1080p`/`4k` 降到 `720p`。

### 传 seedance 模型报 404「not found or method not allowed」

baseURL 带了 `/v1` 前缀，而 Fal 队列路径在根域名下。脚本已通过 `ROOT_BASE` 自动剥离，若仍报错请检查 `MODELINK_BASE_URL` 是否异常。

### 认证报 401

Seedance 使用 `Authorization: Key {key}`（非 Bearer），Kling 使用 `Authorization: Bearer {key}`。脚本已按后端自动区分。
