# Wc3 API 速查（/api/wc3/v1/）

> 共 106 个接口，20 个 tag。画世界3 微信小程序，增加了宿舍/商店/互动规则等。

## 角色 & 宿舍

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wc3/v1/characters` | 角色列表 |
| GET | `/api/wc3/v1/characters/{id}` | 角色详情 |
| PUT | `/api/wc3/v1/characters/{id}` | 更新角色 |
| GET | `/api/wc3/v1/characters/search` | 搜索角色 |
| GET | `/api/wc3/v1/users/{id}/characters` | 用户所有角色 |
| PUT | `/api/wc3/v1/users/{id}/characters/selection` | 切换当前角色 |
| POST | `/api/wc3/v1/characters/{id}/dorm` | 角色入住宿舍 |
| PUT | `/api/wc3/v1/characters/{id}/dorm` | 更新宿舍 |
| PUT | `/api/wc3/v1/characters/{id}/dorm/move` | 搬家 |
| GET | `/api/wc3/v1/dorms` | 楼层宿舍列表 |
| GET | `/api/wc3/v1/dorms/available_buildings` | 可选公寓楼 |
| GET | `/api/wc3/v1/dorms/random` | 随机空房间 |
| GET | `/api/wc3/v1/dorms/status` | 入住情况统计 |

## 动态 & 社交

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wc3/v1/feeds` | Feed 列表 |
| GET | `/api/wc3/v1/feeds/{id}` | Feed 详情 |
| POST | `/api/wc3/v1/characters/{id}/feeds` | 发布 Feed |
| PUT | `/api/wc3/v1/feeds/{id}` | 更新 Feed |
| DELETE | `/api/wc3/v1/feeds/{id}` | 删除 Feed |
| PUT | `/api/wc3/v1/feeds/{id}/topping` | 置顶 Feed |
| GET | `/api/wc3/v1/feeds/search` | 搜索 Feed |
| POST | `/api/wc3/v1/subscribes` | 关注 |
| DELETE | `/api/wc3/v1/subscribes/{id}` | 取消关注 |
| GET | `/api/wc3/v1/characters/{id}/followers` | 粉丝列表 |
| POST | `/api/wc3/v1/likes` | 点赞 |
| DELETE | `/api/wc3/v1/likes/{id}` | 取消点赞 |
| GET | `/api/wc3/v1/comments` | 评论列表 |
| POST | `/api/wc3/v1/comments` | 发表评论 |
| POST | `/api/wc3/v1/comments/{id}/reply` | 回复评论 |

## 商店 & 家具 & Q版

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wc3/v1/shop_cells` | 寄售商品列表 |
| POST | `/api/wc3/v1/characters/{id}/shop_cells` | 上架商品 |
| POST | `/api/wc3/v1/shop_cells/{id}/purchase` | 购买商品 |
| GET | `/api/wc3/v1/characters/{id}/furnitures` | 角色家具 |
| POST | `/api/wc3/v1/characters/{id}/furnitures` | 创造家具 |
| PUT | `/api/wc3/v1/characters/{id}/furnitures/unlock` | 解锁家具 |
| POST | `/api/wc3/v1/characters/{id}/q_style_avatar` | 创建/更新 Q 版形象 |
| GET | `/api/wc3/v1/characters/{id}/q_style_avatar` | 获取 Q 版形象 |
| POST | `/api/wc3/v1/q_style_materials` | 上传捏人素材 |

## 新闻 & 词条 & 配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wc3/v1/topics` | 新闻列表 |
| GET | `/api/wc3/v1/topics/hot_tags` | 热门 Tag |
| PUT | `/api/wc3/v1/topics/{id}/action` | 参加/退出事件 |
| GET | `/api/wc3/v1/buildings/{id}/entries` | 大楼词条 |
| POST | `/api/wc3/v1/buildings/{id}/entries` | 创建词条 |
| GET | `/api/wc3/v1/configures/buildings` | 大楼配置信息 |
| POST | `/api/wc3/v1/announcements` | 发布公告 |
| GET | `/api/wc3/v1/announcements` | 公告列表 |
| POST | `/api/wc3/v1/characters/{id}/interactive_rule` | 创建/更新互动规则 |
| GET | `/api/wc3/v1/interactive_rules/configure` | 互动规则选项 |
| GET | `/api/wc3/v1/system_messages` | 系统通知 |
| PUT | `/api/wc3/v1/system_messages/read_all` | 系统通知全部已读 |
| GET | `/api/wc3/v1/tags` | 标签列表 |
| GET | `/api/wc3/v1/tags/search` | 搜索标签 |

## 简历

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/wc3/v1/resumes` | 生成简历 |
| GET | `/api/wc3/v1/resumes/current` | 当前简历 |
| PUT | `/api/wc3/v1/resumes/{id}/commit` | 提交简历 |
| GET | `/api/wc3/v1/legacy_characters` | 上期角色 |
| POST | `/api/wc3/v1/legacy_characters/inherit` | 继承上期简历 |