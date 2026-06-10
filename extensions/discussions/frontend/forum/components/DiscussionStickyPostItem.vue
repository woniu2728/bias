<template>
  <DiscussionEventPostBase
    :post="post"
    :is-target="isTarget"
    icon="fas fa-thumbtack"
    variant="warm"
    :format-absolute-date="formatAbsoluteDate"
    :format-date="formatDate"
    @jump-to-post="$emit('jump-to-post', $event)"
  >
    <template #line>
      <strong>{{ actorName }}</strong>
      <span>{{ stickyText }}</span>
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
const isSticky = computed(() => Boolean(props.post.event_data?.is_sticky))
const stickyText = computed(() => getUiCopy({
  surface: 'discussion-event-sticky-label',
  isSticky: isSticky.value,
})?.text || (isSticky.value ? '置顶了该讨论' : '取消了该讨论的置顶状态'))
</script>
