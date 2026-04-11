# API 路径规范指南

## Django Ninja 路径规则

Django Ninja 的路径规则与标准 REST API 略有不同，必须严格遵守以下规范：

### 基本规则

1. **集合端点（Collection）** - 需要尾部斜杠 `/`
   - 用于列表查询和创建操作
   - 示例：`GET /api/discussions/`, `POST /api/discussions/`

2. **详情端点（Detail）** - 不需要尾部斜杠
   - 用于单个资源的查询、更新、删除
   - 示例：`GET /api/discussions/{id}`, `PATCH /api/discussions/{id}`, `DELETE /api/discussions/{id}`

3. **子资源端点（Sub-resource）** - 不需要尾部斜杠
   - 用于访问资源的子资源
   - 示例：`GET /api/discussions/{id}/posts`, `POST /api/discussions/{id}/posts`

4. **操作端点（Action）** - 不需要尾部斜杠
   - 用于对资源执行特定操作
   - 示例：`POST /api/posts/{id}/like`, `POST /api/discussions/{id}/pin`

## 完整 API 路径列表

### 用户相关
```
POST   /api/users/register          # 注册
POST   /api/users/login             # 登录
POST   /api/users/logout            # 登出
POST   /api/users/verify-email      # 验证邮箱
POST   /api/users/forgot-password   # 忘记密码
POST   /api/users/reset-password    # 重置密码
GET    /api/users/me                # 获取当前用户
GET    /api/users                   # 用户列表（无尾部斜杠）
GET    /api/users/{user_id}         # 获取用户详情
PATCH  /api/users/{user_id}         # 更新用户
POST   /api/users/{user_id}/password # 修改密码
POST   /api/users/{user_id}/avatar  # 上传头像
```

### 讨论相关
```
GET    /api/discussions/            # 讨论列表（有尾部斜杠）
POST   /api/discussions/            # 创建讨论（有尾部斜杠）
GET    /api/discussions/{id}        # 获取讨论详情
PATCH  /api/discussions/{id}        # 更新讨论
DELETE /api/discussions/{id}        # 删除讨论
POST   /api/discussions/{id}/pin    # 切换置顶
POST   /api/discussions/{id}/lock   # 切换锁定
POST   /api/discussions/{id}/hide   # 切换隐藏
POST   /api/discussions/{id}/subscribe # 关注讨论
DELETE /api/discussions/{id}/subscribe # 取消关注讨论
POST   /api/discussions/read-all    # 全部标记为已读
```

### 帖子相关
```
GET    /api/discussions/{id}/posts  # 获取帖子列表
POST   /api/discussions/{id}/posts  # 创建帖子（回复）
GET    /api/posts/{id}              # 获取帖子详情
PATCH  /api/posts/{id}              # 更新帖子
DELETE /api/posts/{id}              # 删除帖子
POST   /api/posts/{id}/like         # 点赞
DELETE /api/posts/{id}/like         # 取消点赞
```

### 标签相关
```
GET    /api/tags                    # 标签列表（无尾部斜杠）
POST   /api/tags                    # 创建标签（无尾部斜杠）
GET    /api/tags/popular            # 热门标签
GET    /api/tags/{id}               # 获取标签详情
PATCH  /api/tags/{id}               # 更新标签
DELETE /api/tags/{id}               # 删除标签
GET    /api/tags/slug/{slug}        # 通过 slug 获取标签
```

### 通知相关
```
GET    /api/notifications           # 通知列表（无尾部斜杠）
GET    /api/notifications/stats     # 通知统计
GET    /api/notifications/{id}      # 获取通知详情
DELETE /api/notifications/{id}      # 删除通知
POST   /api/notifications/{id}/read # 标记为已读
POST   /api/notifications/read-all  # 全部标记为已读
DELETE /api/notifications/read      # 删除所有已读
```

### 搜索相关
```
GET    /api/search                  # 搜索
GET    /api/search/suggestions      # 搜索建议
```

### 管理后台
```
GET    /api/admin/stats             # 统计数据
GET    /api/admin/settings          # 获取设置
POST   /api/admin/settings          # 保存设置
GET    /api/admin/groups            # 用户组列表
POST   /api/admin/groups            # 创建用户组
GET    /api/admin/permissions       # 获取权限
POST   /api/admin/permissions       # 保存权限
GET    /api/admin/users             # 用户管理列表
GET    /api/admin/tags              # 标签管理列表
POST   /api/admin/tags              # 创建标签
PATCH  /api/admin/tags/{id}         # 更新标签
DELETE /api/admin/tags/{id}         # 删除标签
```

## 前端调用示例

### 正确示例 ✅
```javascript
// 集合端点 - 有尾部斜杠
await api.get('/discussions/')
await api.post('/discussions/', data)

// 详情端点 - 无尾部斜杠
await api.get(`/discussions/${id}`)
await api.patch(`/discussions/${id}`, data)
await api.delete(`/discussions/${id}`)

// 子资源端点 - 无尾部斜杠
await api.get(`/discussions/${id}/posts`)
await api.post(`/discussions/${id}/posts`, data)

// 操作端点 - 无尾部斜杠
await api.post(`/posts/${id}/like`)
await api.post(`/discussions/${id}/pin`)
```

### 错误示例 ❌
```javascript
// 错误：详情端点不应有尾部斜杠
await api.get(`/discussions/${id}/`)

// 错误：子资源端点不应有尾部斜杠
await api.get(`/discussions/${id}/posts/`)

// 错误：操作端点不应有尾部斜杠
await api.post(`/posts/${id}/like/`)
```

## 检查清单

在添加新的 API 调用时，请检查：

1. ✅ 是否是集合端点？→ 添加尾部斜杠 `/`
2. ✅ 是否是详情端点？→ 不添加尾部斜杠
3. ✅ 是否是子资源端点？→ 不添加尾部斜杠
4. ✅ 是否是操作端点？→ 不添加尾部斜杠
5. ✅ 测试 API 调用是否返回 404 错误

## 调试技巧

如果遇到 404 错误：

1. 检查路径是否有尾部斜杠
2. 使用 curl 测试：
   ```bash
   curl http://localhost:8000/api/discussions/
   curl http://localhost:8000/api/discussions/1
   ```
3. 查看 Django 错误页面的路由列表
4. 参考本文档的路径列表

## 注意事项

- Django Ninja 的路径规则与 Django REST Framework 不同
- 必须严格遵守上述规则，否则会返回 404 错误
- 所有路径都以 `/api/` 开头
- 前端 API 调用时会自动添加 `/api/` 前缀，所以只需写相对路径
