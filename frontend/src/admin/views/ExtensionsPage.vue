<template>
  <AdminPage
    class-name="ExtensionsPage"
    icon="fas fa-plug"
    title="扩展中心"
    description="查看扩展清单、状态、依赖与后台入口，为后续启停和独立设置页打底。"
  >
    <AdminStateBlock v-if="loading" tone="subtle">加载扩展信息中...</AdminStateBlock>
    <AdminStateBlock v-else-if="errorMessage" tone="danger">{{ errorMessage }}</AdminStateBlock>

    <div v-else class="ExtensionsPage-content">
      <section class="ExtensionsPage-summary">
        <article class="ExtensionsPage-summaryCard">
          <strong>{{ summary.extension_count ?? extensions.length }}</strong>
          <span>扩展总数</span>
        </article>
        <article class="ExtensionsPage-summaryCard">
          <strong>{{ summary.enabled_count ?? 0 }}</strong>
          <span>已启用</span>
        </article>
        <article class="ExtensionsPage-summaryCard">
          <strong>{{ summary.healthy_count ?? 0 }}</strong>
          <span>健康</span>
        </article>
        <article class="ExtensionsPage-summaryCard">
          <strong>{{ summary.filesystem_count ?? 0 }}</strong>
          <span>目录扩展</span>
        </article>
      </section>

      <AdminToolbar class="ExtensionsPage-toolbar" align="between">
        <div class="ExtensionsPage-toolbarGroup">
          <AdminFilterTabs v-model="sourceFilter" :options="sourceOptions" />
          <AdminFilterTabs v-model="statusFilter" :options="statusOptions" />
        </div>
        <label class="ExtensionsPage-search">
          <span class="sr-only">搜索扩展</span>
          <input
            v-model.trim="searchQuery"
            class="FormControl"
            type="search"
            placeholder="搜索扩展名、ID、能力或依赖"
          />
        </label>
      </AdminToolbar>

      <div v-if="filteredExtensions.length" class="ExtensionsPage-list">
        <article
          v-for="extension in filteredExtensions"
          :key="extension.id"
          class="ExtensionCard"
          :class="{ 'is-disabled': !extension.enabled }"
        >
          <div class="ExtensionCard-main">
            <span class="ExtensionCard-icon">
              <i :class="extension.icon || 'fas fa-puzzle-piece'"></i>
            </span>

            <div class="ExtensionCard-content">
              <div class="ExtensionCard-title">
                <h3>{{ extension.name }}</h3>
                <span class="ExtensionBadge">{{ extension.id }}</span>
                <span class="ExtensionStatus" :class="extension.enabled ? 'is-enabled' : 'is-disabled'">
                  {{ extension.enabled ? '已启用' : '未启用' }}
                </span>
              </div>

              <p class="ExtensionCard-description">{{ extension.description || '暂无描述' }}</p>

              <div class="ExtensionCard-meta">
                <span><strong>版本</strong> {{ extension.version }}</span>
                <span><strong>来源</strong> {{ extension.source }}</span>
                <span v-if="extension.dependencies.length"><strong>依赖</strong> {{ extension.dependencies.join('、') }}</span>
                <span v-if="extension.module_ids.length"><strong>模块</strong> {{ extension.module_ids.join('、') }}</span>
              </div>

              <div v-if="extension.provides.length" class="ExtensionCard-tokens">
                <span v-for="capability in extension.provides" :key="`${extension.id}-${capability}`" class="ExtensionToken">
                  {{ capability }}
                </span>
              </div>
            </div>

            <div class="ExtensionCard-side">
              <router-link
                v-if="extension.settings_pages.length"
                :to="extension.settings_pages[0]"
                class="ExtensionAction ExtensionAction--primary"
              >
                设置入口
              </router-link>
              <router-link
                v-else-if="extension.permissions_pages.length"
                :to="extension.permissions_pages[0]"
                class="ExtensionAction ExtensionAction--primary"
              >
                权限入口
              </router-link>
              <a
                v-else-if="extension.documentation_url"
                :href="extension.documentation_url"
                class="ExtensionAction ExtensionAction--primary"
              >
                查看文档
              </a>

              <span class="ExtensionLifecycle">
                {{ extension.lifecycle?.registration_mode_label || '静态注册' }}
              </span>
            </div>
          </div>
        </article>
      </div>

      <AdminStateBlock v-else tone="subtle">当前筛选下没有匹配的扩展。</AdminStateBlock>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../../api'
import AdminPage from '../components/AdminPage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import AdminToolbar from '../components/AdminToolbar.vue'
import AdminFilterTabs from '../components/AdminFilterTabs.vue'

const loading = ref(true)
const errorMessage = ref('')
const summary = ref({})
const extensions = ref([])
const sourceFilter = ref('all')
const statusFilter = ref('all')
const searchQuery = ref('')

