<template>
  <section class="PostsExtensionHost">
    <header class="PostsExtensionHost-hero">
      <p class="PostsExtensionHost-kicker">Post Stream</p>
      <h2>帖子流与系统事件帖</h2>
      <p>这里集中查看帖子类型、帖子搜索扩展和内容输出语义，作为核心帖子模块的自定义操作宿主页。</p>
    </header>

    <div class="PostsExtensionHost-grid">
      <article class="PostsExtensionHost-card">
        <small>帖子类型</small>
        <strong>{{ postTypes.length }}</strong>
      </article>
      <article class="PostsExtensionHost-card">
        <small>搜索过滤</small>
        <strong>{{ searchFilters.length }}</strong>
      </article>
      <article class="PostsExtensionHost-card">
        <small>系统事件帖</small>
        <strong>{{ systemPostTypes.length }}</strong>
      </article>
    </div>

    <section class="PostsExtensionHost-panel">
      <h3>帖子类型</h3>
      <div class="PostsExtensionHost-typeGrid">
        <article
          v-for="item in postTypes"
          :key="item.key"
          class="PostsExtensionHost-typeCard"
        >
          <strong>{{ item.label }}</strong>
          <code>{{ item.meta }}</code>
          <p v-if="item.description">{{ item.description }}</p>
        </article>
      </div>
    </section>

    <section v-if="systemPostTypes.length" class="PostsExtensionHost-panel">
      <h3>系统事件帖</h3>
      <div class="PostsExtensionHost-chipGroup">
        <span
          v-for="item in systemPostTypes"
          :key="item.key"
          class="PostsExtensionHost-chip"
        >
          {{ item.label }}
        </span>
      </div>
    </section>

    <section v-if="searchFilters.length" class="PostsExtensionHost-panel">
      <h3>帖子搜索扩展</h3>
      <ul class="PostsExtensionHost-list">
        <li v-for="item in searchFilters" :key="item.key">
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
const postTypes = computed(() => capabilityPanels.value.find(item => item.key === 'post_types')?.items || [])
const searchFilters = computed(() => (
  (capabilityPanels.value.find(item => item.key === 'search_filters')?.items || [])
    .filter(item => String(item.moduleId || '').trim() === 'posts')
))
const systemPostTypes = computed(() => postTypes.value.filter(item => item.meta !== 'comment'))
</script>

<style scoped>
.PostsExtensionHost {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.PostsExtensionHost-hero,
.PostsExtensionHost-card,
.PostsExtensionHost-panel {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.PostsExtensionHost-hero,
.PostsExtensionHost-panel {
  padding: 20px;
}

.PostsExtensionHost-hero {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.PostsExtensionHost-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.PostsExtensionHost-hero h2,
.PostsExtensionHost-panel h3 {
  margin: 0 0 10px;
}

.PostsExtensionHost-hero p {
  margin: 0;
}

.PostsExtensionHost-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.PostsExtensionHost-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.PostsExtensionHost-card small,
.PostsExtensionHost-list li p {
  color: var(--forum-text-soft);
}

.PostsExtensionHost-typeGrid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.PostsExtensionHost-typeCard {
  display: grid;
  gap: 6px;
  padding: 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}

.PostsExtensionHost-typeCard p,
.PostsExtensionHost-list li p {
  margin: 0;
  line-height: 1.6;
}

.PostsExtensionHost-chipGroup {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.PostsExtensionHost-chip {
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

.PostsExtensionHost-list {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.PostsExtensionHost-list li {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}
</style>
