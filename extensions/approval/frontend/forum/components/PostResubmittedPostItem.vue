<template>
  <DiscussionEventPostBase
    :post="post"
    :is-target="isTarget"
    icon="fas fa-reply"
    variant="warm"
    :target-post-number="targetPostNumber"
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
const targetPostNumber = computed(() => props.post.event_data?.target_post_number || '?')
const resubmittedText = computed(() => getUiCopy({
  surface: 'post-event-resubmitted-label',
  targetPostNumber: targetPostNumber.value,
})?.text || `修改后重新提交了第 ${targetPostNumber.value} 楼回复的审核`)
</script>
