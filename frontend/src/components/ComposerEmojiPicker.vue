<template>
  <Teleport to="body">
    <div
      class="composer-emoji-picker"
      :style="styleObject"
      role="dialog"
      aria-label="选择表情"
      @mousedown.stop
      @click.stop
    >
      <div class="composer-emoji-search">
        <input
          v-model.trim="query"
          type="text"
          class="composer-emoji-search-input"
          placeholder="搜索表情，例如：开心 / heart / fire"
        />
      </div>

      <div class="composer-emoji-tabs">
        <button
          v-for="group in groups"
          :key="group.key"
          type="button"
          :class="{ 'is-active': activeKey === group.key }"
          @click="activeKey = group.key"
        >
          {{ group.label }}
        </button>
      </div>

      <div class="composer-emoji-summary">
        {{ query ? `搜索结果 ${visibleItems.length} 项` : `${activeGroup.label || '表情'} ${visibleItems.length} 项` }}
      </div>

      <div v-if="visibleItems.length" class="composer-emoji-grid">
        <button
          v-for="item in visibleItems"
          :key="`${item.groupKey || activeGroup.key}-${item.emoji}`"
          type="button"
          :title="buildEmojiTitle(item)"
          @click="$emit('select', item.emoji)"
        >
          {{ item.emoji }}
        </button>
      </div>
      <div v-else class="composer-emoji-empty">没有匹配的表情</div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  groups: {
    type: Array,
    default: () => []
  },
  styleObject: {
    type: Object,
    default: () => ({})
  }
})

defineEmits(['select'])

const activeKey = ref(props.groups[0]?.key || '')
const query = ref('')

watch(
  () => props.groups,
  groups => {
    if (!groups.some(group => group.key === activeKey.value)) {
      activeKey.value = groups[0]?.key || ''
    }
  },
  { deep: true }
)

const activeGroup = computed(() => {
  return props.groups.find(group => group.key === activeKey.value) || props.groups[0] || { key: '', label: '', emojis: [] }
})

const allItems = computed(() => {
  const uniqueItems = new Map()

  props.groups.forEach(group => {
    ;(group.emojis || []).forEach(item => {
      if (!item?.emoji || uniqueItems.has(item.emoji)) return
      uniqueItems.set(item.emoji, {
        ...item,
        groupKey: group.key,
        groupLabel: group.label
      })
    })
  })

  return Array.from(uniqueItems.values())
})

const visibleItems = computed(() => {
  const normalizedQuery = normalizeSearchText(query.value)
  if (!normalizedQuery) {
    return activeGroup.value.emojis || []
  }

  return [...allItems.value]
    .map(item => ({
      ...item,
      score: getEmojiSearchScore(item, normalizedQuery)
    }))
    .filter(item => item.score > 0)
    .sort((left, right) => right.score - left.score || left.name.localeCompare(right.name, 'zh-CN'))
})

function buildEmojiTitle(item) {
  const suffix = (item.keywords || []).slice(0, 4).join(' / ')
  return suffix ? `${item.name} · ${suffix}` : item.name
}

function getEmojiSearchScore(item, queryText) {
  const name = normalizeSearchText(item.name)
  const keywords = (item.keywords || []).map(keyword => normalizeSearchText(keyword))
  const groupLabel = normalizeSearchText(item.groupLabel)

  if (item.emoji === queryText) return 200
  if (name === queryText) return 180
  if (keywords.includes(queryText)) return 160
  if (name.startsWith(queryText)) return 120
  if (keywords.some(keyword => keyword.startsWith(queryText))) return 100
  if (name.includes(queryText)) return 80
  if (keywords.some(keyword => keyword.includes(queryText))) return 60
  if (groupLabel.includes(queryText)) return 40
  return 0
}

function normalizeSearchText(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/\s+/g, '')
}
</script>

<style scoped>
.composer-emoji-picker {
  position: fixed;
  width: min(420px, calc(100vw - 32px));
  padding: 10px;
  border: 1px solid #d8e0e8;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 14px 32px rgba(31, 45, 61, 0.16);
  z-index: 1200;
}

.composer-emoji-search {
  margin-bottom: 10px;
}

.composer-emoji-search-input {
  width: 100%;
  height: 36px;
  padding: 0 12px;
  border: 1px solid #d8e0e8;
  border-radius: 8px;
  background: #f9fbfd;
  font-size: 13px;
  color: #354152;
}

.composer-emoji-search-input:focus {
  outline: none;
  border-color: #a9bfd5;
  background: #ffffff;
}

.composer-emoji-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  overflow-x: auto;
}

.composer-emoji-tabs button,
.composer-emoji-grid button {
  border: 0;
  background: transparent;
  cursor: pointer;
}

.composer-emoji-tabs button {
  padding: 6px 10px;
  border-radius: 999px;
  color: #617182;
  font-size: 12px;
  white-space: nowrap;
}

.composer-emoji-tabs button.is-active,
.composer-emoji-tabs button:hover {
  background: #edf4fb;
  color: #355f8c;
}

.composer-emoji-summary {
  margin-bottom: 8px;
  color: #6c7a89;
  font-size: 12px;
}

.composer-emoji-grid {
  display: grid;
  grid-template-columns: repeat(9, minmax(0, 1fr));
  gap: 6px;
  max-height: min(280px, calc(100vh - 220px));
  overflow-y: auto;
  padding-right: 2px;
}

.composer-emoji-grid button {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 8px;
  font-size: 20px;
  line-height: 1;
}

.composer-emoji-grid button:hover {
  background: #eef3f8;
}

.composer-emoji-empty {
  padding: 24px 12px;
  color: #7b8794;
  font-size: 13px;
  text-align: center;
}

@media (max-width: 768px) {
  .composer-emoji-picker {
    width: min(420px, calc(100vw - 48px));
  }

  .composer-emoji-grid {
    grid-template-columns: repeat(8, minmax(0, 1fr));
  }
}
</style>
