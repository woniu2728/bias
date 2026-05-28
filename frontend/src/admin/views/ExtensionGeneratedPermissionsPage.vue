<template>
  <section class="ExtensionGeneratedPermissions">
    <header class="ExtensionGeneratedPermissions-hero">
      <p class="ExtensionGeneratedPermissions-kicker">Extension Permissions</p>
      <h2>{{ extension?.name || '扩展权限' }}</h2>
      <p>{{ heroDescription }}</p>
    </header>

    <div class="ExtensionGeneratedPermissions-grid">
      <article class="ExtensionGeneratedPermissions-card">
        <small>权限数量</small>
        <strong>{{ permissionSummary.permission_count }}</strong>
      </article>
      <article class="ExtensionGeneratedPermissions-card">
        <small>权限分组</small>
        <strong>{{ permissionSummary.section_count }}</strong>
      </article>
      <article class="ExtensionGeneratedPermissions-card">
        <small>涉及模块</small>
        <strong>{{ permissionSummary.module_count }}</strong>
      </article>
    </div>

    <section v-if="permissionModules.length" class="ExtensionGeneratedPermissions-panel">
      <h3>模块归属</h3>
      <div class="ExtensionGeneratedPermissions-chips">
        <span
          v-for="item in permissionModules"
          :key="item.module_id"
          class="ExtensionGeneratedPermissions-chip"
        >
          {{ item.module_id }} · {{ item.permission_count }}
        </span>
      </div>
    </section>

    <section v-if="permissionSections.length" class="ExtensionGeneratedPermissions-panel">
      <div
        v-for="section in permissionSections"
        :key="section.name"
        class="ExtensionGeneratedPermissions-section"
      >
        <header class="ExtensionGeneratedPermissions-sectionHeader">
          <div>
            <h3>{{ section.label }}</h3>
            <p>{{ section.permission_count }} 项权限</p>
          </div>
        </header>

        <div class="ExtensionGeneratedPermissions-list">
          <article
            v-for="permission in section.permissions"
            :key="permission.name"
            class="ExtensionGeneratedPermissions-item"
          >
            <div class="ExtensionGeneratedPermissions-itemMain">
              <div class="ExtensionGeneratedPermissions-itemTitle">
                <i v-if="permission.icon" :class="permission.icon"></i>
                <strong>{{ permission.label }}</strong>
              </div>
              <code>{{ permission.name }}</code>
            </div>
            <p v-if="permission.description" class="ExtensionGeneratedPermissions-itemDescription">
              {{ permission.description }}
            </p>
            <div class="ExtensionGeneratedPermissions-itemMeta">
              <span>模块：{{ permission.module_id }}</span>
              <span v-if="permission.required_permissions?.length">
                依赖：{{ permission.required_permissions.join('、') }}
              </span>
              <span v-if="permission.aliases?.length">
                别名：{{ permission.aliases.join('、') }}
              </span>
            </div>
          </article>
        </div>
      </div>
    </section>

    <AdminStateBlock v-else tone="subtle">
      当前扩展暂未注册独立权限项，或相关模块尚未启用。
    </AdminStateBlock>

    <div class="ExtensionGeneratedPermissions-actions">
      <router-link v-if="hasPermissionsRoute" to="/admin/permissions" class="Button Button--primary">
        打开全局权限管理
      </router-link>
      <router-link :to="detailPath" class="Button">
        返回扩展详情
      </router-link>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import {
  buildExtensionDetailRouteTarget,
} from '../extensions/diagnostics'

const route = useRoute()
const props = defineProps({
  extension: {
    type: Object,
    default: null,
  },
})

const detailPath = computed(() => (
  buildExtensionDetailRouteTarget(props.extension?.id, route)
))
const hasPermissionsRoute = computed(() => Boolean(props.extension?.action_links?.permissions_page))
const permissionSummary = computed(() => (
  props.extension?.permission_summary || { permission_count: 0, section_count: 0, module_count: 0 }
))
const permissionModules = computed(() => (
  Array.isArray(props.extension?.permission_modules) ? props.extension.permission_modules : []
))
const permissionSections = computed(() => (
  Array.isArray(props.extension?.permission_sections) ? props.extension.permission_sections : []
))
const heroDescription = computed(() => {
  const name = props.extension?.name || '当前扩展'
  if (!permissionSummary.value.permission_count) {
    return `${name} 当前没有独立权限矩阵，这个宿主页会继续承接扩展级权限入口。`
  }
  return `${name} 的权限能力已按扩展归属聚合展示，统一跳转到全局权限页完成用户组授权。`
})
</script>

<style scoped>
.ExtensionGeneratedPermissions {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.ExtensionGeneratedPermissions-hero,
.ExtensionGeneratedPermissions-card,
.ExtensionGeneratedPermissions-panel {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.ExtensionGeneratedPermissions-hero,
.ExtensionGeneratedPermissions-panel {
  padding: 20px;
}

.ExtensionGeneratedPermissions-hero {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.ExtensionGeneratedPermissions-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.ExtensionGeneratedPermissions-hero h2,
.ExtensionGeneratedPermissions-panel h3 {
  margin: 0 0 10px;
}

.ExtensionGeneratedPermissions-hero p:last-child,
.ExtensionGeneratedPermissions-sectionHeader p,
.ExtensionGeneratedPermissions-itemDescription {
  margin: 0;
}

.ExtensionGeneratedPermissions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.ExtensionGeneratedPermissions-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.ExtensionGeneratedPermissions-card small,
.ExtensionGeneratedPermissions-sectionHeader p,
.ExtensionGeneratedPermissions-itemMeta {
  color: var(--forum-text-soft);
}

.ExtensionGeneratedPermissions-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.ExtensionGeneratedPermissions-chip {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--forum-border-color);
  border-radius: 999px;
  background: var(--forum-bg-subtle);
  font-size: 13px;
  font-weight: 600;
}

.ExtensionGeneratedPermissions-section + .ExtensionGeneratedPermissions-section {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--forum-border-color);
}

.ExtensionGeneratedPermissions-sectionHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.ExtensionGeneratedPermissions-list {
  display: grid;
  gap: 12px;
}

.ExtensionGeneratedPermissions-item {
  display: grid;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}

.ExtensionGeneratedPermissions-itemMain {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
}

.ExtensionGeneratedPermissions-itemTitle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.ExtensionGeneratedPermissions-itemMeta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  font-size: 13px;
}

.ExtensionGeneratedPermissions-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
</style>
