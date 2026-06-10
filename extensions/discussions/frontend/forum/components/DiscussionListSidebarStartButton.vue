<template>
  <button
    type="button"
    class="btn-start-discussion"
    :class="{ 'btn-start-discussion--context': Boolean(contextSubject?.color) }"
    :style="startDiscussionButtonStyle"
    @click="$emit('click')"
  >
    <i class="fas fa-edit"></i>
    {{ labelText }}
  </button>
</template>

<script setup>

import { toRef } from '@bias/core'
import { useDiscussionListSidebarStartButtonState } from '../useDiscussionListSidebarStartButtonState'

const props = defineProps({
  contextSubject: {
    type: Object,
    default: null
  },
  startDiscussionButtonStyle: {
    type: Object,
    default: () => ({})
  }
})

defineEmits(['click'])

const { labelText } = useDiscussionListSidebarStartButtonState({
  contextSubject: toRef(props, 'contextSubject'),
})
</script>

<style scoped>
.btn-start-discussion {
  width: 100%;
  padding: 10px 14px;
  background: var(--forum-accent-color);
  color: white;
  border: none;
  border-radius: 3px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: filter 0.2s, background 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  line-height: 20px;
  white-space: nowrap;
  user-select: none;
}

.btn-start-discussion:hover {
  filter: brightness(0.92);
}

.btn-start-discussion--context {
  background: var(--tag-button-bg);
  color: var(--tag-button-text);
}

.btn-start-discussion i {
  font-size: 13px;
}
</style>
