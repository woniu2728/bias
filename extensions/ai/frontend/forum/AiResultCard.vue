<template>
  <section class="AiResultCard">
    <div class="AiResultCard-header">
      <span class="AiResultCard-title">{{ title }}</span>
      <span v-if="modeLabel" class="AiResultCard-mode">{{ modeLabel }}</span>
    </div>
    <p v-if="text" class="AiResultCard-text">{{ text }}</p>
    <div v-if="cards.length" class="AiResultCard-list">
      <div v-for="card in cards" :key="card.title || card.items?.join('|')" class="AiResultCard-section">
        <strong>{{ card.title || '建议' }}</strong>
        <ul>
          <li v-for="item in normalizeItems(card.items)" :key="item">{{ item }}</li>
        </ul>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from '@bias/core'

const props = defineProps({
  result: {
    type: Object,
    default: () => ({}),
  },
  title: {
    type: String,
    default: 'AI 反馈',
  },
})

const text = computed(() => String(props.result?.text || '').trim())
const cards = computed(() => Array.isArray(props.result?.cards) ? props.result.cards : [])
const modeLabel = computed(() => {
  const mode = String(props.result?.mode || '').trim()
  if (mode === 'remote') return '远程模型'
  if (mode === 'fallback') return '本地预览'
  if (mode === 'disabled') return '已关闭'
  return ''
})

function normalizeItems(items) {
  return Array.isArray(items)
    ? items.map(item => String(item || '').trim()).filter(Boolean)
    : []
}
</script>

<style scoped>
.AiResultCard {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--border-color, #dedede);
  border-radius: 8px;
  background: var(--body-bg, #fff);
}

.AiResultCard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.AiResultCard-title {
  font-weight: 700;
  color: var(--heading-color, #222);
}

.AiResultCard-mode {
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--muted-color, #667085);
}

.AiResultCard-text {
  margin: 0;
  line-height: 1.6;
  white-space: pre-wrap;
}

.AiResultCard-list {
  display: grid;
  gap: 10px;
}

.AiResultCard-section {
  display: grid;
  gap: 6px;
}

.AiResultCard-section ul {
  display: grid;
  gap: 4px;
  margin: 0;
  padding-left: 18px;
}
</style>
