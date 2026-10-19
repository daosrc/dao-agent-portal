# Site API 速查目录（/api/v1/）

> 共 589 条路径，约 130 个资源 tag，按业务域分组如下。

## 用户 & 认证

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `sessions` | `GET /api/v1/sessions` | 当前登录会话 |
| `users` | `GET/PUT /api/v1/users/{id}` | 用户详情与更新 |
| `users` | `GET /api/v1/users/search` | 搜索用户 |
| `users` | `PUT /api/v1/users/{id}/avatar` | 更新头像 |
| `authorization_tokens` | `POST /api/v1/authorization_tokens` | 登录（获取 token） |
| `accounts` | `PUT /api/v1/accounts/{id}/password` | 修改密码 |
| `accounts` | `PUT /api/v1/accounts/{id}/phone` | 修改手机号 |
| `accounts` | `PUT /api/v1/accounts/{id}/email` | 修改邮箱 |
| `security` | `GET/PUT /api/v1/security/*` | 安全设置 |
| `one_login` | `POST /api/v1/one_login/phone` | 一键登录 |
| `verified_info` | `POST/GET /api/v1/verified_info` | 实名认证 |
| `name_changelogs` | `GET /api/v1/users/{id}/name_changelogs` | 改名记录 |

## 约稿项目

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `projects` | `GET/POST /api/v1/projects` | 项目列表/创建 |
| `projects` | `GET /api/v1/users/{id}/projects?type=created` | 获取用户发布的企划列表 |
| `projects` | `GET /api/v1/users/{id}/projects?type=bided` | 获取用户应征的企划列表 |
| `projects` | `GET /api/v1/projects/search` | 搜索项目 |
| `projects` | `GET /api/v1/projects/{id}` | 项目详情 |
| `applications` | `POST /api/v1/projects/{id}/applications` | 投稿/申请 |
| `applications` | `GET /api/v1/users/{id}/applications` | 用户的申请列表 |
| `applications` | `PUT /api/v1/applications/{id}/state` | 更新申请状态 |
| `invitations` | `GET/DELETE /api/v1/invitations/{id}` | 邀请管理 |
| `invitations` | `POST /api/v1/invitations/{id}/operation` | 处理邀请 |
| `approximation_relationships` | `POST /api/v1/projects/{id}/approximation_relationships` | 近似匹配 |
| `workbenches` | `GET /api/v1/workbenches/{id}` | 工作台详情 |
| `workbenches` | `GET /api/v1/workbenches/{id}/applications` | 工作台申请列表 |
| `recommend_artist_requests` | `GET /api/v1/workbenches/{id}/recommend_artist_request` | 推荐画师请求 |

## 工作关系 & 稿件

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `hire_relationships` | `GET /api/v1/hire_relationships/{id}` | 雇佣关系详情 |
| `hire_relationships` | `PUT /api/v1/hire_relationships/{id}/pay` | 支付 |
| `hire_relationships` | `PUT /api/v1/hire_relationships/{id}/pass` | 通过验收 |
| `work_relationships` | `GET /api/v1/work_relationships/{id}/manuscripts` | 工作关系的稿件 |
| `work_relationships` | `POST /api/v1/work_relationships/{id}/payment_requests` | 发起付款请求 |
| `work_relationships` | `GET /api/v1/work_relationships/{id}/timelines` | 工作时间线 |
| `manuscripts` | `GET/PUT/DELETE /api/v1/manuscripts/{id}` | 稿件 CRUD |
| `manuscripts` | `GET /api/v1/manuscripts/{id}/download` | 下载稿件 |
| `manuscript_folders` | `GET /api/v1/users/{id}/manuscript_folders` | 稿件文件夹 |
| `payment_requests` | `POST /api/v1/payment_requests/{id}/operation` | 处理付款请求 |
| `deadline_change_requests` | `POST /api/v1/work_relationships/{id}/deadline_change_requests` | 申请延期 |
| `disputes` | `POST /api/v1/work_relationships/{id}/dispute` | 发起纠纷 |
| `disputes` | `GET /api/v1/disputes/{id}` | 纠纷详情 |
| `remuneration_change_requests` | `POST /api/v1/work_relationships/{id}/remuneration_change_requests` | 申请改价 |
| `purchase_relationships` | `GET /api/v1/purchase_relationships/{id}` | 购买关系（摊位订单）详情，含 addition_payments |
| `purchase_relationships` | `PUT /api/v1/purchase_relationships/{id}/accept` | 接受订单 |
| `purchase_relationships` | `PUT /api/v1/purchase_relationships/{id}/pass` | 通过节点 |
| `purchase_relationships` | `PUT /api/v1/purchase_relationships/{id}/confirm` | 确认收稿 |
| `purchase_relationships` | `GET /api/v1/purchase_relationships/{id}/snapshot` | 橱窗快照 |

