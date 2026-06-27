<template>
  <nav v-if="total > limit" class="AdminPagination" aria-label="分页">
    <button
      type="button"
      class="Button"
      :disabled="page <= 1 || disabled"
      @click="$emit('change', page - 1)"
    >
      <i class="fas fa-angle-left"></i>
      <span>上一页</span>
    </button>
    <span class="AdminPagination-info">
      第 {{ page }} 页，共 {{ totalPages }} 页
    </span>
    <button
      type="button"
      class="Button"
      :disabled="page >= totalPages || disabled"
      @click="$emit('change', page + 1)"
    >
      <span>下一页</span>
      <i class="fas fa-angle-right"></i>
    </button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  page: {
    type: Number,
    required: true
  },
  total: {
    type: Number,
    default: 0
  },
  limit: {
    type: Number,
    default: 20
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

defineEmits(['change'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.limit)))
</script>

<style scoped>
.AdminPagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 18px;
  color: var(--forum-text-muted);
}

.AdminPagination .Button {
  min-width: 104px;
  justify-content: center;
}

.AdminPagination-info {
  font-size: var(--forum-font-size-md);
  color: var(--forum-text-muted);
  white-space: nowrap;
}

@media (max-width: 768px) {
  .AdminPagination {
    flex-direction: column;
    align-items: stretch;
  }

  .AdminPagination .Button {
    width: 100%;
  }

  .AdminPagination-info {
    text-align: center;
  }
}
</style>
