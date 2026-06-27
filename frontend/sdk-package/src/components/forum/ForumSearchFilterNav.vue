<template>
  <nav class="search-filters">
    <button
      v-for="item in normalizedItems"
      :key="item.value"
      type="button"
      class="filter-item"
      :class="{ active: activeValue === item.value }"
      @click="$emit('change', item.value)"
    >
      <span>{{ item.label }}</span>
      <strong>{{ item.count }}</strong>
    </button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { getUiCopy } from '../../forum/registry.js'

const props = defineProps({
  activeValue: {
    type: String,
    required: true
  },
  items: {
    type: Array,
    default: () => []
  }
})

defineEmits(['change'])

const normalizedItems = computed(() => props.items.map(item => {
  const uiCopy = getUiCopy({
    surface: 'search-filter-item-label',
    value: item.value,
    label: item.label,
    count: item.count,
    active: props.activeValue === item.value,
  })

  return {
    ...item,
    label: uiCopy?.text || item.label,
  }
}))
</script>

<style scoped>
.search-filters {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: var(--forum-radius-sm);
  background: transparent;
  color: var(--forum-text-muted);
}

.filter-item:hover {
  background: var(--forum-bg-subtle);
}

.filter-item.active {
  background: var(--forum-primary-color);
  color: var(--forum-text-inverse);
}

.filter-item strong {
  font-size: 12px;
}
</style>
