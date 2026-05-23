<template>
  <div
    class="search-box"
    :class="{ 'search-box--active': currentSearchQuery }"
    role="button"
    tabindex="0"
    :aria-label="openLabelText"
    @click="$emit('open-search')"
    @keydown.enter.prevent="$emit('open-search')"
    @keydown.space.prevent="$emit('open-search')"
  >
    <i class="fas fa-search"></i>
    <input
      type="text"
      :placeholder="placeholderText"
      :value="searchPreviewText"
      readonly
    />
    <button
      v-if="currentSearchQuery"
      type="button"
      class="search-clear"
      :aria-label="clearLabelText"
      @click.stop="$emit('clear-search')"
    >
      <i class="fas fa-times-circle"></i>
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { getUiCopy } from '@/forum/registry'

const props = defineProps({
  currentSearchQuery: {
    type: String,
    default: ''
  },
  searchPreviewText: {
    type: String,
    default: ''
  }
})
const placeholderText = computed(() => getUiCopy({
  surface: 'header-search-placeholder',
  currentSearchQuery: props.currentSearchQuery,
})?.text || '搜索论坛')
const openLabelText = computed(() => getUiCopy({
  surface: 'header-search-open-label',
})?.text || '打开全局搜索')
const clearLabelText = computed(() => getUiCopy({
  surface: 'header-search-clear-label',
})?.text || '清除搜索')

defineEmits(['open-search', 'clear-search'])
</script>

<style scoped>
.search-box {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--forum-bg-subtle);
  border-radius: 3px;
  border: 1px solid transparent;
  transition: all 0.2s;
  width: 200px;
  cursor: pointer;
}

.search-box:focus-within,
.search-box--active {
  background: var(--forum-bg-elevated);
  border-color: var(--forum-primary-color);
}

.search-box i {
  color: var(--forum-text-soft);
  font-size: 14px;
}

.search-box input {
  border: none;
  background: none;
  outline: none;
  font-size: 13px;
  color: var(--forum-text-color);
  width: 100%;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  border-radius: 0;
  box-shadow: none;
  padding: 0;
}

.search-box input::placeholder {
  color: var(--forum-text-soft);
}

.search-clear {
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #8c98a4;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.search-clear:hover {
  background: var(--forum-bg-canvas);
  color: var(--forum-text-muted);
}

@media (max-width: 900px) {
  .search-box {
    display: none;
  }
}
</style>
