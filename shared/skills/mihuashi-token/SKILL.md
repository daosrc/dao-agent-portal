---
name: mihuashi-token
description: 在 Chrome 自动化开发/测试（chrome-devtools MCP、浏览器操作、接口调试）遇到需要登录 token 时，静默从本机 Chrome 的 Local Storage 取出米画师登录态并写入新开的浏览器页签。只针对 http://localhost:8080 和 https://test.mihuashi.com 两个地址。触发词：token、登录态、remember_token、免登录、注入登录、需要登录、401、未登录、chrome 测试登录。
---

# 米画师测试环境 Token 自动注入

用途：用 Chrome 做自动化开发/测试时，新开的浏览器是无登录态的。这个 skill 从**本机已经登录过的 Chrome** 里读出 `remember_token`，直接注入到当前自动化页签，避免手动登录。

**全程静默**：不打印 token 原文、不询问用户、不打开可视化页面。取不到就当作没有登录态，直接继续后续流程。

## 适用范围（只处理这两个 origin）

| Origin | 说明 |
| --- | --- |
| `http://localhost:8080` | 本地开发 |
| `https://test.mihuashi.com` | 测试服 |

其他域名一律不处理。

## 数据来源

本机 Chrome / Chrome Beta / Canary / Chromium / Edge 的 profile 目录下的
`Local Storage/leveldb/*.ldb`、`*.log`，键为：

```
_<origin>\x00<enc>remember_token            → 值
_<origin>\x00<enc>remember_token_expires    → 毫秒时间戳
```

直接读文件，**不需要** Chrome 以 `--remote-debugging-port` 启动，也不修改任何文件。

取值规则：

- 同一个 profile 内同一个键有多条历史记录时，取 sequence 最新的一条。
- 多个 profile 都有值时，按 Chrome → Chrome Beta → Canary → Chromium → Edge → Arc → `chrome-devtools-mcp` 自建 profile 的顺序，优先取**未过期**的那个；全都过期才回退到第一个并标记 `expired`。

## 脚本

`scripts/get-token.mjs`（Node，无第三方依赖，退出码恒为 0）。下面 `$S` 是本 skill 目录下的脚本路径：

```bash
S=<本 skill 目录>/scripts/get-token.mjs
# 本机实际路径：
#   ~/dao-agent-portal/shared/skills/mihuashi-token/scripts/get-token.mjs
# 若 ~/.claude/skills 已软链到 shared/skills：
#   ~/.claude/skills/mihuashi-token/scripts/get-token.mjs

node $S                                     # 两个 origin 都查，输出 JSON
node $S --origin http://localhost:8080      # 只查一个
node $S --field token --origin <origin>     # 只输出 token 字符串（取不到输出空行）
node $S --field expires --origin <origin>   # 只输出过期时间
node $S --eval  --origin <origin>           # 输出箭头函数，给 evaluate_script
node $S --init  --origin <origin>           # 输出裸语句，给 navigate_page 的 initScript
```

JSON 输出示例：

```json
{
  "found": true,
  "tokens": {
    "http://localhost:8080": {
      "found": true,
      "token": "...",
      "expires": 1790000000000,
      "expired": false,
      "usable": true,
      "source": "Chrome/Default"
    }
  }
}
```

- `found:false` + `reason:"expired"`：token 存在但已过期，视为不可用。
- 加 `--include-expired` 可以强制拿到过期值（一般不要用）。

## 标准流程

1. **先看目标 origin** 是不是那两个之一。不是 → 跳过整个 skill。

2. **读取 token**（静默，不要展示内容）：
   ```bash
   node $S --field token --origin <origin>
   ```
   输出为空 → 没有可用登录态，**直接继续正常流程**（该登录就登录，该报错就报错），不要中断、不要追问。

3. **注入**，按页签是否已存在选一种：

   - **页签还没建**（推荐，一次到位，不闪登录页）：
     1. 先取 initScript：`node $S --init --origin <origin>`
     2. `new_page({ url: "about:blank", background: true })`
     3. `navigate_page({ pageId, type: "url", url: "<origin>", initScript: "<上一步输出>" })`
     4. `evaluate_script` 确认 `location.pathname` 不是登录页即可。

   - **页签已经打开**（已在目标 origin 上）：
     1. 取注入函数：`node $S --eval --origin <origin>`
     2. `evaluate_script({ pageId, function: "<上一步输出>", waitForStableDom: false })`
     3. `navigate_page({ pageId, type: "reload" })` 让前端读到新登录态。

4. **验证只做静默判断**：看 `location.pathname`、`document.title` 是否还是登录页，或用 `evaluate_script` 读 `localStorage.getItem('remember_token')` 是否为真值。**不要把 token 原文写进回复**，只说「已注入 / 无可用登录态」。

5. **失败即降级**：任何一步报错（脚本报错、origin 不匹配、注入后仍跳登录页），都当作无 token 处理，继续原任务，最多在心里记一句，不打断用户。

## 其他浏览器工具

不限于 chrome-devtools MCP。任何能执行 JS 的自动化方式（browser-act、agent-browser、Playwright 的 `page.addInitScript` 等）都可以：

- 能设「导航前脚本」的 → 用 `--init` 的输出。
- 只能导航后执行 JS 的 → 导航到目标 origin 后执行 `--eval` 的输出，再 reload 一次。

## 兜底（磁盘读不到时）

如果脚本返回 `found:false`，但当前 MCP 里**已经有该 origin 的页签且已登录**，可以直接从页面里取：

```js
() => ({ token: localStorage.getItem('remember_token'), expires: localStorage.getItem('remember_token_expires') })
```

取到后按上面的方式注入到新页签。仍取不到 → 继续后续流程。

## 注意

- 只写 `localStorage`，不动 cookie；前端读取的是 localStorage 里的 `remember_token`。
- 如果目标是需要 cookie 的接口，token 只够 `Authorization: Bearer <token>` 用。
- 不要把 token 落到仓库文件、日志、commit 或回复正文里。
- 不要为了拿 token 去关闭用户正在用的 Chrome；读文件不需要。
