<template>
  <div class="composer-preview">
    <div class="composer-preview-header">
      <span>{{ previewTitleText }}</span>
      <small>{{ statusText }}</small>
    </div>
    <div v-if="loading" class="composer-preview-loading">{{ loadingText }}</div>
    <div
      v-else
      class="composer-preview-body post-body"
      v-html="html || emptyHtml"
    ></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { getUiCopy } from '../../forum/registry.js'

defineProps({
  html: {
    type: String,
    default: ''
  },
  loading: {
    type: Boolean,
    default: false
  },
  statusText: {
    type: String,
    default: ''
  }
})
const loadingText = computed(() => getUiCopy({
  surface: 'composer-preview-panel-loading',
})?.text || '正在生成预览...')
const previewTitleText = computed(() => getUiCopy({
  surface: 'composer-preview-panel-title',
})?.text || '预览')
const emptyHtml = computed(() => {
  const text = getUiCopy({
    surface: 'composer-preview-panel-empty',
  })?.text || '输入内容后即可查看预览'

  return `<p class="composer-preview-empty">${escapeHtml(text)}</p>`
})

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
</script>

<style scoped>
.composer-preview {
  display: flex;
  flex: 1;
  min-height: 120px;
  flex-direction: column;
  padding: 4px 0 12px;
}

.composer-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  color: #5c6d7d;
  font-size: 13px;
}

.composer-preview-loading,
.composer-preview-empty {
  color: #7a8794;
  font-size: 14px;
}

.composer-preview-body {
  flex: 1;
  overflow-y: auto;
  line-height: 1.7;
}
</style>
