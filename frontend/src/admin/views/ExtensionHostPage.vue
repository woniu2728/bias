<template>
  <AdminPage
    class-name="ExtensionHostPage"
    :icon="extension?.icon || 'fas fa-puzzle-piece'"
    :title="pageTitle"
    :description="pageDescription"
  >
    <AdminStateBlock v-if="loading" tone="subtle">加载扩展页面中...</AdminStateBlock>
    <AdminStateBlock v-else-if="errorMessage" tone="danger">{{ errorMessage }}</AdminStateBlock>

    <div v-else-if="extension" class="ExtensionHostPage-content">
      <section class="ExtensionHostPage-topbar">
        <router-link :to="detailPath" class="ExtensionHostPage-back">
          <i class="fas fa-arrow-left"></i>
          <span>返回扩展详情</span>
        </router-link>
        <span class="ExtensionHostPage-kind">{{ pageKindLabel }}</span>
      </section>

      <component
        :is="resolvedComponent"
        v-if="resolvedComponent"
        :extension="extension"
        :host-kind="hostKind"
      />
      <AdminStateBlock v-else tone="subtle">
        当前扩展尚未提供 {{ pageKindLabel }} 组件。
      </AdminStateBlock>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import api from '../../api'
import AdminPage from '../components/AdminPage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import { resolveExtensionAdminComponent } from '../extensions/entryResolver'
import { resolveFallbackExtensionSettingsPage } from '../extensions/fallbacks'
import { findAdminRouteByPath } from '../registry'
import ApprovalQueuePage from './ApprovalQueuePage.vue'
import FlagsPage from './FlagsPage.vue'
import TagsPage from './TagsPage.vue'
import UsersPage from './UsersPage.vue'

const route = useRoute()
const loading = ref(true)
const errorMessage = ref('')
const extension = ref(null)
const resolvedComponent = ref(null)

const adminEntryModules = import.meta.glob('../../../../extensions/*/frontend/admin/index.js')
const builtinAdminEntries = {
  'builtin:approval': {
    resolveOperationsPage: () => ApprovalQueuePage,
  },
  'builtin:flags': {
    resolveOperationsPage: () => FlagsPage,
  },
  'builtin:tags': {
    resolveSettingsPage: () => TagsPage,
  },
  'builtin:users': {
    resolveOperationsPage: () => UsersPage,
  },
}

const hostKind = computed(() => {
  const matchedRoute = findAdminRouteByPath(route.path)
  return matchedRoute?.extensionHostKind || 'settings'
})

const detailPath = computed(() => `/admin/extensions/${String(route.params.extensionId || '').trim()}`)
const pageKindLabel = computed(() => {
  if (hostKind.value === 'operations') {
    return '操作页'
  }
  if (hostKind.value === 'permissions') {
    return '权限页'
  }
  return '设置页'
})
const pageTitle = computed(() => {
  if (!extension.value) {
    return pageKindLabel.value
  }
  return `${extension.value.name} · ${pageKindLabel.value}`
})
const pageDescription = computed(() => {
  if (!extension.value) {
    return '加载扩展自带的后台页面。'
  }
  return `通过扩展入口加载 ${extension.value.name} 的${pageKindLabel.value}组件。`
})

onMounted(async () => {
  await loadExtensionHost()
})

watch(
  () => route.fullPath,
  async () => {
    await loadExtensionHost()
  }
)

async function loadExtensionHost() {
  loading.value = true
  errorMessage.value = ''
  resolvedComponent.value = null

  try {
    const extensionId = String(route.params.extensionId || '').trim()
    const data = await api.get(`/admin/extensions/${extensionId}`)
    extension.value = data.extension || null
    resolvedComponent.value = await resolveExtensionComponent(extension.value, hostKind.value)
  } catch (error) {
    console.error('加载扩展后台页面失败:', error)
    errorMessage.value = error.response?.data?.error || '加载扩展后台页面失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function resolveExtensionComponent(currentExtension, currentHostKind) {
  return resolveExtensionAdminComponent(currentExtension, currentHostKind, {
    importers: adminEntryModules,
    builtins: builtinAdminEntries,
    fallbacks: [resolveFallbackExtensionSettingsPage],
  })
}
</script>

<style scoped>
.ExtensionHostPage-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.ExtensionHostPage-topbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.ExtensionHostPage-back {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
  background: var(--forum-bg-subtle);
  color: var(--forum-text-color);
  text-decoration: none;
}

.ExtensionHostPage-kind {
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--forum-bg-subtle);
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
  font-weight: 600;
}
</style>
