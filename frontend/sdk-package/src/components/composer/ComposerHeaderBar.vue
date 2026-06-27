<template>
  <div class="composer-header">
    <div
      class="composer-title"
      :class="{ 'composer-title--clickable': summaryClickable }"
      @click="$emit('title-click')"
    >
      <span>{{ title }}</span>
      <small>
        <slot name="subtitle">{{ subtitle }}</slot>
      </small>
    </div>
    <div class="composer-controls">
      <button v-if="showSave" type="button" :title="saveDraftTitleText" :disabled="submitting" @click="$emit('save')">
        <i class="far fa-save"></i>
      </button>
      <button
        type="button"
        :title="toggleMinimizedTitleText"
        @click="$emit('toggle-minimized')"
      >
        <i :class="minimized ? 'far fa-window-restore' : minimizeIcon"></i>
      </button>
      <button
        type="button"
        :title="toggleExpandedTitleText"
        @click="$emit('toggle-expanded')"
      >
        <i :class="expanded ? 'fas fa-compress' : 'fas fa-expand'"></i>
      </button>
      <button type="button" :title="closeTitleText" @click="$emit('close')">
        <i class="fas fa-times"></i>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { getUiCopy } from '../../forum/registry.js'

const props = defineProps({
  expanded: {
    type: Boolean,
    default: false
  },
  minimizeIcon: {
    type: String,
    default: 'fas fa-minus'
  },
  minimized: {
    type: Boolean,
    default: false
  },
  showSave: {
    type: Boolean,
    default: false
  },
  submitting: {
    type: Boolean,
    default: false
  },
  subtitle: {
    type: String,
    default: ''
  },
  summaryClickable: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    required: true
  }
})

defineEmits(['close', 'save', 'title-click', 'toggle-expanded', 'toggle-minimized'])

const saveDraftTitleText = computed(() => getUiCopy({
  surface: 'composer-header-save-draft',
  submitting: props.submitting,
})?.text || '保存草稿')

const toggleMinimizedTitleText = computed(() => getUiCopy({
  surface: 'composer-header-toggle-minimized',
  minimized: props.minimized,
})?.text || (props.minimized ? '展开' : '最小化'))

const toggleExpandedTitleText = computed(() => getUiCopy({
  surface: 'composer-header-toggle-expanded',
  expanded: props.expanded,
})?.text || (props.expanded ? '退出全屏' : '全屏'))

const closeTitleText = computed(() => getUiCopy({
  surface: 'composer-header-close',
})?.text || '关闭')
</script>

<style scoped>
.composer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 20px 10px;
  color: #4a5665;
}

.composer-title {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.composer-title--clickable {
  cursor: pointer;
}

.composer-title span,
.composer-title small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.composer-title span {
  font-size: 14px;
  color: #445161;
}

.composer-title small {
  color: #7b8794;
  font-size: 12px;
}

.composer-title small :deep(a) {
  color: inherit;
  text-decoration: none;
}

.composer-title small :deep(a:hover) {
  text-decoration: none;
}

.composer-controls {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.composer-controls button {
  border: 0;
  background: transparent;
  color: #6c7a89;
  border-radius: 4px;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.composer-controls button:hover {
  background: #e8edf3;
  color: #3f4b59;
}

.composer-controls button i {
  font-size: 13px;
}

.composer-controls button:disabled {
  cursor: default;
  opacity: 0.45;
}
</style>
