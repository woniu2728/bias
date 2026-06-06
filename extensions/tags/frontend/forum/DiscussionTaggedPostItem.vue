<template>
  <DiscussionEventPostBase
    :post="post"
    :is-target="isTarget"
    icon="fas fa-tags"
    variant="warm"
    :format-absolute-date="formatAbsoluteDate"
    :format-date="formatDate"
    @jump-to-post="$emit('jump-to-post', $event)"
  >
    <template #line>
      <strong>{{ actorName }}</strong>
      <span>{{ updatedText }}</span>
      <span v-if="addedTags.length" class="tag-change tag-change--added">{{ addedPrefixText }} {{ addedTags.join('、') }}</span>
      <span v-if="removedTags.length" class="tag-change tag-change--removed">{{ removedPrefixText }} {{ removedTags.join('、') }}</span>
    </template>
  </DiscussionEventPostBase>
</template>

<script setup>
import {
  computed,
  DiscussionEventPostBase,
  getUiCopy,
} from '@bias/forum'

const props = defineProps({
  post: { type: Object, required: true },
  isTarget: { type: Boolean, default: false },
  getUserDisplayName: { type: Function, required: true },
  formatAbsoluteDate: { type: Function, required: true },
  formatDate: { type: Function, required: true }
})

defineEmits(['jump-to-post'])

const actorName = computed(() => props.getUserDisplayName(props.post.user))
const addedTags = computed(() => props.post.event_data?.added_tags || [])
const removedTags = computed(() => props.post.event_data?.removed_tags || [])
const updatedText = computed(() => getUiCopy({
  surface: 'discussion-event-tagged-label',
})?.text || '更新了讨论标签')
const addedPrefixText = computed(() => getUiCopy({
  surface: 'discussion-event-tagged-added-prefix',
})?.text || '新增')
const removedPrefixText = computed(() => getUiCopy({
  surface: 'discussion-event-tagged-removed-prefix',
})?.text || '移除')
</script>

<style scoped>
.tag-change {
  font-weight: 700;
}

.tag-change--added {
  color: #1f7a46;
}

.tag-change--removed {
  color: #9a4b4b;
}
</style>
