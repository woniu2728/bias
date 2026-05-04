<template>
  <div :class="containerClass">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      :class="[itemClass, {
        'is-danger': item.tone === 'danger',
        'is-disabled': item.disabled,
      }]"
      :disabled="item.disabled"
      :title="item.disabledReason || item.description || ''"
      @click="$emit('select', item.key)"
    >
      <span :class="`${itemClass}__main`">
        <i v-if="item.icon" :class="item.icon"></i>
        <span>{{ item.label }}</span>
      </span>
      <small v-if="item.description || item.disabledReason">
        {{ item.disabledReason || item.description }}
      </small>
    </button>
  </div>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => []
  },
  containerClass: {
    type: String,
    default: 'forum-action-menu'
  },
  itemClass: {
    type: String,
    default: 'forum-action-menu-item'
  }
})

defineEmits(['select'])
</script>

<style scoped>
.forum-action-menu-item {
  width: 100%;
  margin: 0;
  border: 0;
  background: transparent;
  color: var(--forum-text-muted);
  padding: 9px 10px;
  border-radius: var(--forum-radius-sm);
  text-align: left;
  font-size: var(--forum-font-size-sm);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.forum-action-menu-item__main {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.forum-action-menu-item small {
  color: var(--forum-text-soft);
  font-size: 12px;
  line-height: 1.45;
}

.forum-action-menu-item:hover {
  background: var(--forum-bg-subtle);
}

.forum-action-menu-item.is-danger {
  color: var(--forum-danger-color);
}

.forum-action-menu-item.is-danger:hover {
  background: var(--forum-danger-soft);
}

.forum-action-menu-item.is-disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.forum-action-menu-item.is-disabled:hover {
  background: transparent;
}
</style>
