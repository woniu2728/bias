<template>
  <AdminPage
    class-name="DeveloperDocsPage"
    icon="fas fa-book"
    title="开发者文档"
    description="查看模块开发、资源字段、事件订阅、前端注入点、权限注册和后台页面注册指南。"
  >
    <div class="DeveloperDocsPage-layout">
      <aside class="DeveloperDocsPage-sidebar">
        <strong>文档目录</strong>
        <span v-if="moduleId">当前模块：{{ moduleId }}</span>

        <nav class="DeveloperDocsPage-nav">
          <router-link
            v-for="guide in guides"
            :key="guide.key"
            class="DeveloperDocsPage-navItem"
            :class="{ 'is-active': guide.key === activeGuide.key }"
            :to="{ path: '/admin/docs', query: buildGuideQuery(guide.key) }"
          >
            <span>{{ guide.title }}</span>
            <small>{{ guide.description }}</small>
          </router-link>
        </nav>
      </aside>

      <section class="DeveloperDocsPage-content">
        <header class="DeveloperDocsPage-contentHeader">
          <div>
            <h3>{{ activeGuide.title }}</h3>
            <p>{{ activeGuide.description }}</p>
          </div>
          <code>{{ activeGuide.filename }}</code>
        </header>

        <article class="DeveloperDocsPage-markdown" v-html="activeGuideHtml"></article>
      </section>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import { useRoute } from 'vue-router'
import AdminPage from '../components/AdminPage.vue'

const route = useRoute()

const guides = [
  { key: 'module-development', title: '模块开发指南', description: '说明模块定义与主链路接入方式。', filename: 'module-development.md', content: '# 模块开发指南\n\n1. 先确定模块边界，再注册后端扩展、前端入口和资源定义。\n2. 后端能力优先挂到资源、服务和生命周期钩子上，减少页面侧直连。\n3. 前端页面只消费已注册的运行时能力，不直接假设接口存在。' },
  { key: 'resource-fields', title: 'Resource 字段扩展指南', description: '说明 Resource 字段如何注册与消费。', filename: 'resource-fields.md', content: '# Resource 字段扩展指南\n\n1. 字段注册应跟随资源语义，不要把展示逻辑塞进字段 resolver。\n2. 列表、详情和搜索结果可以共享 resolver，但注意预加载与性能。\n3. 对外输出要保持字段稳定，避免前端按临时结构写死。' },
  { key: 'event-subscriptions', title: '事件订阅指南', description: '说明领域事件与监听器接入方式。', filename: 'event-subscriptions.md', content: '# 事件订阅指南\n\n1. 事件订阅只处理领域动作，不做页面跳转或 UI 副作用。\n2. 订阅逻辑要幂等，失败后不能污染主流程。\n3. 对高频事件优先做合并、去重和异步化处理。' },
  { key: 'frontend-injection-points', title: '前端注入点指南', description: '说明 header、动作、状态块等扩展入口。', filename: 'frontend-injection-points.md', content: '# 前端注入点指南\n\n1. 注入点应保持局部职责，不要替代整页路由。\n2. 组件需要兼容无登录、加载中和权限不足三种基础状态。\n3. 交互要和宿主应用的视觉与布局约定保持一致。' },
  { key: 'permission-registration', title: '权限注册指南', description: '说明权限码、别名和依赖关系的注册方式。', filename: 'permission-registration.md', content: '# 权限注册指南\n\n1. 权限码必须全局唯一，命名要稳定。\n2. 后端校验和前端展示应使用同一套权限语义。\n3. 新权限应补齐默认角色、迁移和回归测试。' },
  { key: 'admin-page-registration', title: '后台页面注册指南', description: '说明后台页面如何同时接入后端模块定义与前端路由。', filename: 'admin-page-registration.md', content: '# 后台页面注册指南\n\n1. 后台页面先注册模块，再挂前端路由和权限控制。\n2. 页面入口需要在未登录和权限不足时给出明确退路。\n3. 列表页、详情页和编辑页应共享统一的数据源。' },
  { key: 'platform-delivery', title: '平台交付与性能收尾指南', description: '说明阶段 F 的性能、部署和平台交付检查项。', filename: 'platform-delivery.md', content: '# 平台交付与性能收尾指南\n\n1. 上线前要跑完构建、核心接口和关键页面的回归。\n2. 注意缓存、静态资源版本和反向代理配置。\n3. 先处理启动链路、认证链路和 500 错误，再看体验优化。' },
]

const moduleId = computed(() => String(route.query.module || '').trim())
const activeGuide = computed(() => guides.find(item => item.key === String(route.query.guide || '').trim()) || guides[0])
const activeGuideHtml = computed(() => marked.parse(activeGuide.value.content))

function buildGuideQuery(guide) {
  return {
    guide,
    ...(moduleId.value ? { module: moduleId.value } : {}),
  }
}
</script>

<style scoped>
.DeveloperDocsPage-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 20px;
}

.DeveloperDocsPage-sidebar,
.DeveloperDocsPage-content {
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.DeveloperDocsPage-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  align-self: start;
  position: sticky;
  top: 76px;
}

.DeveloperDocsPage-sidebar span {
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
}

.DeveloperDocsPage-nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.DeveloperDocsPage-navItem {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-radius: var(--forum-radius-sm);
  border: 1px solid var(--forum-border-soft);
  color: var(--forum-text-color);
  text-decoration: none;
}

.DeveloperDocsPage-navItem:hover,
.DeveloperDocsPage-navItem.is-active {
  background: var(--forum-bg-subtle);
  border-color: var(--forum-primary-color);
  text-decoration: none;
}

.DeveloperDocsPage-navItem small {
  color: var(--forum-text-muted);
}

.DeveloperDocsPage-contentHeader {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px 0;
}

.DeveloperDocsPage-contentHeader h3 {
  margin: 0 0 8px;
}

.DeveloperDocsPage-contentHeader p {
  margin: 0;
  color: var(--forum-text-muted);
}

.DeveloperDocsPage-markdown {
  padding: 18px 22px 24px;
  line-height: 1.75;
}

.DeveloperDocsPage-markdown :deep(h1),
.DeveloperDocsPage-markdown :deep(h2),
.DeveloperDocsPage-markdown :deep(h3) {
  margin: 24px 0 12px;
}

.DeveloperDocsPage-markdown :deep(h1:first-child) {
  margin-top: 0;
}

.DeveloperDocsPage-markdown :deep(p),
.DeveloperDocsPage-markdown :deep(ul),
.DeveloperDocsPage-markdown :deep(ol),
.DeveloperDocsPage-markdown :deep(pre) {
  margin: 0 0 14px;
}

.DeveloperDocsPage-markdown :deep(code) {
  padding: 2px 5px;
  border-radius: 4px;
  background: var(--forum-bg-subtle);
}

.DeveloperDocsPage-markdown :deep(pre) {
  padding: 14px 16px;
  overflow-x: auto;
  border-radius: var(--forum-radius-sm);
  background: var(--forum-code-bg);
}

.DeveloperDocsPage-markdown :deep(pre code) {
  padding: 0;
  background: transparent;
}

@media (max-width: 960px) {
  .DeveloperDocsPage-layout {
    grid-template-columns: 1fr;
  }

  .DeveloperDocsPage-sidebar {
    position: static;
  }
}
</style>
