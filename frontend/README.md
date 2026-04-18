# Bias 前端开发指南

Bias 前端基于 Vue 3、Pinia 与 Vite，提供论坛前台与管理后台两个 SPA 入口。

## 技术栈

- Vue 3.4.21 (Composition API)
- Vue Router 4.3.0
- Pinia 2.1.7 (状态管理)
- Vite 5.1.5 (构建工具)
- Axios 1.6.7 (HTTP客户端)

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

访问: http://localhost:5173

### 3. 构建生产版本

```bash
npm run build
```

## 入口说明

- 前台开发入口：`http://localhost:5173`
- 管理后台开发入口：`http://localhost:5173/admin.html`
- 默认后端接口：`http://127.0.0.1:8000/api`

## 项目结构

```
frontend/
├── public/                      # 静态资源
│   └── default-avatar.svg      # 默认头像
├── src/
│   ├── api/                    # API接口
│   │   └── index.js           # Axios配置和拦截器
│   ├── assets/                 # 资源文件
│   ├── components/             # 公共组件
│   │   ├── Header.vue         # 导航栏（带通知徽章）
│   │   └── Footer.vue         # 页脚
│   ├── router/                 # 路由配置
│   │   └── index.js           # 路由定义和守卫
│   ├── stores/                 # Pinia状态管理
│   │   ├── auth.js            # 认证状态
│   │   └── notification.js    # 通知和WebSocket
│   ├── views/                  # 前台页面
│   │   ├── DiscussionListView.vue
│   │   ├── DiscussionDetailView.vue
│   │   ├── DiscussionCreateView.vue
│   │   ├── ProfileView.vue
│   │   └── NotificationView.vue
│   ├── admin/                  # 后台页面与组件
│   ├── App.vue                 # 根组件
│   └── main.js                 # 入口文件
├── index.html
├── package.json
└── vite.config.js
```

## 当前能力

- 讨论列表、讨论详情、浮层 Composer、回复与编辑
- 登录、注册、忘记密码等认证弹窗流程
- 搜索、通知、用户资料、标签筛选
- 后台 Dashboard、Basics、Permissions、Appearance、Users、Tags、Mail、Advanced
- Twemoji 渲染、附件上传、图片上传、@ 提及、Markdown 预览

## API 集成

### HTTP API

```javascript
import api from '@/api'

// 获取讨论列表
const discussions = await api.get('/discussions/')

// 创建讨论
const discussion = await api.post('/discussions/', {
  title: '标题',
  content: '内容'
})
```

### WebSocket

```javascript
import { useNotificationStore } from '@/stores/notification'

const notificationStore = useNotificationStore()

// 连接WebSocket
notificationStore.connect()

// 断开连接
notificationStore.disconnect()

// 标记为已读
notificationStore.markAsRead(notificationId)
```

## 状态管理

### Auth Store

```javascript
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// 登录
await authStore.login(username, password)

// 注册
await authStore.register(username, email, password)

// 登出
authStore.logout()

// 获取当前用户
const user = authStore.user
const isAuthenticated = authStore.isAuthenticated
```

### Notification Store

```javascript
import { useNotificationStore } from '@/stores/notification'

const notificationStore = useNotificationStore()

// 通知列表
const notifications = notificationStore.notifications

// 未读数量
const unreadCount = notificationStore.unreadCount
```

## 路由说明

```javascript
const routes = [
  { path: '/', name: 'home' },
  { path: '/login', name: 'login' }, // 兼容路由，实际打开认证弹窗
  { path: '/register', name: 'register' }, // 兼容路由，实际打开认证弹窗
  { path: '/discussions', name: 'discussions' },
  { path: '/discussions/:id', name: 'discussion-detail' },
  { path: '/discussions/create', name: 'discussion-create', meta: { requiresAuth: true } },
  { path: '/profile', name: 'profile', meta: { requiresAuth: true } },
  { path: '/notifications', name: 'notifications', meta: { requiresAuth: true } }
]
```

## 开发建议

### 1. 组件开发
- 使用Composition API
- 组件尽量保持单一职责
- 使用TypeScript（可选）

### 2. 状态管理
- 全局状态使用Pinia
- 组件内状态使用ref/reactive
- 避免过度使用全局状态

### 3. API调用
- 统一使用api实例
- 错误处理在拦截器中统一处理
- 加载状态管理

### 4. 性能优化
- 路由懒加载
- 组件懒加载
- 图片懒加载
- 虚拟滚动（长列表）

## 环境变量

创建`.env`文件：

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

## 部署

### 构建

```bash
npm run build
```

### Nginx配置

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    root /path/to/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
    }

    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## 常见问题

### 1. CORS错误
确保后端配置了正确的CORS设置：
```python
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
]
```

### 2. WebSocket连接失败
检查：
- `USE_REDIS=False` 的本地模式下会退回进程内 channel layer
- `USE_REDIS=True` 时需确认 Redis 与 Django Channels 配置正常
- WebSocket URL 需与后端地址一致

### 3. Token过期
自动刷新Token或重新登录

## 更多信息

- Vue 3文档: https://vuejs.org/
- Vite文档: https://vitejs.dev/
- Pinia文档: https://pinia.vuejs.org/
