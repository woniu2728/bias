<template>
  <section class="RealtimeExtensionHost">
    <header class="RealtimeExtensionHost-hero">
      <p class="RealtimeExtensionHost-kicker">Realtime Runtime</p>
      <h2>实时连接与广播链路</h2>
      <p>这里集中查看实时广播依赖的事件监听、能力声明和连接语义，作为实时模块的自定义操作宿主页。</p>
    </header>

    <div class="RealtimeExtensionHost-grid">
      <article class="RealtimeExtensionHost-card">
        <small>事件监听</small>
        <strong>{{ eventListeners.length }}</strong>
      </article>
      <article class="RealtimeExtensionHost-card">
        <small>能力声明</small>
        <strong>{{ capabilities.length }}</strong>
      </article>
      <article class="RealtimeExtensionHost-card">
        <small>关联模块</small>
        <strong>{{ moduleIds.length }}</strong>
      </article>
    </div>

    <section v-if="eventListeners.length" class="RealtimeExtensionHost-panel">
      <h3>广播事件链路</h3>
      <ul class="RealtimeExtensionHost-list">
        <li v-for="item in eventListeners" :key="item.key">
          <strong>{{ item.label }}</strong>
          <code>{{ item.meta }}</code>
          <p v-if="item.description">{{ item.description }}</p>
        </li>
      </ul>
    </section>

    <section v-if="capabilities.length" class="RealtimeExtensionHost-panel">
      <h3>实时能力</h3>
      <div class="RealtimeExtensionHost-chipGroup">
        <span
          v-for="item in capabilities"
          :key="item"
          class="RealtimeExtensionHost-chip"
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
const eventListeners = computed(() => capabilityPanels.value.find(item => item.key === 'event_listeners')?.items || [])
const capabilities = computed(() => Array.isArray(props.extension?.provides) ? props.extension.provides : [])
const moduleIds = computed(() => Array.isArray(props.extension?.module_ids) ? props.extension.module_ids : [])
</script>

<style scoped>
.RealtimeExtensionHost {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.RealtimeExtensionHost-hero,
.RealtimeExtensionHost-card,
.RealtimeExtensionHost-panel {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.RealtimeExtensionHost-hero,
.RealtimeExtensionHost-panel {
  padding: 20px;
}

.RealtimeExtensionHost-hero {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.RealtimeExtensionHost-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.RealtimeExtensionHost-hero h2,
.RealtimeExtensionHost-panel h3 {
  margin: 0 0 10px;
}

.RealtimeExtensionHost-hero p,
.RealtimeExtensionHost-list li p {
  margin: 0;
}

.RealtimeExtensionHost-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.RealtimeExtensionHost-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.RealtimeExtensionHost-card small,
.RealtimeExtensionHost-list li p {
  color: var(--forum-text-soft);
}

.RealtimeExtensionHost-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.RealtimeExtensionHost-list li {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}

.RealtimeExtensionHost-list li p {
  line-height: 1.6;
}

.RealtimeExtensionHost-chipGroup {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.RealtimeExtensionHost-chip {
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
</style>
