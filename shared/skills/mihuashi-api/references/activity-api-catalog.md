# Activity API 速查（/api/activity/v1/）

> 共 14 个接口，6 个 tag，围绕站内活动（投票/作品）设计。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/activity/v1/activities` | 获取活动列表 |
| GET | `/api/activity/v1/activities/{activity_name}/session` | 当前用户在活动中的会话 |
| GET | `/api/activity/v1/activities/{activity_name}/artworks` | 活动作品列表 |
| POST | `/api/activity/v1/activities/{activity_name}/artworks` | 提交活动作品 |
| GET | `/api/activity/v1/activities/{activity_name}/artworks/{id}` | 作品详情 |
| PUT | `/api/activity/v1/activities/{activity_name}/artworks/{id}` | 更新活动作品 |
| GET | `/api/activity/v1/activities/{activity_name}/artworks/{id}/comments` | 作品评论 |
| GET | `/api/activity/v1/activities/{activity_name}/users/{id}/artworks` | 用户的活动作品 |
| GET | `/api/activity/v1/activities/{activity_name}/users/{id}/notifications` | 活动通知 |
| PUT | `/api/activity/v1/activities/{activity_name}/users/{id}/notifications/readall` | 通知全部已读 |
| POST | `/api/activity/v1/users/{id}/vote_records` | 投票（已登录） |
| GET | `/api/activity/v1/users/{id}/vote_records/search` | 查询投票记录（已登录） |
| POST | `/api/activity/v1/vote_records` | 投票（未登录） |
| GET | `/api/activity/v1/vote_records/search` | 查询投票记录（未登录） |