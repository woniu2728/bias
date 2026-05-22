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

import moduleDevelopmentDoc from '../../../../docs/developer/module-development.md?raw'
import resourceFieldsDoc from '../../../../docs/developer/resource-fields.md?raw'
import eventSubscriptionsDoc from '../../../../docs/developer/event-subscriptions.md?raw'
import frontendInjectionDoc from '../../../../docs/developer/frontend-injection-points.md?raw'
import permissionRegistrationDoc from '../../../../docs/developer/permission-registration.md?raw'
import adminPageRegistrationDoc from '../../../../docs/developer/admin-page-registration.md?raw'
import platformDeliveryDoc from '../../../../docs/developer/platform-delivery.md?raw'

const route = useRoute()

const guides = [
  { key: 'module-development', title: '模块开发指南', description: '说明模块定义与主链路接入方式。', filename: 'module-development.md', content: moduleDevelopmentDoc },
  { key: 'resource-fields', title: 'Resource 字段扩展指南', description: '说明 Resource 字段如何注册与消费。', filename: 'resource-fields.md', content: resourceFieldsDoc },
  { key: 'event-subscriptions', title: '事件订阅指南', description: '说明领域事件与监听器接入方式。', filename: 'event-subscriptions.md', content: eventSubscriptionsDoc },
  { key: 'frontend-injection-points', title: '前端注入点指南', description: '说明 header、动作、状态块等扩展入口。', filename: 'frontend-injection-points.md', content: frontendInjectionDoc },
  { key: 'permission-registration', title: '权限注册指南', description: '说明权限码、别名和依赖关系的注册方式。', filename: 'permission-registration.md', content: permissionRegistrationDoc },
  { key: 'admin-page-registration', title: '后台页面注册指南', description: '说明后台页面如何同时接入后端模块定义与前端路由。', filename: 'admin-page-registration.md', content: adminPageRegistrationDoc },
  { key: 'platform-delivery', title: '平台交付与性能收尾指南', description: '说明阶段 F 的性能、部署和平台交付检查项。', filename: 'platform-delivery.md', content: platformDeliveryDoc },
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
