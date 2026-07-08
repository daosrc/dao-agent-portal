# agentmemory 记忆系统

你有 agentmemory 记忆系统可用。按照以下规则使用：

## 自动记录
每次对话中，以下信息请调用 memory_save 主动保存：
- 用户说的重要偏好、配置、决定
- 当前项目的关键架构决策
- 用户明确说"记住"的内容

## 自动检索
每次开始对话时，调用 memory_smart_search 搜索相关记忆：
- 搜索词用当前任务关键关键词
- 如果结果相关，注入到回答中

## 查询记忆
当用户问"还记得吗"、"之前怎么做的"等问题时，调用 memory_smart_search 或 memory_recall 查询。