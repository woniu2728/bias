# PyFlarum 与 Flarum 对比缺口

对比基准：`D:\files\project\tmp\flarum`，核心版本来自 `composer.json` 的 `flarum/core:^2.0.0-beta.8`，并启用了 approval、flags、gdpr、likes、lock、mentions、messages、nicknames、realtime、statistics、sticky、subscriptions、suspend、tags 等官方扩展。

## 已覆盖较好的部分

- 讨论、帖子、用户、标签、通知的基础模型和 API 已经存在。
- 讨论列表、详情、创建讨论、标签页、用户页、通知页已有 Vue 页面。
- 已支持置顶、锁定、隐藏、点赞、关注讨论、关注流、未读状态和基础通知偏好。
- 管理后台已有 Dashboard、Basics、Permissions、Appearance、Users、Tags、Mail、Advanced 的页面框架。
- 顶栏搜索已支持 Flarum 式讨论、帖子、用户三类结果下拉和键盘选择。
- 基础、外观、邮件、高级设置已接入 `Setting` 表持久化，并补齐缓存清理和测试邮件接口。
- 讨论详情已支持 `near` 楼层定位、帖子页前后加载、基础帖子导航、滚动进度同步、地址栏历史状态更新和可最小化浮层回复 Composer。

## 前台与交互缺口

- Flarum 使用浮层 Composer（发帖、回复、编辑可最小化/恢复），pyflarum 仍是独立发帖页和详情页内 textarea。
- Flarum 讨论页有更完整的 PostStreamScrubber 和 Composer 状态管理；pyflarum 已补基础 `near` 定位、帖子导航、滚动历史状态和浮层回复 Composer，但还需要继续精细化。
- Flarum 的登录、注册、忘记密码、改邮箱、改密码、头像编辑是 Modal 交互；pyflarum 多数是独立页面或未实现上传。
- Flarum 用户页有 Discussions、Posts、安全/Access Tokens、设置页等细分；pyflarum 用户页覆盖较少。
- Flarum 移动端有抽屉式导航、滑动操作和更完整的 responsive 行为；pyflarum 只有基础响应式布局。
- Flarum 帖子操作菜单包含重命名讨论、审核、举报、软删除/恢复等扩展项；pyflarum 目前只有基础编辑、删除、点赞、回复。

## 管理后台缺口

- Flarum 后台有 ExtensionPage、ExtensionsWidget、扩展启停、Readme、扩展权限面板；pyflarum 没有扩展管理模型和 UI。
- Flarum 后台有全局搜索、状态/公告组件、会话菜单、GroupBar 和更完整的 PermissionGrid；pyflarum 后台页面更接近静态表单。
- pyflarum 的设置持久化已接入基础能力，但仍需要更完整的字段校验、运行时配置生效和审计日志。
- Flarum tags 后台有拖拽排序、父子标签、颜色/图标选择、权限范围联动；pyflarum Tags 后台仍需要补齐细节体验。
- Flarum 用户后台包含创建用户弹窗、编辑用户、组管理和更细粒度筛选；pyflarum 用户后台仅覆盖基础列表/管理。

## 官方扩展功能缺口

- approval：待审核内容、审核队列、未审核徽标。
- flags：举报帖子、举报列表、处理状态、版主通知。
- gdpr：数据导出、删除账号、隐私相关流程。
- messages：私信会话、消息流、输入中提示、私信通知。
- nicknames：昵称与用户名分离的完整显示/搜索/校验。
- suspend：用户封禁后台、封禁提示和权限联动。
- realtime：实时讨论/帖子/通知更新；pyflarum 目前只有通知 WebSocket 基础能力。
- statistics：后台统计扩展更完整；pyflarum 只有总量统计。

## 搜索差距与本次处理

- Flarum 后端搜索会按数据库驱动选择 SQLite LIKE、MySQL/MariaDB fulltext、PostgreSQL tsvector，并搜索讨论标题和帖子内容。
- pyflarum 原先只做 `icontains`，讨论列表只查标题和 slug，不搜首帖/回复内容。
- 本次已加入 `jieba` 依赖，并在搜索服务中优先使用 jieba 的中文搜索分词，未安装时降级到内置 CJK 二元切分。
- 本次已将讨论列表 `q` 过滤接到同一套中文搜索逻辑，可通过标题、slug、首帖/回复内容命中讨论。
- 本次已将顶栏搜索改为多源下拉，展示讨论、帖子、用户三类结果并支持键盘选择。

## 建议下一步

- 第一优先级：继续精细化讨论详情 PostStream，补更完整的移动端浏览体验和 Composer 草稿持久化。
- 第二优先级：补充后台全局搜索、扩展管理页框架和更完整的 PermissionGrid。
- 第三优先级：实现 flags/approval/suspend 这三类版主管理能力，先覆盖后台和帖子操作菜单。
- 第四优先级：继续完善设置校验、运行时配置生效和审计日志。
