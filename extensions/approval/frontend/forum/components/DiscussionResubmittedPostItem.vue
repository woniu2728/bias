<template>
  <DiscussionEventPostBase
    :post="post"
    :is-target="isTarget"
    icon="fas fa-rotate-right"
    variant="warm"
    :format-absolute-date="formatAbsoluteDate"
    :format-date="formatDate"
    @jump-to-post="$emit('jump-to-post', $event)"
  >
    <template #line>
      <strong>{{ actorName }}</strong>
      <span>{{ resubmittedText }}</span>
    </template>
  </DiscussionEventPostBase>
</template>

<script setup>
import { computed } from '@bias/core'
import { getUiCopy } from '@bias/forum'
import { DiscussionEventPostBase } from '@bias/discussions'

const props = defineProps({
  post: { type: Object, required: true },
  isTarget: { type: Boolean, default: false },
  getUserDisplayName: { type: Function, required: true },
  formatAbsoluteDate: { type: Function, required: true },
  formatDate: { type: Function, required: true },
})

defineEmits(['jump-to-post'])

const actorName = computed(() => props.getUserDisplayName(props.post.user))
const resubmittedText = computed(() => getUiCopy({
  surface: 'discussion-event-resubmitted-label',
})?.text || '修改后重新提交了该讨论的审核')
</script>
