<template>
  <section class="LikesExtensionHost">
    <header class="LikesExtensionHost-hero">
      <p class="LikesExtensionHost-kicker">Reaction Flow</p>
      <h2>点赞互动与提醒</h2>
      <p>这里集中查看点赞通知、默认互动偏好和当前互动能力，作为点赞模块的自定义操作宿主页。</p>
    </header>

    <div class="LikesExtensionHost-grid">
      <article class="LikesExtensionHost-card">
        <small>通知类型</small>
        <strong>{{ notificationTypes.length }}</strong>
      </article>
      <article class="LikesExtensionHost-card">
        <small>用户偏好</small>
        <strong>{{ userPreferences.length }}</strong>
      </article>
      <article class="LikesExtensionHost-card">
        <small>能力声明</small>
        <strong>{{ capabilities.length }}</strong>
      </article>
    </div>

    <section v-if="notificationTypes.length" class="LikesExtensionHost-panel">
      <h3>点赞通知</h3>
      <ul class="LikesExtensionHost-list">
        <li v-for="item in notificationTypes" :key="item.key">
          <strong>{{ item.label }}</strong>
          <code>{{ item.meta }}</code>
          <p v-if="item.description">{{ item.description }}</p>
        </li>
      </ul>
    </section>

    <section v-if="userPreferences.length" class="LikesExtensionHost-panel">
      <h3>默认用户偏好</h3>
      <div class="LikesExtensionHost-chipGroup">
        <span
          v-for="item in userPreferences"
          :key="item.key"
          class="LikesExtensionHost-chip"
        >
          {{ item.label }}
          <small>{{ item.meta }}</small>
        </span>
      </div>
    </section>

    <section v-if="capabilities.length" class="LikesExtensionHost-panel">
      <h3>当前互动能力</h3>
      <div class="LikesExtensionHost-chipGroup">
        <span
          v-for="item in capabilities"
          :key="item"
          class="LikesExtensionHost-chip LikesExtensionHost-chip--plain"
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
const capabilities = computed(() => Array.isArray(props.extension?.provides) ? props.extension.provides : [])
</script>

<style scoped>
.LikesExtensionHost {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.LikesExtensionHost-hero,
.LikesExtensionHost-card,
.LikesExtensionHost-panel {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.LikesExtensionHost-hero,
.LikesExtensionHost-panel {
  padding: 20px;
}

.LikesExtensionHost-hero {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.LikesExtensionHost-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.LikesExtensionHost-hero h2,
.LikesExtensionHost-panel h3 {
  margin: 0 0 10px;
}

.LikesExtensionHost-hero p {
  margin: 0;
}

.LikesExtensionHost-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.LikesExtensionHost-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.LikesExtensionHost-card small,
.LikesExtensionHost-list li p {
  color: var(--forum-text-soft);
}

.LikesExtensionHost-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.LikesExtensionHost-list li {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}

.LikesExtensionHost-list li p {
  margin: 0;
  line-height: 1.6;
}

.LikesExtensionHost-chipGroup {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.LikesExtensionHost-chip {
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

.LikesExtensionHost-chip small {
  color: var(--forum-text-soft);
  font-size: 12px;
  font-weight: 500;
}

.LikesExtensionHost-chip--plain {
  min-width: 0;
  justify-content: center;
}
</style>
