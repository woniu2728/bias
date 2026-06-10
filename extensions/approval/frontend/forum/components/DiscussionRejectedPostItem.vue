<template>
  <DiscussionEventPostBase
    :post="post"
    :is-target="isTarget"
    icon="fas fa-ban"
    variant="alert"
    :format-absolute-date="formatAbsoluteDate"
    :format-date="formatDate"
    @jump-to-post="$emit('jump-to-post', $event)"
  >
    <template #line>
      <strong>{{ actorName }}</strong>
      <span>{{ rejectedText }}</span>
      <span v-if="note">{{ notePrefixText }}{{ note }}</span>
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
const note = computed(() => String(props.post.event_data?.note || '').trim())
const rejectedText = computed(() => getUiCopy({
  surface: 'discussion-event-rejected-label',
})?.text || '拒绝了该讨论的审核')
const notePrefixText = computed(() => getUiCopy({
  surface: 'discussion-event-note-prefix',
})?.text || '理由：')
</script>
