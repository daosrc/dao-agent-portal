---
name: mihuashi-token
description: 在 Chrome 自动化开发/测试（chrome-devtools MCP、浏览器操作、接口调试）需要米画师登录态时使用。登录凭据已改为 httpOnly cookie `remember_token`，不再存 localStorage；取不到时打开登录页让用户登录。只针对 http://localhost:8080 和 https://test.mihuashi.com。触发词：token、cookie、登录态、remember_token、免登录、注入登录、需要登录、401、403 签名错误、chrome 测试登录。
---

# 米画师登录态获取

**2026-11 变更**：前端不再把 `remember_token` 存 `localStorage`，改为服务端下发的 **httpOnly cookie**。所有读 localStorage 的老办法（包括本 skill 的 `scripts/get-token.mjs`）都已失效，只能当兜底。

## 登录态长什么样

```
Cookie: remember_token=<value>
```

- **httpOnly** → 页面 JS `document.cookie` 读不到，必须走 CDP / DevTools / 用户复制
- 只带 cookie 还不够：`/api/**` 还要签名头 `m-t` + `m-s`，见 `mihuashi-api` skill（缺签名返回 `403 签名错误`，缺登录返回 `401 需登录`）

## 适用范围（只处理这两个 origin）

| Origin | 说明 |
| --- | --- |
| `http://localhost:8080` | 本地开发 |
| `https://test.mihuashi.com` | 测试服 |

其他域名一律不处理。

## 获取顺序（成本从低到高，全程静默）

1. **当前自动化浏览器已登录** → 用 CDP 读 cookie：
   - chrome-devtools MCP：`Network.getAllCookies` / `Storage.getCookies`，筛 `name=remember_token`
   - 其他 CDP 客户端：`Network.getCookies({ urls: [origin] })`
2. **没登录** → 打开登录页 `https://test.mihuashi.com/login`（本地 `http://localhost:8080/login`），**让用户自己登录**，登录完再按第 1 步读。
3. **登录页极验（geetest）报错登不进去** → 直接请用户从自己浏览器复制 cookie（DevTools → Application → Cookies → `remember_token`）。**不要反复重试登录**。
4. **兜底**：本机 Chrome `Cookies` SQLite（`~/Library/Application Support/Google/Chrome/<Profile>/Cookies`）里也有该 cookie，但值被 macOS Keychain 加密，脚本解不开；`scripts/get-token.mjs` 只读 localStorage，现在基本取不到值。不要为拿 cookie 去关用户的 Chrome。

## 注入到其它页签

localStorage 那套 `initScript` 注入对 httpOnly cookie 无效，必须用浏览器级 API：

| 工具 | 做法 |
| --- | --- |
| 同一页签内发请求 | 直接 `fetch('/api/v1/...')`，cookie 自动带、签名自动加（**首选**） |
| Playwright | `context.addCookies([{ name: 'remember_token', value, domain: 'test.mihuashi.com', path: '/', httpOnly: true, secure: true }])` |
| Puppeteer | `page.setCookie({ name: 'remember_token', value, domain: 'test.mihuashi.com', path: '/' })` |
| chrome-devtools MCP | 无写 cookie 工具；改在已登录页签里发请求，或让用户在新页签重新登录 |

## 注意

- 只写 cookie 注入即可，**不要再写 localStorage**；页面已不读它。
- `Authorization: Bearer <remember_token>` 服务端仍兼容，但只在拿不到 cookie 时当备用。
- 不要把 cookie 写进仓库文件、日志、commit 或回复正文。
- 取不到就当作没有登录态，继续正常流程，不要打断用户。