## 摊位（Stall）

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `stalls` | `GET /api/v1/stalls` | 摊位列表（全局搜索） |
| `stalls` | `POST/GET /api/v1/users/{id}/stalls` | 用户摊位 |
| `stalls` | `GET /api/v1/users/{id}/stalls/displayable` | 用户可展示橱窗（公开） |
| `stalls` | `GET /api/v1/stalls/{id}` | 摊位详情 |
| `stalls` | `PUT /api/v1/stalls/{id}/shelf` | 上架摊位 |
| `stalls` | `PUT /api/v1/stalls/{id}/unshelf` | 下架摊位 |
| `stalls` | `GET/PUT /api/v1/users/{id}/stalls/config` | 摊位配置 |
| `stall_orders` | `POST /api/v1/stall_orders` | 下单 |
| `stall_orders` | `GET /api/v1/stall_orders/{id}` | 订单详情 |
| `stall_applications` | `GET /api/v1/users/{id}/stall_application/apply_status` | 摊位申请状态 |
| `stall_activities` | `GET/PUT /api/v1/users/{id}/pet_food` | 宠物喂食活动 |
| `stall_auto_reply_templates` | `GET /api/v1/users/{id}/stall_auto_reply_templates` | 自动回复模板 |
| `stall_topics` | `GET/POST /api/v1/stall_topics` | 摊位话题 |
| `stall_data` | `GET /api/v1/users/{id}/recent_stall_data` | 摊位数据统计 |

## 内容 & 作品

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `artworks` | `GET /api/v1/artworks` | 作品列表 |
| `artworks` | `POST /api/v1/users/{id}/artworks` | 上传作品 |
| `artworks` | `GET /api/v1/artworks/search` | 搜索作品 |
| `artworks` | `GET/PUT/DELETE /api/v1/artworks/{id}` | 作品 CRUD |
| `collections` | `POST/GET /api/v1/users/{id}/collections` | 合集管理 |
| `collections` | `POST/DELETE /api/v1/collections/{id}/items` | 合集内容 |
| `galleries` | `GET /api/v1/galleries/{token}` | 画廊 |
| `character_albums` | `GET /api/v1/users/{id}/character_albums` | OC 角色集 |
| `character_cards` | `GET /api/v1/users/{id}/character_cards` | 角色卡 |
| `character_cards` | `GET /api/v1/character_cards/{id}` | 角色卡详情 |
| `manuscript_praises` | `GET /api/v1/manuscript_praises` | 画廊展示稿件 |
| `oc_showcases` | `GET /api/v1/oc_showcases` | OC 展示橱窗 |
| `oc_showcases` | `POST /api/v1/oc_showcases/{id}/purchase` | 购买 OC 展示 |
| `artwork_rankings` | `GET /api/v1/artwork_rankings` | 作品排行榜 |

## 社交 & 通知

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `comments` | `POST /api/v1/work_relationships/{id}/comments` | 发表评论 |
| `like_relationships` | `POST /api/v1/users/{id}/like_relationships` | 点赞 |
| `subscribe_relationships` | `POST /api/v1/users/{id}/subscribe_relationships` | 关注用户 |
| `favorite_relationships` | `POST /api/v1/users/{id}/favorite_relationships` | 收藏 |
| `notifications` | `GET /api/v1/users/{id}/notifications` | 通知列表 |
| `notifications` | `PUT /api/v1/users/{id}/notifications/readall` | 全部已读 |
| `block_rules` | `POST /api/v1/users/{id}/block_rules` | 拉黑用户 |
| `user_emotions` | `POST /api/v1/users/{id}/user_emotions` | 用户情绪标签 |
| `help_wall_questions` | `GET /api/v1/help_wall_questions` | 求助墙 |
| `help_wall_answers` | `POST /api/v1/help_wall_answers` | 回答求助 |

## 聊天（IM）

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `contact_relationships` | `POST/GET /api/v1/users/{id}/contact_relationships` | 联系人 |
| `contact_relationships` | `GET /api/v1/contact_relationships/{id}/chat_messages` | 聊天记录 |
| `contact_relationships` | `PUT /api/v1/contact_relationships/{id}/chat_messages/readall` | 消息已读 |
| `chat_messages` | `GET /api/v1/chat_messages/search` | 搜索消息 |
| `chat_messages` | `GET /api/v1/chat_messages/asset_overview` | 资产概览 |
| `collect_messages` | `POST/GET /api/v1/users/{id}/collect_messages` | 收藏消息 |
| `chat_groups` | `GET /api/v1/users/{id}/chat_groups` | 聊天分组 |

