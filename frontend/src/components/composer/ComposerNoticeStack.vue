<template>
  <div v-if="visibleNotices.length" class="composer-notice-stack" aria-live="polite">
    <div
      v-for="notice in visibleNotices"
      :key="notice.key"
      class="composer-notice"
      :class="`composer-notice--${normalizeTone(notice.tone)}`"
    >
      <span class="composer-notice-label">
        <i :class="notice.icon || toneIcon(normalizeTone(notice.tone))"></i>
        {{ notice.label }}
      </span>
      <span class="composer-notice-message">{{ notice.message }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  notices: {
    type: Array,
    default: () => []
  }
})

const visibleNotices = computed(() => {
  return props.notices.filter(notice => String(notice?.message || '').trim())
})

function normalizeTone(tone) {
  return ['success', 'warning', 'error'].includes(tone) ? tone : 'info'
}

function toneIcon(tone) {
  if (tone === 'success') return 'fas fa-check-circle'
  if (tone === 'warning') return 'fas fa-exclamation-triangle'
  if (tone === 'error') return 'fas fa-exclamation-circle'
  return 'fas fa-info-circle'
}
</script>

<style scoped>
.composer-notice-stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.composer-notice {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: #edf4fb;
  color: #325b88;
  line-height: 1.5;
}

.composer-notice--success {
  border-color: #c8ead2;
  background: #edf9f1;
  color: #256b3c;
}

.composer-notice--warning {
  border-color: #f3df9f;
  background: #fff3cd;
  color: #856404;
}

.composer-notice--error {
  border-color: #f1c4c4;
  background: #fdf0f0;
  color: #b33a3a;
}

.composer-notice-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 22px;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 700;
}

.composer-notice-label i {
  width: 14px;
  text-align: center;
}

.composer-notice-message {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 13px;
}

@media (max-width: 520px) {
  .composer-notice {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>
