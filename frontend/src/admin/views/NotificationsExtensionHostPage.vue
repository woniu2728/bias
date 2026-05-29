<template>
  <section class="NotificationsExtensionHost">
    <header class="NotificationsExtensionHost-hero">
      <p class="NotificationsExtensionHost-kicker">Notification Hub</p>
      <h2>通知分发与用户偏好</h2>
      <p>这里集中查看站内通知类型、默认偏好和扩展用户触达范围，作为通知模块的自定义操作宿主页。</p>
    </header>

    <div class="NotificationsExtensionHost-grid">
      <article class="NotificationsExtensionHost-card">
        <small>通知类型</small>
        <strong>{{ notificationTypes.length }}</strong>
      </article>
      <article class="NotificationsExtensionHost-card">
        <small>用户偏好</small>
        <strong>{{ userPreferences.length }}</strong>
      </article>
      <article class="NotificationsExtensionHost-card">
        <small>触达范围</small>
        <strong>{{ navigationScopes.length }}</strong>
      </article>
    </div>

    <section v-if="notificationTypes.length" class="NotificationsExtensionHost-panel">
      <h3>通知类型</h3>
      <div class="NotificationsExtensionHost-typeGrid">
        <article
          v-for="item in notificationTypes"
          :key="item.key"
          class="NotificationsExtensionHost-typeCard"
        >
          <strong>{{ item.label }}</strong>
          <code>{{ item.meta }}</code>
          <p v-if="item.description">{{ item.description }}</p>
        </article>
      </div>
    </section>

    <section v-if="userPreferences.length" class="NotificationsExtensionHost-panel">
      <h3>默认通知偏好</h3>
      <div class="NotificationsExtensionHost-chipGroup">
        <span
          v-for="item in userPreferences"
          :key="item.key"
          class="NotificationsExtensionHost-chip"
        >
          {{ item.label }}
          <small>{{ item.meta }}</small>
        </span>
      </div>
    </section>

    <section v-if="navigationScopes.length" class="NotificationsExtensionHost-panel">
      <h3>通知触达范围</h3>
      <div class="NotificationsExtensionHost-chipGroup">
        <span
          v-for="item in navigationScopes"
          :key="item"
          class="NotificationsExtensionHost-chip NotificationsExtensionHost-chip--scope"
        >
          {{ item }}
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
const userPreferences = computed(() => capabilityPanels.value.find(item => item.key === 'user_preferences')?.items || [])

const navigationScopes = computed(() => {
  const items = Array.isArray(props.extension?.notification_types) ? props.extension.notification_types : []
  return [...new Set(items.map(item => String(item.navigation_scope || '').trim()).filter(Boolean))]
})
</script>

<style scoped>
.NotificationsExtensionHost {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.NotificationsExtensionHost-hero,
.NotificationsExtensionHost-card,
.NotificationsExtensionHost-panel {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.NotificationsExtensionHost-hero,
.NotificationsExtensionHost-panel {
  padding: 20px;
}

.NotificationsExtensionHost-hero {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.NotificationsExtensionHost-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.NotificationsExtensionHost-hero h2,
.NotificationsExtensionHost-panel h3 {
  margin: 0 0 10px;
}

.NotificationsExtensionHost-hero p {
  margin: 0;
}

.NotificationsExtensionHost-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.NotificationsExtensionHost-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.NotificationsExtensionHost-card small {
  color: var(--forum-text-soft);
}

.NotificationsExtensionHost-typeGrid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.NotificationsExtensionHost-typeCard {
  display: grid;
  gap: 6px;
  padding: 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}

.NotificationsExtensionHost-typeCard p {
  margin: 0;
  color: var(--forum-text-soft);
  line-height: 1.6;
}

.NotificationsExtensionHost-chipGroup {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.NotificationsExtensionHost-chip {
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

.NotificationsExtensionHost-chip small {
  color: var(--forum-text-soft);
  font-size: 12px;
  font-weight: 500;
}

.NotificationsExtensionHost-chip--scope {
  min-width: 0;
  justify-content: center;
}
</style>
