# PyFlarum 对标 Flarum 开发路线

最后更新：2026-04-11

## 目标

将 `pyflarum` 从“可用的论坛骨架”持续推进到“尽可能接近 Flarum 2.x 官方产品体验的 Python 复刻版本”。

对标基准：
- 本地 Flarum 安装：`D:\files\project\tmp\flarum`
- 官方文档：<https://docs.flarum.org/2.x/>
- 官方社区：<https://discuss.flarum.org/>

本地 Flarum 安装当前启用的官方扩展见 [composer.json](/D:/files/project/tmp/flarum/composer.json#L24)，包括：
- `approval`
- `flags`
- `gdpr`
- `likes`
- `lock`
- `mentions`
- `messages`
- `nicknames`
- `realtime`
- `statistics`
- `sticky`
- `subscriptions`
- `suspend`
- `tags`

## 一、当前评估

### 1. 已有能力

- 前台已具备讨论列表、标签页、讨论详情、创建讨论、用户页、通知页。
- 后端已具备用户、讨论、帖子、标签、通知、搜索、后台基础 API。
- 已支持置顶、锁定、隐藏、点赞、@提及、关注讨论、未读状态、基础通知。
- 已有后台页面框架：Dashboard、Basics、Permissions、Appearance、Users、Tags、Mail、Advanced。
- 已实现基础 WebSocket 通知链路。

### 2. 现阶段定位

`pyflarum` 当前更接近：
- 一个功能基本成型的论坛系统；
- 一个带有 Flarum 风格界面的 Django + Vue 论坛；
- 而不是已经完整达到 Flarum 2.x 产品级复刻。

保守判断：
- 前台完成度：60%-70%
- 后台完成度：40%-50%
- 官方扩展能力覆盖度：30% 左右
- 工程成熟度：中低

## 二、主要差距

### 1. 用户与账号体系差距

- 忘记密码前端缺失，登录页已有入口，但此前无对应页面和路由。
- 重置密码虽有后端接口，但此前未形成完整前端闭环。
- 头像上传接口仍是待实现状态：[apps/users/api.py](/D:/files/project/tmp/pyflarum/apps/users/api.py#L244)
- `AccessToken`、封禁字段存在于模型中，但没有前后台完整闭环：
  - [apps/users/models.py](/D:/files/project/tmp/pyflarum/apps/users/models.py#L39)
  - [apps/users/models.py](/D:/files/project/tmp/pyflarum/apps/users/models.py#L144)
- 用户设置页、账号安全、邮箱验证体验仍较弱。

### 2. 讨论与帖子体验差距

- Flarum 的 Composer、Scrubber、Modal 流程更完整，当前 `pyflarum` 仍有明显差距。
- 讨论页已补 `near` 定位和浮层回复编辑器，但滚动、恢复、移动端细节仍不足。
- 帖子操作仍缺少审核、举报、恢复、更多版主操作。

### 3. 标签与导航差距

- 标签模型和统计已具备，但后台体验仍明显弱于 Flarum Tags 扩展。
- 父子标签、排序、权限联动、可视化管理仍不完整。

### 4. 通知与实时能力差距

- 当前主要是通知 WebSocket，实时帖子流、输入状态、在线状态前台闭环不足。
- WebSocket 前端连接仍存在硬编码环境问题：[frontend/src/stores/notification.js](/D:/files/project/tmp/pyflarum/frontend/src/stores/notification.js#L14)

### 5. 后台差距

- 后台页面已存在，但很多只是“可访问页面”，不是“完整功能模块”。
- 权限页创建/编辑用户组仍是 TODO：
  - [frontend/src/admin/views/PermissionsPage.vue](/D:/files/project/tmp/pyflarum/frontend/src/admin/views/PermissionsPage.vue#L208)
- 用户页编辑仍未实现：
  - [frontend/src/admin/views/UsersPage.vue](/D:/files/project/tmp/pyflarum/frontend/src/admin/views/UsersPage.vue#L147)
- 标签页能 CRUD，但仍缺少 Flarum 式高级管理能力。
- 扩展管理、语言管理、主题管理、扩展 Readme、扩展开关完全缺失。

### 6. 设置与运行时差距

- 后台设置可保存到 `Setting` 表，但很多值尚未驱动真实运行时行为：
  - [apps/core/admin_api.py](/D:/files/project/tmp/pyflarum/apps/core/admin_api.py#L107)
- 基础设置、外观设置、高级设置目前更多是“持久化字段”，不是“即时生效能力”。

### 7. 官方扩展能力差距

未覆盖或只部分覆盖：
- `approval`
- `flags`
- `gdpr`
- `messages`
- `nicknames`
- `realtime`
- `statistics`
- `suspend`

### 8. 工程成熟度差距

- 自动化测试覆盖面仍小，通知测试几乎为空：
  - [apps/notifications/tests.py](/D:/files/project/tmp/pyflarum/apps/notifications/tests.py)
- 功能闭环不一致，存在“后端已有接口但前端没接”的情况。
- 配置、部署、运行时联动仍需要统一整理。

## 三、开发优先级

### P0：闭环缺口修复

优先解决已有后端能力但前台或后台没接上的问题：
- 忘记密码 / 重置密码
- 头像上传
- 用户编辑
- 用户组创建与编辑
- 基础账号安全页

目标：
- 消除明显断链功能；
- 提升产品可用性；
- 为后续深度复刻打稳定地基。

### P1：论坛核心体验对齐

- 继续加强 Composer
- 完善讨论详情页 Scrubber / 滚动状态 / 移动端
- 更接近 Flarum 的 Modal 流程
- 完善搜索结果页与搜索交互

### P2：版主与社区治理能力

- `flags`
- `approval`
- `suspend`

这是从“能发帖的论坛”升级到“能管理社区的论坛”的关键阶段。

### P3：后台产品化

- 扩展管理
- 语言管理
- 主题与样式编译链路
- 更完整的权限网格
- 用户后台与标签后台增强

### P4：实时与高级能力

- 实时帖子流
- 输入中提示
- 在线状态闭环
- 更完整的通知偏好
- 后台统计与趋势图表

### P5：扩展生态对齐

- `messages`
- `gdpr`
- `nicknames`
- 其他官方扩展能力

## 四、建议执行顺序

建议按以下顺序推进：

1. 修复闭环缺口
2. 完善前台主流程
3. 补齐版主管理能力
4. 强化后台产品化能力
5. 完成实时能力与扩展对齐
6. 最后统一做 UI/交互精修与工程加固

## 五、近期任务池

### 已确认优先做

- [x] 忘记密码 / 重置密码前端闭环
- [ ] 后端密码重置邮件发送接入
- [x] 头像上传接口与前端入口
- [ ] 用户后台编辑闭环
- [ ] 用户组创建/编辑闭环

### 第二批建议

- [ ] 封禁用户后台能力
- [ ] 举报帖子
- [ ] 审核队列
- [ ] 设置即时生效链路
- [ ] WebSocket 地址与环境适配

## 六、执行原则

- 不以 README 的“完成度描述”为准，以代码闭环和产品可用性为准。
- 优先做“用户能感知的断点修复”，再做更大的扩展模块。
- 每补一个模块，都要同时补：
  - 前端入口
  - 后端接口
  - 数据模型
  - 最少一条回归测试
- 每阶段结束后重新对照本文件更新状态。