## 财务 & 支付

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `orders` | `POST /api/v1/users/{id}/orders` | 创建订单 |
| `orders` | `GET /api/v1/orders/{id}` | 订单详情 |
| `fund_records` | `GET /api/v1/users/{id}/fund_records` | 资金流水 |
| `fund_records` | `GET /api/v1/users/{id}/fund_records/export` | 导出流水 |
| `withdraw_records` | `POST /api/v1/users/{id}/withdraw_records` | 申请提现 |
| `withdraw_records` | `GET /api/v1/users/{id}/withdraw_records/income_account_info` | 收款账户信息 |
| `alipay_accounts` | `GET /api/v1/users/{id}/alipay_accounts` | 支付宝账户 |
| `bills` | `GET /api/v1/users/{id}/bill` | 账单 |
| `addition_payments` | `POST /api/v1/addition_payments` | 追加付款 |
| `service_orders` | `GET /api/v1/workbenches/{id}/service_orders` | 服务订单 |
| `deposit` | `GET /api/v1/deposit/style` | 押金配置 |

## 画师相关

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `artists` | `GET /api/v1/artists` | 画师列表 |
| `artists` | `GET /api/v1/artists/search` | 搜索画师 |
| `draw_types` | `GET /api/v1/draw_types/search` | 绘画类型搜索 |
| `draw_types` | `GET /api/v1/users/{user_id}/draw_types` | 用户的绘画类型 |
| `qualification_applications` | `POST /api/v1/users/{id}/qualification_application` | 申请画师资质 |
| `artist_contracts` | `GET /api/v1/artist_contracts/{token}` | 画师合同 |
| `cooperations` | `GET /api/v1/users/{id}/cooperations` | 合作记录 |
| `punishments` | `GET /api/v1/users/{id}/punishments` | 处罚记录 |
| `punishment_appeals` | `POST /api/v1/punishment_appeals` | 申诉 |
| `illegal_reports` | `POST /api/v1/illegal_reports` | 举报 |

## Dashboard & 工作台

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `dashboard` | `GET /api/v1/users/{id}/dashboard/work_relationships` | 工作关系总览 |
| `dashboard` | `GET /api/v1/users/{id}/dashboard/projects` | 项目总览 |
| `dashboard` | `GET /api/v1/users/{id}/dashboard/hire_relationships` | 雇佣关系总览 |
| `dashboard` | `GET /api/v1/users/{id}/dashboard/purchase_relationships` | 购买关系（订单）总览 |
| `dashboard` | `GET /api/v1/users/{id}/dashboard/reminder` | 待办提醒 |
| `deadline_calendar` | `GET /api/v1/users/{id}/deadline_calendar/month` | 月度截止日历 |
| `invite_calendars` | `GET /api/v1/invite_calendars` | 招募日历 |
| `work_schedules` | `GET /api/v1/users/{id}/work_schedules` | 排班表 |
| `todo` | `GET/POST /api/v1/todos` | 待办事项 |

## 制造 & OC 商品

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `manufactures` | `GET /api/v1/manufactures` | 制造商品列表 |
| `manufactures` | `POST /api/v1/manufactures/{id}/purchase` | 购买制造商品 |
| `manufactures` | `PUT /api/v1/manufactures/{id}/shelf` | 上架制造商品 |
| `manufacture_relationships` | `GET /api/v1/manufacture_relationships/{id}` | 制造关系详情 |
| `original_characters` | `GET /api/v1/original_characters` | 原创角色列表 |
| `time_stamp_authentications` | `GET /api/v1/users/{id}/time_stamp_authentications` | 时间戳认证 |

## 配置 & 系统

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `configure` | `GET /api/v1/configure` | 全局配置 |
| `configure` | `GET /api/v1/configure/art_categories` | 美术分类 |
| `configure` | `GET /api/v1/configure/hot_keywords` | 热搜词 |
| `configure` | `GET /api/v1/configure/version` | 版本信息 |
| `banners` | `GET /api/v1/banners` | Banner 列表 |
| `website_terms` | `GET /api/v1/website_terms/{code}` | 服务条款 |
| `guides` | `GET /api/v1/guides` | 引导配置 |
| `uploads` | `POST /api/v1/uploads` | 文件上传 |
| `search` | `GET /api/v1/search` | 全局搜索 |
| `utils` | `GET /api/v1/utils/infos` | 工具信息 |
| `weixin` | `GET /api/v1/weixin/signature` | 微信 JS-SDK 签名 |
| `watermark_stickers` | `GET /api/v1/watermark_stickers` | 水印贴纸 |

## 认证 & 实名

| Tag | 关键路径示例 | 说明 |
|-----|-------------|------|
| `verified_info` | `POST /api/v1/verified_info` | 提交实名认证 |
| `verified_info` | `GET /api/v1/verified_info/token` | 获取认证 token |
| `verified_info` | `GET /api/v1/verified_info/result` | 查询认证结果 |
| `enterprise_authentications` | `POST /api/v1/users/{id}/enterprise_authentication` | 企业认证 |
| `individual_business_registrations` | `POST /api/v1/users/{id}/individual_business_registration` | 个体工商户注册 |
| `vat` | `GET /api/v1/users/{id}/vat/need_accept_vat_declaration` | 增值税申报 |
| `wetax` | `GET /api/v1/users/{id}/wetax/check_agreement` | 汇算清缴协议 |