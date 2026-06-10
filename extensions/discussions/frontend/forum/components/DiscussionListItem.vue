<template>
  <li
    class="discussion-list-item"
    :data-discussion-id="discussion.id"
    :class="{ 'is-sticky': discussion.is_sticky, 'is-unread': discussion.is_unread }"
  >
    <div class="discussion-list-item-content">
      <DiscussionListItemAvatar
        :discussion="discussion"
        :discussion-badges="discussionBadges"
        :build-user-path="buildUserPath"
        :get-user-avatar-color="getUserAvatarColor"
        :get-user-display-name="getUserDisplayName"
        :get-user-initial="getUserInitial"
      />
      <DiscussionListItemMeta
        :discussion="discussion"
        :is-unread="discussion.is_unread"
        :has-new-replies="hasNewReplies"
        :new-reply-count="newReplyCount"
        :build-discussion-path="buildDiscussionPath"
        :build-user-path="buildUserPath"
        :format-relative-time="formatRelativeTime"
      />
      <DiscussionListItemStats :discussion="discussion" :is-unread="discussion.is_unread" />
    </div>
  </li>
</template>

<script setup>

import { toRef } from '@bias/core'
import DiscussionListItemAvatar from './DiscussionListItemAvatar.vue'
import DiscussionListItemMeta from './DiscussionListItemMeta.vue'
import DiscussionListItemStats from './DiscussionListItemStats.vue'
import { useDiscussionListItemState } from '../useDiscussionListItemState'

const props = defineProps({
  discussion: {
    type: Object,
    required: true
  },
  buildDiscussionPath: {
    type: Function,
    required: true
  },
  buildUserPath: {
    type: Function,
    required: true
  },
  formatRelativeTime: {
    type: Function,
    required: true
  },
  getUserAvatarColor: {
    type: Function,
    required: true
  },
  getUserDisplayName: {
    type: Function,
    required: true
  },
  getUserInitial: {
    type: Function,
    required: true
  }
})

const { discussionBadges, hasNewReplies, newReplyCount } = useDiscussionListItemState({
  discussion: toRef(props, 'discussion'),
})
</script>

<style scoped>
.discussion-list-item {
  border-bottom: 1px solid var(--forum-border-soft);
  transition: background 0.2s;
}

.discussion-list-item:hover {
  background: var(--forum-bg-elevated-strong);
}

.discussion-list-item.is-sticky {
  background: #fffbf0;
}

.discussion-list-item.is-sticky:hover {
  background: #fff8e1;
}

.discussion-list-item.is-unread {
  background: #f8fbff;
}

.discussion-list-item.is-unread:hover {
  background: #f1f7fd;
}

.discussion-list-item-content {
  display: flex;
  gap: 16px;
  padding: 12px 26px 12px 26px;
  position: relative;
}

@media (max-width: 768px) {
  .discussion-list-item-content {
    gap: 12px;
    padding: 12px 15px 14px;
  }
}
</style>
