<template>
  <section class="DiscussionsExtensionHost">
    <section v-if="hostKind === 'permissions'" class="DiscussionsExtensionHost-panel">
      <div class="DiscussionsExtensionHost-sectionHead">
        <h3>讨论权限</h3>
        <router-link to="/admin/permissions" class="DiscussionsExtensionHost-link">
          打开全局权限管理
        </router-link>
      </div>

      <div v-if="permissionSections.length" class="DiscussionsExtensionHost-sections">
        <section
          v-for="section in permissionSections"
          :key="section.name"
          class="DiscussionsExtensionHost-section"
        >
          <header class="DiscussionsExtensionHost-sectionHeader">
            <h4>{{ section.label }}</h4>
            <span>{{ section.permission_count }}</span>
          </header>

          <div class="DiscussionsExtensionHost-list">
            <article
              v-for="permission in section.permissions"
              :key="permission.name"
              class="DiscussionsExtensionHost-item"
            >
              <div class="DiscussionsExtensionHost-itemMain">
                <div class="DiscussionsExtensionHost-itemTitle">
                  <i v-if="permission.icon" :class="permission.icon"></i>
                  <strong>{{ permission.label }}</strong>
                </div>
                <code>{{ permission.name }}</code>
              </div>
              <p v-if="permission.description" class="DiscussionsExtensionHost-itemDescription">
                {{ permission.description }}
              </p>
            </article>
          </div>
        </section>
      </div>
    </section>

    <section v-else class="DiscussionsExtensionHost-panel">
      <div class="DiscussionsExtensionHost-sectionHead">
        <h3>讨论相关功能</h3>
      </div>

      <div class="DiscussionsExtensionHost-groups">
        <section v-if="discussionListFilters.length" class="DiscussionsExtensionHost-section">
          <header class="DiscussionsExtensionHost-sectionHeader">
            <h4>列表入口</h4>
            <span>{{ discussionListFilters.length }}</span>
          </header>

          <div class="DiscussionsExtensionHost-list">
            <article
              v-for="item in discussionListFilters"
              :key="item.key"
              class="DiscussionsExtensionHost-item"
            >
              <div class="DiscussionsExtensionHost-itemMain">
                <strong>{{ item.label }}</strong>
                <code>{{ item.meta }}</code>
              </div>
              <p v-if="item.description" class="DiscussionsExtensionHost-itemDescription">
                {{ item.description }}
              </p>
            </article>
          </div>
        </section>

        <section v-if="discussionSorts.length" class="DiscussionsExtensionHost-section">
          <header class="DiscussionsExtensionHost-sectionHeader">
            <h4>讨论排序</h4>
            <span>{{ discussionSorts.length }}</span>
          </header>

          <div class="DiscussionsExtensionHost-list">
            <article
              v-for="item in discussionSorts"
              :key="item.key"
              class="DiscussionsExtensionHost-item"
            >
              <div class="DiscussionsExtensionHost-itemMain">
                <strong>{{ item.label }}</strong>
                <code>{{ item.meta }}</code>
              </div>
              <p v-if="item.description" class="DiscussionsExtensionHost-itemDescription">
                {{ item.description }}
              </p>
            </article>
          </div>
        </section>

        <section v-if="searchFilters.length" class="DiscussionsExtensionHost-section">
          <header class="DiscussionsExtensionHost-sectionHeader">
            <h4>搜索过滤</h4>
            <span>{{ searchFilters.length }}</span>
          </header>

          <div class="DiscussionsExtensionHost-list">
            <article
              v-for="item in searchFilters"
              :key="item.key"
              class="DiscussionsExtensionHost-item"
            >
              <div class="DiscussionsExtensionHost-itemMain">
                <strong>{{ item.label }}</strong>
                <code>{{ item.meta }}</code>
              </div>
              <p v-if="item.description" class="DiscussionsExtensionHost-itemDescription">
                {{ item.description }}
              </p>
            </article>
          </div>
        </section>
      </div>
    </section>
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

const permissionSections = computed(() => (
  Array.isArray(props.extension?.permission_sections) ? props.extension.permission_sections : []
))

const capabilityPanels = computed(() => resolveExtensionCapabilityPanels(props.extension))
const discussionSorts = computed(() => capabilityPanels.value.find(item => item.key === 'discussion_sorts')?.items || [])
const discussionListFilters = computed(() => capabilityPanels.value.find(item => item.key === 'discussion_list_filters')?.items || [])
const searchFilters = computed(() => capabilityPanels.value.find(item => item.key === 'search_filters')?.items || [])
</script>

<style scoped>
.DiscussionsExtensionHost {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.DiscussionsExtensionHost-panel {
  padding: 20px;
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.DiscussionsExtensionHost-sectionHead,
.DiscussionsExtensionHost-sectionHeader,
.DiscussionsExtensionHost-itemMain {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
}

.DiscussionsExtensionHost-sectionHead {
  margin-bottom: 16px;
}

.DiscussionsExtensionHost-sectionHead h3,
.DiscussionsExtensionHost-sectionHeader h4 {
  margin: 0;
}

.DiscussionsExtensionHost-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid #d6e4f3;
  border-radius: 999px;
  background: #edf4fb;
  color: #325b85;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

.DiscussionsExtensionHost-sections,
.DiscussionsExtensionHost-groups {
  display: grid;
  gap: 22px;
}

.DiscussionsExtensionHost-section + .DiscussionsExtensionHost-section {
  padding-top: 22px;
  border-top: 1px solid #e5ebf3;
}

.DiscussionsExtensionHost-sectionHeader {
  margin-bottom: 14px;
}

.DiscussionsExtensionHost-sectionHeader h4 {
  color: #5f7798;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.DiscussionsExtensionHost-sectionHeader span {
  color: var(--forum-text-soft);
  font-size: 12px;
  font-weight: 700;
}

.DiscussionsExtensionHost-list {
  display: grid;
  gap: 0;
}

.DiscussionsExtensionHost-item {
  display: grid;
  gap: 8px;
  padding: 14px 0;
  border-bottom: 1px solid #edf2f7;
}

.DiscussionsExtensionHost-item:last-child {
  border-bottom: 0;
}

.DiscussionsExtensionHost-itemTitle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.DiscussionsExtensionHost-itemTitle i {
  color: #6d83a4;
}

.DiscussionsExtensionHost-itemDescription {
  margin: 0;
  color: var(--forum-text-soft);
  line-height: 1.6;
}
</style>
