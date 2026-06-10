<template>
  <DiscussionEventPostBase
    :post="post"
    :is-target="isTarget"
    :icon="isHidden ? 'fas fa-eye-slash' : 'fas fa-eye'"
    :variant="isHidden ? 'alert' : 'default'"
    :target-post-number="targetPostNumber"
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
const targetPostNumber = computed(() => props.post.event_data?.target_post_number || '?')
const hiddenText = computed(() => getUiCopy({
  surface: 'post-event-hidden-label',
  isHidden: isHidden.value,
  targetPostNumber: targetPostNumber.value,
})?.text || (isHidden.value ? `隐藏了第 ${targetPostNumber.value} 楼回复` : `恢复显示第 ${targetPostNumber.value} 楼回复`))
</script>
