---
name: mihuashi-api
description: 米画师（Mihuashi）API 接口速查工具。当需要查询米画师接口、定位某个功能对应的接口路径、了解请求参数或数据结构、在测试/正式环境调试接口时使用。触发关键词：接口、API、swagger、接口文档、请求、endpoint、stall、project、user、manuscript、order、hire、workbench、约稿、摊位、稿件、用户、订单。
---

# 米画师 API 速查 Skill

## 环境说明

| 环境 | 域名 | API 文档页面 |
|------|------|-------------|
| **测试服** | `test.mihuashi.com` | `https://test.mihuashi.com/api-doc` |
| **正式服** | `mihuashi.com` | `https://mihuashi.com/api-doc` |

> 两套环境 API 路径完全一致，只需替换域名。下文示例均使用测试服。

---

## 认证方式

```
Authorization: Bearer <remember_token>
```

- `remember_token`：登录令牌，**使用时手动提供，不写入文件**
- `remember_token_expires`：token 过期时间（Unix 毫秒时间戳）
- WebSocket（ActionCable）连接：`/cable?remember_token=<token>`

**获取 token 的接口：**
```
POST /api/v1/authorization_tokens                        # 账号密码登录
PUT  /api/v1/authorization_tokens/{token}/refresh        # 刷新 token
POST /api/v1/authorization_tokens/{token}/exchange       # App token 换 Web token
```

---

## Swagger JSON 端点

| API 组 | Swagger JSON 地址 | 说明 |
|--------|-------------------|------|
| **Site API** | `https://test.mihuashi.com/api/v1/swagger_doc` | 主站，589 条路径 |
| **Admin API** | `https://test.mihuashi.com/api/admin/v1/swagger_doc` | 管理后台，需管理员 token |
| **Activity API** | `https://test.mihuashi.com/api/activity/v1/swagger_doc` | 活动专属 |
| **Wc2 API** | `https://test.mihuashi.com/api/wc2/v1/swagger_doc` | 微信小程序2（画世界） |
| **Wc3 API** | `https://test.mihuashi.com/api/wc3/v1/swagger_doc` | 微信小程序3（画世界3） |

---

## 速查目录

各 API 组的路径速查表已拆分到独立文件：

| 文件 | 内容 |
|------|------|
| `references/site-api-catalog.md` | Site API 速查（13 个业务域） |
| `references/activity-api-catalog.md` | Activity API 全量路径 |
| `references/wc2-api-catalog.md` | Wc2 API 全量路径 |
| `references/wc3-api-catalog.md` | Wc3 API 全量路径 |

---

## 查询脚本

| 脚本 | 用途 | 用法 |
|------|------|------|
| `scripts/search-keyword.sh` | 按关键词搜索接口路径 | `./scripts/search-keyword.sh <keyword> [group]` |
| `scripts/view-endpoint.sh` | 查看某个接口的完整参数结构 | `./scripts/view-endpoint.sh <path> [group]` |

**也可以直接使用内联命令：**

```bash
# 按关键词搜索
scripts/search-keyword.sh stall

# 查看接口参数
scripts/view-endpoint.sh /api/v1/projects

# 或直接使用内联 python3
curl -s https://test.mihuashi.com/api/v1/swagger_doc | python3 -c "
import json, sys
doc = json.load(sys.stdin)
kw = 'stall'
for path, methods in sorted(doc['paths'].items()):
    if kw in path:
        for m, op in methods.items():
            if m in ('get','post','put','patch','delete'):
                print(f'{m.upper():<7} {path}')
                desc = op.get('description','').strip()
                if desc: print(f'        {desc}')
"

# 带认证调试
curl -H "Authorization: Bearer <your_token>" \
     https://test.mihuashi.com/api/v1/users/1
```

---

## Admin API

> **需要管理员 token** 才能访问 Swagger 文档（匿名返回 401）。

```bash
curl -H "Authorization: Bearer <admin_token>" \
     https://test.mihuashi.com/api/admin/v1/swagger_doc | python3 -m json.tool
```

---

## 查询规则（MUST FOLLOW）

> **核心原则：本 skill 的速查目录是静态快照，线上 Swagger 才是权威数据源。**

1. **先在速查目录中查找** — 按功能关键词匹配 `references/*.md` 中的表格
2. **目录查不到或结果不完整时，MUST 实时拉取线上 Swagger JSON 搜索** — 使用 `scripts/search-keyword.sh` 或内联命令
3. **需要看参数字段细节时，MUST 实时拉取** — 使用 `scripts/view-endpoint.sh` 或内联命令
4. **实时查询后，无论成功与否，都必须执行以下反馈逻辑：**
   - **找到了匹配接口** — 完成任务后，将新发现的 API 路径添加到 `references/site-api-catalog.md` 对应业务域的表格中，让后续查询能直接命中
   - **未找到匹配接口** — 向用户提示"未找到精确匹配的接口"，同时自动搜索关键词相关路径，询问用户是否尝试语义相似的接口，并附上相似接口路径供确认

---

## 快速定位流程

```
1. 知道功能关键词？
   → 在 references/*.md 速查目录找对应业务域的 Tag 行
   → 查不到？执行 scripts/search-keyword.sh 或内联命令（自动拉线）
   → 找到匹配接口 → 完成任务后将该接口添加到 references/site-api-catalog.md 对应表格
   → 未找到精确匹配 → 提示用户，并自动搜索关键词相关路径，列出相似接口供用户确认

2. 知道接口路径，想看完整参数？
   → 执行 scripts/view-endpoint.sh 或内联命令（自动拉线）

3. 需要调试？
   → 手动提供 remember_token
   → curl -H "Authorization: Bearer <token>" <url>

4. 不确定在哪个 API 组？
   → Site API    主站功能（用户/约稿/稿件/财务）   /api/v1/
   → Activity API  站内活动（投票/活动作品）        /api/activity/v1/
   → Wc2 API     画世界2 小程序                  /api/wc2/v1/
   → Wc3 API     画世界3 小程序                  /api/wc3/v1/
   → Admin API   后台管理（需管理员权限）           /api/admin/v1/
   → 仍不确定？同时拉取全部 swagger JSON 按关键词搜索
```