<template>
  <div class="discussion-list-item-main">
    <div class="discussion-title-row">
      <router-link
        :to="buildDiscussionPath(discussion)"
        class="discussion-list-item-title"
        :class="{ 'discussion-list-item-title--unread': isUnread }"
      >
        {{ discussion.title }}
      </router-link>
      <span v-if="hasNewReplies" class="discussion-live-pill">
        {{ newReplyCount > 1 ? `${newReplyCount} 条新回复` : '有新回复' }}
      </span>
      <ForumStateBadge
        v-for="badge in discussionStateBadges"
        :key="badge.key"
        :label="badge.label"
        :tone="badge.tone"
        :size="badge.size || 'sm'"
        :icon="badge.icon || ''"
        :title="badge.title || ''"
      />
    </div>

    <p v-if="feedbackNote" class="feedback-note">
      {{ feedbackNote.text }}
    </p>

    <ul class="discussion-list-item-info">
      <li
        v-for="item in presentationItems"
        :key="item.key"
        class="item-extension"
        :class="item.className || ''"
      >
        <component
          :is="item.component"
          v-if="item.component"
          v-bind="item.componentProps"
        />
      </li>
      <li class="item-author">
        <router-link :to="buildUserPath(discussion.user)" class="username">
          {{ discussion.user?.display_name || discussion.user?.username }}
        </router-link>
        {{ createdAtText }}
      </li>
      <li v-if="discussion.last_posted_at" class="item-last-post">
        <i class="fas fa-reply"></i>
        {{ lastPostedAtText }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { toRef } from '@bias/core'
import { ForumStateBadge } from '@bias/forum'
import { useDiscussionListItemMetaState } from '../useDiscussionListItemMetaState'

const props = defineProps({
  discussion: {
    type: Object,
    required: true
  },
  isUnread: {
    type: Boolean,
    default: false
  },
  hasNewReplies: {
    type: Boolean,
    default: false
  },
  newReplyCount: {
    type: Number,
    default: 0
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
  }
})

const {
  createdAtText,
  discussionStateBadges,
  feedbackNote,
  lastPostedAtText,
  presentationItems,
} = useDiscussionListItemMetaState({
  discussion: toRef(props, 'discussion'),
  formatRelativeTime: props.formatRelativeTime,
})
</script>

<style scoped>
.discussion-list-item-main {
  flex: 1;
  min-width: 0;
}

.discussion-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  margin-bottom: 3px;
}

.discussion-list-item-title {
  display: block;
  font-size: var(--forum-font-size-lg);
  font-weight: normal;
  color: var(--forum-text-color);
  margin: 0;
  line-height: 1.3;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  overflow-wrap: anywhere;
}

.discussion-list-item-title:hover {
  color: var(--forum-primary-color);
  text-decoration: none;
}

.discussion-list-item-title--unread {
  font-weight: 600;
  color: var(--forum-text-color);
}

.discussion-live-pill {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: #e8f4ee;
  color: #1f7a45;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.discussion-list-item-info {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 11px;
  color: var(--forum-text-soft);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.discussion-list-item-info > li {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.item-extension {
  display: flex;
  gap: 6px;
  min-width: 0;
  max-width: 100%;
}

.feedback-note {
  margin: 0 0 6px;
  color: #9a5050;
  font-size: 12px;
  line-height: 1.6;
}

.username {
  font-weight: bold;
  color: #666;
  min-width: 0;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-last-post i {
  font-size: 10px;
}

@media (max-width: 768px) {
  .discussion-list-item-main {
    padding-right: 52px;
  }

  .discussion-title-row {
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 6px;
    margin-bottom: 5px;
  }

  .discussion-live-pill {
    min-height: 20px;
    font-size: 10px;
  }

  .discussion-list-item-title {
    font-size: 14px;
    line-height: 1.35;
    white-space: normal;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    word-break: break-word;
  }

  .feedback-note {
    margin-bottom: 8px;
    font-size: 11px;
  }

  .discussion-list-item-info {
    gap: 6px 8px;
    font-size: 12px;
    line-height: 1.5;
  }

  .discussion-list-item-info > li {
    max-width: 100%;
  }

  .item-extension {
    flex-wrap: wrap;
  }

  .item-author,
  .item-last-post {
    flex: 1 1 100%;
  }

  .username {
    max-width: min(58vw, 220px);
  }

  :deep(.forum-tag-badge) {
    max-width: min(52vw, 180px);
  }

  :deep(.forum-state-badge) {
    font-size: 10px;
  }
}
</style>
