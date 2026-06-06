<template>
  <div class="tag-cloud">
    <TagBadge
      v-for="tag in tags"
      :key="tag.id"
      :tag="tag"
      variant="soft"
    />
  </div>
</template>

<script setup>
import TagBadge from './TagBadge.vue'

defineProps({
  tags: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped>
.tag-cloud {
  margin-top: 22px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
</style>
