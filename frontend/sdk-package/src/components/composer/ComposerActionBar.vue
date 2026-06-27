<template>
  <div class="composer-toolbar">
    <button
      type="button"
      class="composer-submit"
      :disabled="submitDisabled"
      @click="$emit('submit')"
    >
      <i class="fas fa-paper-plane"></i>
      {{ submitText }}
    </button>

    <div class="composer-formatting" :aria-label="formattingLabelText">
      <slot name="formatting"></slot>
    </div>

    <div class="composer-secondary-actions">
      <slot name="secondary" :items="secondaryActions"></slot>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { getUiCopy } from '../../forum/registry.js'

defineProps({
  submitDisabled: {
    type: Boolean,
    default: false
  },
  submitText: {
    type: String,
    required: true
  },
  secondaryActions: {
    type: Array,
    default: () => []
  }
})
const formattingLabelText = computed(() => getUiCopy({
  surface: 'composer-formatting-toolbar-label',
})?.text || '格式化工具栏')

defineEmits(['submit'])
</script>

<style scoped>
.composer-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 -20px;
  padding: 10px 20px;
  border-top: 1px solid #dbe2ea;
  flex-wrap: nowrap;
}

.composer-submit {
  border: 0;
  border-radius: 4px;
  padding: 8px 14px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  background: var(--forum-primary-color);
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
}

.composer-submit:disabled {
  cursor: default;
  opacity: 0.6;
}

.composer-submit i {
  font-size: 13px;
}

.composer-formatting {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  white-space: nowrap;
}

.composer-formatting :deep(.composer-tool) {
  position: relative;
  flex-shrink: 0;
}

.composer-formatting :deep(button) {
  border: 0;
  background: transparent;
  color: #5b6776;
  border-radius: 4px;
  min-width: 28px;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}

.composer-formatting :deep(button:hover) {
  background: #e8edf3;
  color: #354152;
}

.composer-formatting :deep(button.is-active) {
  background: #e3ecf5;
  color: #325b88;
}

.composer-formatting :deep(button:disabled) {
  opacity: 0.45;
  cursor: default;
}

.composer-formatting :deep(button i) {
  font-size: 14px;
}

.composer-formatting :deep(button span) {
  font-weight: 700;
  font-size: 14px;
  line-height: 1;
  white-space: nowrap;
}

.composer-secondary-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.composer-secondary-actions :deep(.composer-secondary) {
  border: 0;
  border-radius: 4px;
  padding: 8px 14px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  background: transparent;
  color: #6b7786;
}

.composer-secondary-actions :deep(.composer-secondary:hover) {
  background: #e8edf3;
  color: #425062;
}

@media (max-width: 768px) {
  .composer-toolbar {
    align-items: stretch;
    flex-wrap: wrap;
  }

  .composer-submit,
  .composer-secondary-actions :deep(.composer-secondary) {
    justify-content: center;
  }

  .composer-formatting {
    order: 3;
    flex: 0 0 100%;
    padding-bottom: 2px;
  }
}
</style>
