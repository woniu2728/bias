<template>
  <section class="DiscussionsExtensionHost">
    <header class="DiscussionsExtensionHost-hero">
      <p class="DiscussionsExtensionHost-kicker">Discussion Platform</p>
      <h2>{{ heroTitle }}</h2>
      <p>{{ heroDescription }}</p>
    </header>

    <div v-if="hostKind === 'permissions'" class="DiscussionsExtensionHost-stack">
      <div class="DiscussionsExtensionHost-grid">
        <article class="DiscussionsExtensionHost-card">
          <small>权限数量</small>
          <strong>{{ permissionSummary.permission_count }}</strong>
        </article>
        <article class="DiscussionsExtensionHost-card">
          <small>权限分组</small>
          <strong>{{ permissionSummary.section_count }}</strong>
        </article>
        <article class="DiscussionsExtensionHost-card">
          <small>涉及模块</small>
          <strong>{{ permissionSummary.module_count }}</strong>
        </article>
      </div>

      <section v-if="permissionSections.length" class="DiscussionsExtensionHost-panel">
        <h3>讨论治理权限</h3>
        <div class="DiscussionsExtensionHost-sectionGrid">
          <article
            v-for="section in permissionSections"
            :key="section.name"
            class="DiscussionsExtensionHost-sectionCard"
          >
            <div class="DiscussionsExtensionHost-sectionHead">
              <strong>{{ section.label }}</strong>
              <span>{{ section.permission_count }}</span>
            </div>
            <ul class="DiscussionsExtensionHost-list">
              <li v-for="permission in section.permissions" :key="permission.name">
                <div class="DiscussionsExtensionHost-listTitle">
                  <i v-if="permission.icon" :class="permission.icon"></i>
                  <strong>{{ permission.label }}</strong>
                </div>
                <code>{{ permission.name }}</code>
                <p v-if="permission.description">{{ permission.description }}</p>
              </li>
            </ul>
          </article>
        </div>
      </section>

      <div class="DiscussionsExtensionHost-actions">
        <router-link to="/admin/permissions" class="Button Button--primary">
          打开全局权限管理
        </router-link>
      </div>
    </div>

    <div v-else class="DiscussionsExtensionHost-stack">
      <div class="DiscussionsExtensionHost-grid">
        <article class="DiscussionsExtensionHost-card">
          <small>讨论排序</small>
          <strong>{{ capabilityCounts.discussionSorts }}</strong>
        </article>
        <article class="DiscussionsExtensionHost-card">
          <small>列表入口</small>
          <strong>{{ capabilityCounts.listFilters }}</strong>
        </article>
        <article class="DiscussionsExtensionHost-card">
          <small>搜索过滤</small>
          <strong>{{ capabilityCounts.searchFilters }}</strong>
        </article>
      </div>

      <section class="DiscussionsExtensionHost-panel">
        <h3>讨论流入口</h3>
        <div class="DiscussionsExtensionHost-chipGroup">
          <span
            v-for="item in discussionListFilters"
            :key="item.key"
            class="DiscussionsExtensionHost-chip"
          >
            {{ item.label }}<small>{{ item.meta }}</small>
          </span>
        </div>
      </section>

      <section class="DiscussionsExtensionHost-panel">
        <h3>排序与搜索</h3>
        <div class="DiscussionsExtensionHost-sectionGrid">
          <article class="DiscussionsExtensionHost-sectionCard">
            <div class="DiscussionsExtensionHost-sectionHead">
              <strong>讨论排序</strong>
              <span>{{ discussionSorts.length }}</span>
            </div>
            <ul class="DiscussionsExtensionHost-list">
              <li v-for="item in discussionSorts" :key="item.key">
                <strong>{{ item.label }}</strong>
                <code>{{ item.meta }}</code>
                <p v-if="item.description">{{ item.description }}</p>
              </li>
            </ul>
          </article>
          <article class="DiscussionsExtensionHost-sectionCard">
            <div class="DiscussionsExtensionHost-sectionHead">
              <strong>搜索过滤</strong>
              <span>{{ searchFilters.length }}</span>
            </div>
            <ul class="DiscussionsExtensionHost-list">
              <li v-for="item in searchFilters" :key="item.key">
                <strong>{{ item.label }}</strong>
                <code>{{ item.meta }}</code>
                <p v-if="item.description">{{ item.description }}</p>
              </li>
            </ul>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import {
  resolveExtensionCapabilityPanels,
} from '../extensions/diagnostics'

