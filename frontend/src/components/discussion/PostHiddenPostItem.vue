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
      <span>{{ isHidden ? `隐藏了第 ${targetPostNumber} 楼回复` : `恢复显示第 ${targetPostNumber} 楼回复` }}</span>
    </template>
  </DiscussionEventPostBase>
</template>

<script setup>
import { computed } from 'vue'
import DiscussionEventPostBase from '@/components/discussion/DiscussionEventPostBase.vue'

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
</script>
