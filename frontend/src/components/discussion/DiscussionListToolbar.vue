<template>
  <div class="index-toolbar">
    <ul class="index-toolbar-view">
      <li v-for="option in normalizedSortOptions" :key="option.code">
        <button
          type="button"
          class="btn-view"
          :class="{ active: sortBy === option.code }"
          :title="option.description || option.label"
          @click="$emit('change-sort', option.code)"
        >
          <i v-if="option.icon" :class="option.icon"></i>
          {{ option.label }}
        </button>
      </li>
    </ul>

    <ul class="index-toolbar-action">
      <li v-if="authStore.isAuthenticated">
        <button
          type="button"
          class="btn-mark-read"
          :disabled="markingAllRead"
          title="全部标记为已读"
          @click="$emit('mark-all-read')"
        >
          <i class="fas fa-check-double"></i>
        </button>
      </li>
      <li>
        <button
          type="button"
          class="btn-refresh"
          title="刷新"
          :disabled="refreshing"
          @click="$emit('refresh')"
        >
          <i class="fas fa-sync-alt" :class="{ 'fa-spin': refreshing }"></i>
        </button>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  authStore: {
    type: Object,
    required: true
  },
  sortBy: {
    type: String,
    default: 'latest'
  },
  sortOptions: {
    type: Array,
    default: () => []
  },
  markingAllRead: {
    type: Boolean,
    default: false
  },
  refreshing: {
    type: Boolean,
    default: false
  }
})

defineEmits(['change-sort', 'change-filter', 'change-search', 'mark-all-read', 'refresh'])

const normalizedSortOptions = computed(() => {
  if (props.sortOptions.length) {
    return props.sortOptions
  }

  return [
    { code: 'latest', label: '最新活跃', icon: 'fas fa-clock' },
    { code: 'newest', label: '新主题', icon: 'fas fa-sparkles' },
    { code: 'top', label: '热门', icon: 'fas fa-fire' },
  ]
})
</script>

<style scoped>
.index-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 26px;
  border-bottom: 1px solid var(--forum-border-color);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(250, 252, 253, 0.92) 100%);
}
.index-toolbar-view,
.index-toolbar-action {
  display: flex;
  gap: 5px;
  list-style: none;
  padding: 0;
  margin: 0;
}

.btn-view {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--forum-bg-subtle);
  border: none;
  color: var(--forum-text-muted);
  font-size: 13px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: var(--forum-radius-pill);
  transition: all 0.15s;
  font-weight: 500;
}

.btn-view:hover {
  background: #dbe5ed;
  color: var(--forum-text-color);
}

.btn-view.active {
  background: var(--forum-primary-color);
  color: var(--forum-text-inverse);
}

.btn-refresh,
.btn-mark-read {
  background: none;
  border: none;
  color: var(--forum-text-soft);
  font-size: 14px;
  cursor: pointer;
  padding: 6px 10px;
  border-radius: var(--forum-radius-pill);
  transition: all 0.15s;
}

.btn-refresh:hover,
.btn-mark-read:hover {
  background: var(--forum-bg-subtle);
  color: var(--forum-text-color);
}

.btn-refresh:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-mark-read:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .index-toolbar {
    flex-wrap: nowrap;
    gap: 10px;
    padding: 12px 15px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .index-toolbar-view,
  .index-toolbar-action {
    flex-wrap: nowrap;
    flex-shrink: 0;
  }

  .index-toolbar-view::-webkit-scrollbar,
  .index-toolbar-action::-webkit-scrollbar {
    display: none;
  }

  .index-toolbar-view,
  .index-toolbar-action {
    overflow-x: auto;
    scrollbar-width: none;
  }

  .btn-view,
  .btn-refresh,
  .btn-mark-read {
    min-height: 34px;
    border-radius: 999px;
  }

  .btn-view {
    padding: 6px 11px;
    font-size: 12px;
    white-space: nowrap;
  }
}
</style>
