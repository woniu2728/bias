<template>
  <section class="result-section">
    <div class="section-header">
      <h2>{{ title }}</h2>
      <button
        v-if="showMore"
        type="button"
        class="section-link"
        @click="$emit('show-more')"
      >
        {{ showMoreText }}
      </button>
    </div>
    <div class="result-list">
      <slot></slot>
    </div>
  </section>
</template>

<script setup>
import { computed } from '@bias/core'
import { getUiCopy } from '@bias/forum'

const props = defineProps({
  showMore: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    required: true
  }
})

defineEmits(['show-more'])

const showMoreText = computed(() => getUiCopy({
  surface: 'search-result-section-show-more',
  title: props.title,
})?.text || '查看全部')
</script>

<style scoped>
.result-section + .result-section {
  margin-top: 20px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.section-header h2 {
  font-size: 20px;
  color: var(--forum-text-color);
  min-width: 0;
  overflow-wrap: anywhere;
}

.section-link {
  padding: 0;
  background: transparent;
  color: var(--forum-primary-color);
  font-size: 13px;
  font-weight: 600;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@media (max-width: 520px) {
  .section-header {
    gap: 12px;
    align-items: flex-start;
  }

  .section-header h2 {
    font-size: 18px;
  }

  .section-link {
    flex: 0 0 auto;
  }
}
</style>
