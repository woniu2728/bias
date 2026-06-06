<template>
  <div class="discussion-tag-labels">
    <TagBadge
      v-for="tag in tags"
      :key="tag.id"
      :tag="tag"
      :size="size"
      :max-width="maxWidth"
    />
  </div>
</template>

<script setup>
import TagBadge from './TagBadge.vue'

defineProps({
  tags: { type: Array, default: () => [] },
  size: { type: String, default: 'sm' },
  maxWidth: { type: String, default: '160px' },
})
</script>

<style scoped>
.discussion-tag-labels {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
  max-width: 100%;
}
</style>
