<template>
  <div class="search-stats">
    <span
      v-for="item in items"
      :key="item.key"
      class="search-stat"
    >
      <strong>{{ item.count }}</strong>
      <span>{{ formatLabel(item) }}</span>
    </span>
  </div>
</template>

<script setup>
import { getUiCopy } from '@bias/forum'

defineProps({
  items: {
    type: Array,
    default: () => []
  }
})

function formatLabel(item) {
  return getUiCopy({
    surface: 'search-stat-label',
    key: item?.key,
    label: item?.label,
    count: item?.count,
  })?.text || item?.label || ''
}
</script>

<style scoped>
.search-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 18px;
}

.search-stat {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 0 12px;
  border-radius: var(--forum-radius-pill);
  background: rgba(255, 255, 255, 0.88);
  color: #4a5d70;
}

.search-stat strong {
  color: #263646;
  font-size: 15px;
}
</style>
