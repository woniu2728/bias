<template>
  <div class="forum-pagination">
    <button
      type="button"
      class="forum-pagination__button"
      :disabled="currentPage <= 1"
      @click="$emit('change', currentPage - 1)"
    >
      {{ prevText }}
    </button>
    <span class="forum-pagination__info">
      第 {{ currentPage }} / {{ totalPages }} 页
    </span>
    <button
      type="button"
      class="forum-pagination__button"
      :disabled="currentPage >= totalPages"
      @click="$emit('change', currentPage + 1)"
    >
      {{ nextText }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  currentPage: {
    type: Number,
    required: true
  },
  totalPages: {
    type: Number,
    required: true
  },
  prevText: {
    type: String,
    default: '上一页'
  },
  nextText: {
    type: String,
    default: '下一页'
  }
})

defineEmits(['change'])
</script>

<style scoped>
.forum-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  margin-top: 24px;
}

.forum-pagination__button {
  background: var(--forum-bg-elevated);
  border: 1px solid var(--forum-border-color);
  color: var(--forum-text-muted);
}

.forum-pagination__button:hover:not(:disabled) {
  border-color: var(--forum-primary-color);
  color: var(--forum-primary-color);
}

.forum-pagination__info {
  color: var(--forum-text-muted);
  font-size: 13px;
}
</style>
