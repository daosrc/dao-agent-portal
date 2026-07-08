# Wc2 API 速查（/api/wc2/v1/）

> 共 58 个接口，13 个 tag。画世界2 微信小程序。

## 角色 & 社交

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wc2/v1/characters` | 角色列表 |
| GET | `/api/wc2/v1/characters/{name}` | 角色详情（by name） |
| PUT | `/api/wc2/v1/characters/{id}` | 更新角色 |
| POST | `/api/wc2/v1/characters/{id}/subscribe_relationships` | 关注角色 |
| DELETE | `/api/wc2/v1/characters/{id}/subscribe_relationships/{relationship_id}` | 取消关注 |
| GET | `/api/wc2/v1/characters/{id}/followers` | 角色粉丝 |
| GET | `/api/wc2/v1/characters/{id}/followings` | 角色关注列表 |
| GET | `/api/wc2/v1/users/{id}/characters` | 用户所有角色 |
| PUT | `/api/wc2/v1/users/{id}/characters/selection` | 切换当前角色 |

## 动态 & 故事线

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wc2/v1/feeds` | Feed 列表 |
| GET | `/api/wc2/v1/feeds/{id}` | Feed 详情 |
| POST | `/api/wc2/v1/characters/{id}/feeds` | 发布 Feed |
| POST | `/api/wc2/v1/feeds/{id}/repost` | 转发 Feed |
| GET | `/api/wc2/v1/users/{id}/feeds` | 关注人的 Feed |
| GET | `/api/wc2/v1/stories` | 故事线列表 |
| GET | `/api/wc2/v1/stories/{id}/feeds` | 故事线的动态 |
| POST | `/api/wc2/v1/stories/{id}/feeds/addition` | 将动态收录到故事线 |

## 新闻 & 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wc2/v1/topics` | 新闻列表 |
| GET | `/api/wc2/v1/topics/{id}` | 新闻详情 |
| POST | `/api/wc2/v1/topics/{id}/participants` | 参与新闻事件 |
| GET | `/api/wc2/v1/buildings` | 大楼列表 |
| GET | `/api/wc2/v1/map_characters` | 地图角色分布 |
| GET | `/api/wc2/v1/weather` | 天气 |
| GET | `/api/wc2/v1/winners` | 获奖列表 |
| GET | `/api/wc2/v1/session` | 当前会话 |
| POST | `/api/wc2/v1/resumes` | 生成简历 |
| PUT | `/api/wc2/v1/resumes/{id}` | 更新简历 |
| GET | `/api/wc2/v1/tags/hotest` | 热门标签 |