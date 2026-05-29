<template>
  <section class="TagStatsExtensionHost">
    <header class="TagStatsExtensionHost-hero">
      <p class="TagStatsExtensionHost-kicker">Tag Runtime</p>
      <h2>标签统计刷新链路</h2>
      <p>这里集中查看标签统计刷新依赖的事件监听和关联模块，作为标签统计模块的自定义操作宿主页。</p>
    </header>

    <div class="TagStatsExtensionHost-grid">
      <article class="TagStatsExtensionHost-card">
        <small>事件监听</small>
        <strong>{{ eventListeners.length }}</strong>
      </article>
      <article class="TagStatsExtensionHost-card">
        <small>关联模块</small>
        <strong>{{ moduleIds.length }}</strong>
      </article>
      <article class="TagStatsExtensionHost-card">
        <small>能力声明</small>
        <strong>{{ capabilities.length }}</strong>
      </article>
    </div>

    <section v-if="eventListeners.length" class="TagStatsExtensionHost-panel">
      <h3>刷新事件链路</h3>
      <ul class="TagStatsExtensionHost-list">
        <li v-for="item in eventListeners" :key="item.key">
          <strong>{{ item.label }}</strong>
          <code>{{ item.meta }}</code>
          <p v-if="item.description">{{ item.description }}</p>
        </li>
      </ul>
    </section>

    <section v-if="moduleIds.length" class="TagStatsExtensionHost-panel">
      <h3>关联模块</h3>
      <div class="TagStatsExtensionHost-chipGroup">
        <span
          v-for="item in moduleIds"
          :key="item"
          class="TagStatsExtensionHost-chip"
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
const moduleIds = computed(() => Array.isArray(props.extension?.module_ids) ? props.extension.module_ids : [])
const capabilities = computed(() => Array.isArray(props.extension?.provides) ? props.extension.provides : [])
</script>

<style scoped>
.TagStatsExtensionHost {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.TagStatsExtensionHost-hero,
.TagStatsExtensionHost-card,
.TagStatsExtensionHost-panel {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.TagStatsExtensionHost-hero,
.TagStatsExtensionHost-panel {
  padding: 20px;
}

.TagStatsExtensionHost-hero {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.TagStatsExtensionHost-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.TagStatsExtensionHost-hero h2,
.TagStatsExtensionHost-panel h3 {
  margin: 0 0 10px;
}

.TagStatsExtensionHost-hero p {
  margin: 0;
}

.TagStatsExtensionHost-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.TagStatsExtensionHost-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.TagStatsExtensionHost-card small,
.TagStatsExtensionHost-list li p {
  color: var(--forum-text-soft);
}

.TagStatsExtensionHost-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.TagStatsExtensionHost-list li {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}

.TagStatsExtensionHost-list li p {
  margin: 0;
  line-height: 1.6;
}

.TagStatsExtensionHost-chipGroup {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.TagStatsExtensionHost-chip {
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
