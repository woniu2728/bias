<template>
  <Teleport to="body">
    <div
      class="composer-emoji-autocomplete"
      :style="styleObject"
      role="listbox"
      aria-label="表情建议"
      ref="pickerRef"
      @mousedown.stop
      @click.stop
    >
      <button
        v-for="(item, index) in items"
        :key="`${item.emoji}-${item.matchedAlias || item.name}`"
        :ref="element => setItemRef(element, index)"
        type="button"
        class="composer-emoji-autocomplete-item"
        :class="{ 'is-active': index === activeIndex }"
        @mouseenter="$emit('highlight', index)"
        @click="$emit('select', item)"
      >
        <span class="composer-emoji-autocomplete-icon">{{ item.emoji }}</span>
        <span class="composer-emoji-autocomplete-main">
          <strong>{{ item.name }}</strong>
          <small v-if="item.matchedAlias">:{{ item.matchedAlias }}</small>
        </span>
      </button>
    </div>
  </Teleport>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  },
  activeIndex: {
    type: Number,
    default: 0
  },
  styleObject: {
    type: Object,
    default: () => ({})
  }
})

defineEmits(['select', 'highlight'])

const pickerRef = ref(null)
const itemRefs = ref([])

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
.composer-emoji-autocomplete {
  position: fixed;
  width: min(320px, calc(100vw - 32px));
  max-height: min(320px, calc(100vh - 32px));
  overflow-y: auto;
  border: 1px solid #d8e0e8;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 14px 32px rgba(31, 45, 61, 0.16);
  z-index: 1200;
}

.composer-emoji-autocomplete-item {
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

.composer-emoji-autocomplete-item + .composer-emoji-autocomplete-item {
  border-top: 1px solid #eef2f6;
}

.composer-emoji-autocomplete-item:hover,
.composer-emoji-autocomplete-item.is-active {
  background: #edf4fb;
}

.composer-emoji-autocomplete-icon {
  width: 28px;
  flex-shrink: 0;
  font-size: 20px;
  line-height: 1;
  text-align: center;
}

.composer-emoji-autocomplete-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.composer-emoji-autocomplete-main strong,
.composer-emoji-autocomplete-main small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.composer-emoji-autocomplete-main strong {
  color: #2f3b47;
  font-size: 13px;
  font-weight: 600;
}

.composer-emoji-autocomplete-main small {
  color: #7b8794;
  font-size: 12px;
}
</style>