const sourceOptions = [
  { value: 'all', label: '全部来源', icon: 'fas fa-layer-group' },
  { value: 'builtin-module', label: '内置模块', icon: 'fas fa-shield-alt' },
  { value: 'filesystem', label: '目录扩展', icon: 'fas fa-folder-open' },
]

const statusOptions = [
  { value: 'all', label: '全部状态', icon: 'fas fa-border-all' },
  { value: 'enabled', label: '已启用', icon: 'fas fa-toggle-on' },
  { value: 'disabled', label: '未启用', icon: 'fas fa-toggle-off' },
]

const filteredExtensions = computed(() => {
  const keyword = searchQuery.value.trim().toLowerCase()

  return [...extensions.value]
    .filter(item => {
      if (sourceFilter.value !== 'all' && item.source !== sourceFilter.value) {
        return false
      }
      if (statusFilter.value === 'enabled' && !item.enabled) {
        return false
      }
      if (statusFilter.value === 'disabled' && item.enabled) {
        return false
      }

      if (!keyword) return true

      const haystack = [
        item.id,
        item.name,
        item.description,
        ...(item.dependencies || []),
        ...(item.provides || []),
        ...(item.module_ids || []),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()

      return haystack.includes(keyword)
    })
    .sort((left, right) => {
      if (Boolean(left.enabled) !== Boolean(right.enabled)) return left.enabled ? -1 : 1
      return String(left.name || '').localeCompare(String(right.name || ''), 'zh-CN')
    })
})

onMounted(async () => {
  await loadExtensions()
})

async function loadExtensions() {
  loading.value = true
  errorMessage.value = ''

  try {
    const data = await api.get('/admin/extensions')
    summary.value = data.summary || {}
    extensions.value = data.extensions || []
  } catch (error) {
    console.error('加载扩展信息失败:', error)
    errorMessage.value = error.response?.data?.error || '加载扩展信息失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.ExtensionsPage-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.ExtensionsPage-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}

.ExtensionsPage-summaryCard {
  padding: 16px 18px;
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-subtle);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ExtensionsPage-summaryCard strong {
  color: var(--forum-text-color);
  font-size: 22px;
}

.ExtensionsPage-summaryCard span {
  color: var(--forum-text-soft);
  font-size: 12px;
}

.ExtensionsPage-toolbar {
  gap: 16px;
}

.ExtensionsPage-toolbarGroup {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.ExtensionsPage-search {
  min-width: min(320px, 100%);
}

.ExtensionsPage-search .FormControl {
  width: 100%;
  min-height: 40px;
  padding: 0 14px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
  background: var(--forum-bg-elevated);
  color: var(--forum-text-color);
}

.ExtensionsPage-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ExtensionCard {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.ExtensionCard.is-disabled {
  opacity: 0.8;
}

.ExtensionCard-main {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 16px;
  align-items: flex-start;
  padding: 18px;
}

.ExtensionCard-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: #eef5fb;
  color: #426789;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
}

.ExtensionCard-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ExtensionCard-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.ExtensionCard-title h3 {
  margin: 0;
  color: var(--forum-text-color);
  font-size: 17px;
}

.ExtensionBadge,
.ExtensionStatus,
.ExtensionToken {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.ExtensionBadge {
  padding: 5px 9px;
  background: #eef2f6;
  color: #5c6b7c;
}

.ExtensionStatus {
  padding: 5px 10px;
}

.ExtensionStatus.is-enabled {
  background: #edf8f2;
  color: #25704d;
}

.ExtensionStatus.is-disabled {
  background: #f5f7fa;
  color: #6c7988;
}

.ExtensionCard-description {
  margin: 0;
  color: var(--forum-text-muted);
  line-height: 1.6;
}

.ExtensionCard-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  color: var(--forum-text-soft);
  font-size: 13px;
}

.ExtensionCard-meta strong {
  margin-right: 4px;
  color: var(--forum-text-muted);
}

.ExtensionCard-tokens {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ExtensionToken {
  padding: 5px 9px;
  background: var(--forum-bg-subtle);
  color: var(--forum-text-muted);
}

.ExtensionCard-side {
  min-width: 132px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.ExtensionAction {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--forum-border-color);
  border-radius: 999px;
  background: var(--forum-bg-subtle);
  color: var(--forum-text-color);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

.ExtensionAction--primary {
  background: #edf4fb;
  border-color: #d6e4f3;
  color: #325b85;
}

.ExtensionLifecycle {
  color: var(--forum-text-soft);
  font-size: 12px;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 768px) {
  .ExtensionsPage-toolbarGroup {
    flex-direction: column;
  }

  .ExtensionCard-main {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .ExtensionCard-side {
    grid-column: 1 / -1;
    min-width: 0;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
