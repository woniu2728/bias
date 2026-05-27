<template>
  <section class="ExtensionGeneratedSurface">
    <header class="ExtensionGeneratedSurface-hero">
      <p class="ExtensionGeneratedSurface-kicker">Extension Permissions</p>
      <h2>{{ extension?.name || '扩展权限' }}</h2>
      <p>{{ heroDescription }}</p>
    </header>

    <div class="ExtensionGeneratedSurface-grid">
      <article class="ExtensionGeneratedSurface-card">
        <small>扩展 ID</small>
        <strong>{{ extension?.id || 'unknown' }}</strong>
      </article>
      <article class="ExtensionGeneratedSurface-card">
        <small>模块归属</small>
        <strong>{{ moduleSummary }}</strong>
      </article>
      <article class="ExtensionGeneratedSurface-card">
        <small>权限入口</small>
        <strong>{{ hasPermissionsRoute ? '已声明' : '未声明' }}</strong>
      </article>
    </div>

    <section class="ExtensionGeneratedSurface-panel">
      <h3>权限宿主说明</h3>
      <p>
        当前扩展未提供自定义权限页组件。Bias 会继续使用统一的权限管理页承载权限矩阵，避免每个扩展重复实现用户组和权限编辑界面。
      </p>
      <div class="ExtensionGeneratedSurface-actions">
        <router-link v-if="hasPermissionsRoute" to="/admin/permissions" class="Button Button--primary">
          打开全局权限管理
        </router-link>
        <router-link :to="detailPath" class="Button">
          返回扩展详情
        </router-link>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  extension: {
    type: Object,
    default: null,
  },
})

const detailPath = computed(() => `/admin/extensions/${String(props.extension?.id || '').trim()}`)
const hasPermissionsRoute = computed(() => Boolean(props.extension?.action_links?.permissions_page))
const moduleSummary = computed(() => {
  const moduleIds = Array.isArray(props.extension?.module_ids) ? props.extension.module_ids : []
  return moduleIds.length ? moduleIds.join('、') : '未关联模块'
})
const heroDescription = computed(() => {
  const name = props.extension?.name || '当前扩展'
  return `${name} 的权限能力仍通过平台统一权限矩阵管理，这个宿主页用于承接扩展级权限入口。`
})
</script>

<style scoped>
.ExtensionGeneratedSurface {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.ExtensionGeneratedSurface-hero,
.ExtensionGeneratedSurface-card,
.ExtensionGeneratedSurface-panel {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.ExtensionGeneratedSurface-hero,
.ExtensionGeneratedSurface-panel {
  padding: 20px;
}

.ExtensionGeneratedSurface-hero {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.ExtensionGeneratedSurface-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.ExtensionGeneratedSurface-hero h2,
.ExtensionGeneratedSurface-panel h3 {
  margin: 0 0 10px;
}

.ExtensionGeneratedSurface-hero p:last-child,
.ExtensionGeneratedSurface-panel p {
  margin: 0;
}

.ExtensionGeneratedSurface-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.ExtensionGeneratedSurface-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.ExtensionGeneratedSurface-card small {
  color: var(--forum-text-soft);
}

.ExtensionGeneratedSurface-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}
</style>
