<template>
  <DiscussionEventPostBase
    :post="post"
    :is-target="isTarget"
    :icon="isHidden ? 'fas fa-eye-slash' : 'fas fa-eye'"
    :variant="isHidden ? 'alert' : 'default'"
    :format-absolute-date="formatAbsoluteDate"
    :format-date="formatDate"
    @jump-to-post="$emit('jump-to-post', $event)"
  >
    <template #line>
      <strong>{{ actorName }}</strong>
      <span>{{ hiddenText }}</span>
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
const isHidden = computed(() => Boolean(props.post.event_data?.is_hidden))
const hiddenText = computed(() => getUiCopy({
  surface: 'discussion-event-hidden-label',
  isHidden: isHidden.value,
})?.text || (isHidden.value ? '隐藏了该讨论' : '恢复显示该讨论'))
</script>
