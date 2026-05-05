<template>
  <div v-if="items.length" class="composer-status-bar" aria-label="编辑器状态">
    <div
      v-for="item in items"
      :key="item.key"
      class="composer-status-item"
      :class="{ [`is-${item.tone}`]: Boolean(item.tone) }"
    >
      <span class="composer-status-label">{{ item.label }}</span>
      <span class="composer-status-value">{{ item.value }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped>
.composer-status-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 0 10px;
}

.composer-status-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 5px 10px;
  border-radius: 999px;
  background: #edf2f7;
  color: #5b6877;
  font-size: 12px;
  line-height: 1.4;
}

.composer-status-item.is-warning {
  background: #fff3d9;
  color: #946200;
}

.composer-status-item.is-success {
  background: #e8f6ee;
  color: #2d6f48;
}

.composer-status-item.is-error {
  background: #fdebec;
  color: #a33a44;
}

.composer-status-label {
  font-weight: 700;
  white-space: nowrap;
}

.composer-status-value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .composer-status-bar {
    gap: 6px;
  }

  .composer-status-item {
    max-width: 100%;
  }
}
</style>
