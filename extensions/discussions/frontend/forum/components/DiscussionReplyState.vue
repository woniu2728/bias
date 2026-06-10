<template>
  <div class="reply-state-stack">
    <div v-if="replyState?.kind === 'composer'" class="reply-placeholder">
      <button type="button" class="primary" @click="$emit('open-composer')">
        {{ replyState.actionLabel }}
      </button>
      <span v-if="replyState.hint">{{ replyState.hint }}</span>
    </div>
    <div
      v-else-if="replyState?.kind === 'login'"
      class="reply-notice"
      :class="`reply-notice--${replyState.tone || 'warning'}`"
    >
      <router-link :to="replyState.to || '/login'">{{ replyState.linkLabel || '登录' }}</router-link>
      {{ replyState.message }}
    </div>
    <div
      v-else-if="replyState"
      class="reply-notice"
      :class="`reply-notice--${replyState.tone || 'warning'}`"
    >
      {{ replyState.message }}
    </div>

    <div v-if="typingNoticeText" class="reply-typing-notice">
      {{ typingNoticeText }}
    </div>
  </div>
</template>

<script setup>

import { computed } from '@bias/core'
import { getDiscussionReplyState } from '@bias/discussions'
import { getUiCopy } from '@bias/forum'
import { useForumRealtimeStore } from '@bias/realtime'
import { formatDiscussionTypingNotice } from '../discussionTypingState'

const props = defineProps({
  authStore: {
    type: Object,
    required: true
  },
  discussion: {
    type: Object,
    required: true
  },
  isSuspended: {
    type: Boolean,
    default: false
  },
  suspensionNotice: {
    type: String,
    default: ''
  },
  hasActiveComposer: {
    type: Boolean,
    default: false
  },
  typingDiscussionId: {
    type: Number,
    default: 0
  }
})

defineEmits(['open-composer'])

const forumRealtimeStore = useForumRealtimeStore()

const replyState = computed(() => getDiscussionReplyState({
  authStore: props.authStore,
  discussion: props.discussion,
  isSuspended: props.isSuspended,
  suspensionNotice: props.suspensionNotice,
  hasActiveComposer: props.hasActiveComposer,
  surface: 'discussion-reply',
}))

const typingUsers = computed(() => forumRealtimeStore.getTypingUsers(props.typingDiscussionId))

const typingNoticeText = computed(() => {
  if (!typingUsers.value.length) return ''

  const usernames = typingUsers.value.map(item => item.username).filter(Boolean)
  return getUiCopy({
    surface: 'discussion-reply-typing-notice',
    count: usernames.length,
    usernames,
  })?.text || formatDiscussionTypingNotice(usernames)
})
</script>

<style scoped>
.reply-state-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.reply-placeholder {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
  background: var(--forum-bg-elevated-strong);
  border: 1px dashed var(--forum-border-strong);
  border-radius: var(--forum-radius-md);
  margin-bottom: 20px;
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
}

.reply-notice {
  text-align: center;
  padding: 20px;
  border-radius: var(--forum-radius-sm);
  line-height: 1.6;
}

.reply-notice--warning {
  background: var(--forum-warning-bg-strong);
  color: var(--forum-warning-color);
}

.reply-typing-notice {
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
  padding: 0 2px;
}

@media (max-width: 768px) {
  .reply-placeholder,
  .reply-notice {
    margin-left: 15px;
    margin-right: 15px;
  }

  .reply-placeholder {
    flex-direction: column;
    align-items: flex-start;
    padding: 14px 15px;
    gap: 8px;
  }

  .reply-notice {
    padding: 14px 15px;
    font-size: 13px;
  }
}
</style>