const props = defineProps({
  extension: {
    type: Object,
    default: null,
  },
  hostKind: {
    type: String,
    default: 'operations',
  },
})

const permissionSummary = computed(() => (
  props.extension?.permission_summary || { permission_count: 0, section_count: 0, module_count: 0 }
))
const permissionSections = computed(() => (
  Array.isArray(props.extension?.permission_sections) ? props.extension.permission_sections : []
))

const capabilityPanels = computed(() => resolveExtensionCapabilityPanels(props.extension))
const discussionSorts = computed(() => capabilityPanels.value.find(item => item.key === 'discussion_sorts')?.items || [])
const discussionListFilters = computed(() => capabilityPanels.value.find(item => item.key === 'discussion_list_filters')?.items || [])
const searchFilters = computed(() => capabilityPanels.value.find(item => item.key === 'search_filters')?.items || [])

const capabilityCounts = computed(() => ({
  discussionSorts: discussionSorts.value.length,
  listFilters: discussionListFilters.value.length,
  searchFilters: searchFilters.value.length,
}))

const heroTitle = computed(() => (
  props.hostKind === 'permissions' ? '讨论权限与治理规则' : '讨论流与搜索策略'
))

const heroDescription = computed(() => (
  props.hostKind === 'permissions'
    ? '这里集中查看讨论模块的发帖、回复和治理权限，再统一跳转到全局权限矩阵完成授权。'
    : '这里集中查看讨论列表、排序和搜索语法，作为核心讨论模块的自定义操作宿主页。'
))
</script>

<style scoped>
.DiscussionsExtensionHost {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.DiscussionsExtensionHost-hero,
.DiscussionsExtensionHost-card,
.DiscussionsExtensionHost-panel {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.DiscussionsExtensionHost-hero,
.DiscussionsExtensionHost-panel {
  padding: 20px;
}

.DiscussionsExtensionHost-hero {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.DiscussionsExtensionHost-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.DiscussionsExtensionHost-hero h2,
.DiscussionsExtensionHost-panel h3 {
  margin: 0 0 10px;
}

.DiscussionsExtensionHost-hero p {
  margin: 0;
}

.DiscussionsExtensionHost-stack {
  display: grid;
  gap: 18px;
}

.DiscussionsExtensionHost-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.DiscussionsExtensionHost-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.DiscussionsExtensionHost-card small,
.DiscussionsExtensionHost-list li p {
  color: var(--forum-text-soft);
}

.DiscussionsExtensionHost-sectionGrid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}

.DiscussionsExtensionHost-sectionCard {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}

.DiscussionsExtensionHost-sectionHead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.DiscussionsExtensionHost-sectionHead span {
  color: var(--forum-text-soft);
  font-size: 12px;
  font-weight: 700;
}

.DiscussionsExtensionHost-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.DiscussionsExtensionHost-list li {
  display: grid;
  gap: 4px;
}

.DiscussionsExtensionHost-listTitle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.DiscussionsExtensionHost-list li p {
  margin: 0;
  line-height: 1.6;
}

.DiscussionsExtensionHost-chipGroup {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.DiscussionsExtensionHost-chip {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  min-width: 120px;
  padding: 10px 12px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
  font-size: 13px;
  font-weight: 600;
}

.DiscussionsExtensionHost-chip small {
  color: var(--forum-text-soft);
  font-size: 12px;
  font-weight: 500;
}

.DiscussionsExtensionHost-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

@media (max-width: 768px) {
  .DiscussionsExtensionHost-sectionGrid {
    grid-template-columns: 1fr;
  }
}
</style>
