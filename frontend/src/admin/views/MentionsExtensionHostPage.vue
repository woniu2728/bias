<template>
  <section class="MentionsExtensionHost">
    <header class="MentionsExtensionHost-hero">
      <p class="MentionsExtensionHost-kicker">Mention Signals</p>
      <h2>@提及规则与提醒</h2>
      <p>这里集中查看 @提及 的通知触达、搜索过滤和默认偏好，作为提及模块的自定义操作宿主页。</p>
    </header>

    <div class="MentionsExtensionHost-grid">
      <article class="MentionsExtensionHost-card">
        <small>通知类型</small>
        <strong>{{ notificationTypes.length }}</strong>
      </article>
      <article class="MentionsExtensionHost-card">
        <small>搜索过滤</small>
        <strong>{{ searchFilters.length }}</strong>
      </article>
      <article class="MentionsExtensionHost-card">
        <small>用户偏好</small>
        <strong>{{ userPreferences.length }}</strong>
      </article>
    </div>

    <section v-if="notificationTypes.length" class="MentionsExtensionHost-panel">
      <h3>提及通知</h3>
      <ul class="MentionsExtensionHost-list">
        <li v-for="item in notificationTypes" :key="item.key">
          <strong>{{ item.label }}</strong>
          <code>{{ item.meta }}</code>
          <p v-if="item.description">{{ item.description }}</p>
        </li>
      </ul>
    </section>

    <section v-if="searchFilters.length" class="MentionsExtensionHost-panel">
      <h3>提及搜索过滤</h3>
      <ul class="MentionsExtensionHost-list">
        <li v-for="item in searchFilters" :key="item.key">
          <strong>{{ item.label }}</strong>
          <code>{{ item.meta }}</code>
          <p v-if="item.description">{{ item.description }}</p>
        </li>
      </ul>
    </section>

    <section v-if="userPreferences.length" class="MentionsExtensionHost-panel">
      <h3>默认用户偏好</h3>
      <div class="MentionsExtensionHost-chipGroup">
        <span
          v-for="item in userPreferences"
          :key="item.key"
          class="MentionsExtensionHost-chip"
        >
          {{ item.label }}
          <small>{{ item.meta }}</small>
        </span>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { resolveExtensionCapabilityPanels } from '../extensions/diagnostics'

const props = defineProps({
  extension: {
    type: Object,
    default: null,
  },
})

const capabilityPanels = computed(() => resolveExtensionCapabilityPanels(props.extension))
const notificationTypes = computed(() => capabilityPanels.value.find(item => item.key === 'notification_types')?.items || [])
const searchFilters = computed(() => capabilityPanels.value.find(item => item.key === 'search_filters')?.items || [])
const userPreferences = computed(() => capabilityPanels.value.find(item => item.key === 'user_preferences')?.items || [])
</script>

<style scoped>
.MentionsExtensionHost {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.MentionsExtensionHost-hero,
.MentionsExtensionHost-card,
.MentionsExtensionHost-panel {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.MentionsExtensionHost-hero,
.MentionsExtensionHost-panel {
  padding: 20px;
}

.MentionsExtensionHost-hero {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.MentionsExtensionHost-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.MentionsExtensionHost-hero h2,
.MentionsExtensionHost-panel h3 {
  margin: 0 0 10px;
}

.MentionsExtensionHost-hero p,
.MentionsExtensionHost-list li p {
  margin: 0;
}

.MentionsExtensionHost-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.MentionsExtensionHost-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.MentionsExtensionHost-card small,
.MentionsExtensionHost-list li p,
.MentionsExtensionHost-chip small {
  color: var(--forum-text-soft);
}

.MentionsExtensionHost-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.MentionsExtensionHost-list li {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}

.MentionsExtensionHost-list li p {
  line-height: 1.6;
}

.MentionsExtensionHost-chipGroup {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.MentionsExtensionHost-chip {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  min-width: 140px;
  padding: 10px 12px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
  font-size: 13px;
  font-weight: 600;
}

.MentionsExtensionHost-chip small {
  font-size: 12px;
  font-weight: 500;
}
</style>
