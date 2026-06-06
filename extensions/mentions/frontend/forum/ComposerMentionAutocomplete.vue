<template>
  <Teleport to="body">
    <div
      ref="pickerRef"
      class="composer-mention-picker"
      :style="styleObject"
      role="listbox"
      :aria-label="pickerLabelText"
      @mousedown.stop
      @click.stop
    >
      <div v-if="loading" class="composer-mention-state">{{ loadingStateText }}</div>
      <div v-else-if="!items.length" class="composer-mention-state">{{ emptyStateText }}</div>
      <button
        v-for="(item, index) in items"
        v-else
        :key="item.id"
        :ref="element => setItemRef(element, index)"
        type="button"
        class="composer-mention-item"
        :class="{ 'is-active': index === activeIndex }"
        @mouseenter="$emit('highlight', index)"
        @click="$emit('select', item)"
      >
        <div class="composer-mention-avatar">
          <img v-if="item.avatar_url" :src="item.avatar_url" :alt="item.username" />
          <span v-else>{{ (item.display_name || item.username || '?').charAt(0).toUpperCase() }}</span>
        </div>
        <div class="composer-mention-main">
          <strong>{{ item.display_name || item.username }}</strong>
          <small>@{{ item.username }}</small>
        </div>
      </button>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, ref, watch } from '@bias/forum'
import { getStateBlock, getUiCopy } from '@bias/forum'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  },
  activeIndex: {
    type: Number,
    default: 0
  },
  loading: {
    type: Boolean,
    default: false
  },
  styleObject: {
    type: Object,
    default: () => ({})
  }
})

defineEmits(['select', 'highlight'])

const pickerRef = ref(null)
const itemRefs = ref([])
const pickerLabelText = computed(() => getUiCopy({
  surface: 'composer-mention-picker-label',
})?.text || '提及用户')
const loadingStateText = computed(() => {
  const stateBlock = getStateBlock({
    surface: 'composer-mention-loading',
    loading: props.loading,
    itemCount: props.items.length,
  })

  return stateBlock?.text || '搜索中...'
})
const emptyStateText = computed(() => {
  const stateBlock = getStateBlock({
    surface: 'composer-mention-empty',
    loading: props.loading,
    itemCount: props.items.length,
  })

  return stateBlock?.text || '没有匹配的用户'
})

watch(
  () => [props.activeIndex, props.items.length],
  () => {
    nextTick(() => {
      const container = pickerRef.value
      const activeItem = itemRefs.value[props.activeIndex]
      if (!container || !activeItem) return

      const itemTop = activeItem.offsetTop
      const itemBottom = itemTop + activeItem.offsetHeight
      const visibleTop = container.scrollTop
      const visibleBottom = visibleTop + container.clientHeight

      if (itemTop < visibleTop) {
        container.scrollTop = itemTop
        return
      }

      if (itemBottom > visibleBottom) {
        container.scrollTop = itemBottom - container.clientHeight
      }
    })
  },
  { immediate: true }
)

function setItemRef(element, index) {
  if (!element) {
    delete itemRefs.value[index]
    return
  }

  itemRefs.value[index] = element
}
</script>

<style scoped>
.composer-mention-picker {
  position: fixed;
  width: min(320px, calc(100vw - 32px));
  max-height: min(280px, calc(100vh - 32px));
  overflow-y: auto;
  border: 1px solid #d8e0e8;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 14px 32px rgba(31, 45, 61, 0.16);
  z-index: 1200;
}

.composer-mention-state {
  padding: 12px 14px;
  color: #6c7a89;
  font-size: 13px;
}

.composer-mention-item {
  width: 100%;
  border: 0;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  text-align: left;
}

.composer-mention-item + .composer-mention-item {
  border-top: 1px solid #eef2f6;
}

.composer-mention-item:hover,
.composer-mention-item.is-active {
  background: #edf4fb;
}

.composer-mention-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  overflow: hidden;
  background: #4d698e;
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 700;
}

.composer-mention-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.composer-mention-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.composer-mention-main strong,
.composer-mention-main small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.composer-mention-main strong {
  color: #2f3b47;
  font-size: 13px;
}

.composer-mention-main small {
  color: #7b8794;
  font-size: 12px;
}
</style>
