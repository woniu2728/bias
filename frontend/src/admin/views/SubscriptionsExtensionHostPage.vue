<template>
  <section class="SubscriptionsExtensionHost">
    <header class="SubscriptionsExtensionHost-hero">
      <p class="SubscriptionsExtensionHost-kicker">Subscription Flow</p>
      <h2>关注流与关注通知</h2>
      <p>这里集中查看关注偏好、关注列表入口和关注后的通知链路，作为关注模块的自定义操作宿主页。</p>
    </header>

    <div class="SubscriptionsExtensionHost-grid">
      <article class="SubscriptionsExtensionHost-card">
        <small>用户偏好</small>
        <strong>{{ userPreferences.length }}</strong>
      </article>
      <article class="SubscriptionsExtensionHost-card">
        <small>列表入口</small>
        <strong>{{ listFilters.length }}</strong>
      </article>
      <article class="SubscriptionsExtensionHost-card">
        <small>事件监听</small>
        <strong>{{ eventListeners.length }}</strong>
      </article>
    </div>

    <section v-if="userPreferences.length" class="SubscriptionsExtensionHost-panel">
      <h3>默认关注偏好</h3>
      <div class="SubscriptionsExtensionHost-chipGroup">
        <span
          v-for="item in userPreferences"
          :key="item.key"
          class="SubscriptionsExtensionHost-chip"
        >
          {{ item.label }}
          <small>{{ item.meta }}</small>
        </span>
      </div>
    </section>

    <section v-if="listFilters.length" class="SubscriptionsExtensionHost-panel">
      <h3>关注列表入口</h3>
      <div class="SubscriptionsExtensionHost-chipGroup">
        <span
          v-for="item in listFilters"
          :key="item.key"
          class="SubscriptionsExtensionHost-chip SubscriptionsExtensionHost-chip--filter"
        >
          {{ item.label }}
          <small>{{ item.meta }}</small>
        </span>
      </div>
    </section>

    <section v-if="eventListeners.length" class="SubscriptionsExtensionHost-panel">
      <h3>通知触发链路</h3>
      <ul class="SubscriptionsExtensionHost-list">
        <li v-for="item in eventListeners" :key="item.key">
          <strong>{{ item.label }}</strong>
          <code>{{ item.meta }}</code>
          <p v-if="item.description">{{ item.description }}</p>
        </li>
      </ul>
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
const userPreferences = computed(() => capabilityPanels.value.find(item => item.key === 'user_preferences')?.items || [])
const listFilters = computed(() => capabilityPanels.value.find(item => item.key === 'discussion_list_filters')?.items || [])
const eventListeners = computed(() => capabilityPanels.value.find(item => item.key === 'event_listeners')?.items || [])
</script>

<style scoped>
.SubscriptionsExtensionHost {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.SubscriptionsExtensionHost-hero,
.SubscriptionsExtensionHost-card,
.SubscriptionsExtensionHost-panel {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.SubscriptionsExtensionHost-hero,
.SubscriptionsExtensionHost-panel {
  padding: 20px;
}

.SubscriptionsExtensionHost-hero {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.SubscriptionsExtensionHost-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.SubscriptionsExtensionHost-hero h2,
.SubscriptionsExtensionHost-panel h3 {
  margin: 0 0 10px;
}

.SubscriptionsExtensionHost-hero p,
.SubscriptionsExtensionHost-list li p {
  margin: 0;
}

.SubscriptionsExtensionHost-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.SubscriptionsExtensionHost-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.SubscriptionsExtensionHost-card small,
.SubscriptionsExtensionHost-list li p,
.SubscriptionsExtensionHost-chip small {
  color: var(--forum-text-soft);
}

.SubscriptionsExtensionHost-chipGroup {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.SubscriptionsExtensionHost-chip {
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

.SubscriptionsExtensionHost-chip small {
  font-size: 12px;
  font-weight: 500;
}

.SubscriptionsExtensionHost-chip--filter {
  min-width: 120px;
}

.SubscriptionsExtensionHost-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.SubscriptionsExtensionHost-list li {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}

.SubscriptionsExtensionHost-list li p {
  line-height: 1.6;
}
</style>
