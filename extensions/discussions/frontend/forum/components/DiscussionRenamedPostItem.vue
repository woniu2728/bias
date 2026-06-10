<template>
  <DiscussionEventPostBase
    :post="post"
    :is-target="isTarget"
    icon="fas fa-heading"
    variant="warm"
    :format-absolute-date="formatAbsoluteDate"
    :format-date="formatDate"
    @jump-to-post="$emit('jump-to-post', $event)"
  >
    <template #line>
      <strong>{{ actorName }}</strong>
      <span>{{ renamedFromText }}</span>
      <span class="event-post-title event-post-title--old">“{{ oldTitle }}”</span>
      <span>{{ renamedToText }}</span>
      <span class="event-post-title">“{{ newTitle }}”</span>
    </template>
  </DiscussionEventPostBase>
</template>

<script setup>

import { computed } from '@bias/core'
import DiscussionEventPostBase from './DiscussionEventPostBase.vue'
import { getUiCopy } from '@bias/forum'

const props = defineProps({
  post: { type: Object, required: true },
  isTarget: { type: Boolean, default: false },
  getUserDisplayName: { type: Function, required: true },
  formatAbsoluteDate: { type: Function, required: true },
  formatDate: { type: Function, required: true }
})

defineEmits(['jump-to-post'])

const actorName = computed(() => props.getUserDisplayName(props.post.user))
const oldTitle = computed(() => props.post.event_data?.old_title || getUiCopy({
  surface: 'discussion-event-renamed-old-title-fallback',
})?.text || '旧标题')
const newTitle = computed(() => props.post.event_data?.new_title || getUiCopy({
  surface: 'discussion-event-renamed-new-title-fallback',
})?.text || '新标题')
const renamedFromText = computed(() => getUiCopy({
  surface: 'discussion-event-renamed-from-label',
})?.text || '将讨论标题从')
const renamedToText = computed(() => getUiCopy({
  surface: 'discussion-event-renamed-to-label',
})?.text || '改为')
</script>

<style scoped>
.event-post-title {
  color: #7a4a16;
  font-weight: 700;
}

.event-post-title--old {
  text-decoration: line-through;
  opacity: 0.72;
}
</style>
