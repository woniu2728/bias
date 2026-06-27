<template>
  <div class="ForumLoadMoreButton" :class="{ 'ForumLoadMoreButton--compact': compact }">
    <button
      type="button"
      class="ForumLoadMoreButton-button secondary"
      :disabled="disabled || loading"
      @click="$emit('click')"
    >
      {{ loading ? loadingText : text }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  text: {
    type: String,
    default: '加载更多'
  },
  loadingText: {
    type: String,
    default: '加载中...'
  },
  loading: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  },
  compact: {
    type: Boolean,
    default: false
  }
})

defineEmits(['click'])
</script>

<style scoped>
.ForumLoadMoreButton {
  text-align: center;
  padding: 20px;
  border-top: 1px solid var(--forum-border-color);
}

.ForumLoadMoreButton--compact {
  padding: 0;
  border-top: 0;
}

.ForumLoadMoreButton-button {
  min-width: 136px;
}
</style>
