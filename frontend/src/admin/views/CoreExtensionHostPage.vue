<template>
  <section class="CoreExtensionHost">
    <header class="CoreExtensionHost-hero">
      <p class="CoreExtensionHost-kicker">Core Admin Surface</p>
      <h2>{{ heroTitle }}</h2>
      <p>{{ heroDescription }}</p>
    </header>

    <div class="CoreExtensionHost-grid">
      <article
        v-for="card in cards"
        :key="card.key"
        class="CoreExtensionHost-card"
      >
        <div class="CoreExtensionHost-cardHeader">
          <span class="CoreExtensionHost-cardIcon">
            <i :class="card.icon"></i>
          </span>
          <div>
            <h3>{{ card.title }}</h3>
            <p>{{ card.description }}</p>
          </div>
        </div>

        <router-link :to="card.path" class="CoreExtensionHost-link">
          打开页面
        </router-link>
      </article>
    </div>

    <AdminStateBlock v-if="!cards.length" tone="subtle">
      当前核心扩展尚未注册对应后台页面。
    </AdminStateBlock>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'

const props = defineProps({
  extension: {
    type: Object,
    default: null,
  },
  hostKind: {
    type: String,
    default: 'settings',
  },
})

const internalPageTargets = {
  '/admin/mail': '/admin/internal/core/mail',
  '/admin/advanced': '/admin/internal/core/advanced',
  '/admin/audit-logs': '/admin/internal/core/audit-logs',
  '/admin/docs': '/admin/internal/core/docs',
}

const cards = computed(() => (
  (Array.isArray(props.extension?.admin_page_details) ? props.extension.admin_page_details : [])
    .filter((page) => {
      const path = String(page?.path || '').trim()
      if (!path || path === '/admin' || path === '/admin/modules' || path === '/admin/permissions') {
        return false
      }

      if (props.hostKind === 'operations') {
        return ['/admin/advanced', '/admin/audit-logs', '/admin/docs'].includes(path)
      }

      return Boolean(page?.settings_group) && path !== '/admin/advanced'
    })
    .map((page) => ({
      key: page.path,
      title: page.label,
      description: page.description || '查看当前核心后台页面。',
      path: internalPageTargets[page.path] || page.path,
      icon: page.icon || 'fas fa-cog',
    }))
))

const heroTitle = computed(() => {
  const name = props.extension?.name || '核心扩展'
  return props.hostKind === 'operations'
    ? `${name} 维护与工具入口`
    : `${name} 配置入口`
})

const heroDescription = computed(() => (
  props.hostKind === 'operations'
    ? '核心后台能力正在迁移到扩展宿主协议，这里统一承接运行维护、审计与开发工具类页面入口。'
    : '核心后台能力正在迁移到扩展宿主协议，这里统一承接基础配置类页面入口。'
))
</script>

<style scoped>
.CoreExtensionHost {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.CoreExtensionHost-hero,
.CoreExtensionHost-card {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.CoreExtensionHost-hero {
  padding: 20px;
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.CoreExtensionHost-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.CoreExtensionHost-hero h2,
.CoreExtensionHost-card h3 {
  margin: 0 0 10px;
}

.CoreExtensionHost-hero p,
.CoreExtensionHost-card p {
  margin: 0;
}

.CoreExtensionHost-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
}

.CoreExtensionHost-card {
  display: grid;
  gap: 16px;
  padding: 18px;
}

.CoreExtensionHost-cardHeader {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.CoreExtensionHost-cardIcon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: var(--forum-bg-subtle);
  color: var(--forum-primary-color);
  flex-shrink: 0;
}

.CoreExtensionHost-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 0 14px;
  border: 1px solid #d6e4f3;
  border-radius: 999px;
  background: #edf4fb;
  color: #325b85;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

@media (max-width: 768px) {
  .CoreExtensionHost-grid {
    grid-template-columns: 1fr;
  }
}
</style>
