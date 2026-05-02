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
      <span v-if="discussion.approval_status === 'pending'" class="approval-pill">待审核</span>
      <span v-else-if="discussion.approval_status === 'rejected'" class="approval-pill approval-pill--rejected">已拒绝</span>
      <span v-if="discussion.is_unread" class="unread-pill">{{ discussion.unread_count }} 条未读</span>
      <span v-if="discussion.is_subscribed" class="subscription-pill">已关注</span>
    </div>

    <p v-if="discussion.approval_status === 'rejected' && discussion.approval_note" class="approval-note">
      审核反馈：{{ discussion.approval_note }}
    </p>

    <ul class="discussion-list-item-info">
      <li v-if="discussion.tags.length" class="item-tags">
        <router-link
          v-for="tag in discussion.tags"
          :key="tag.id"
          :to="buildTagPath(tag)"
          class="tag-label"
          :style="{ backgroundColor: tag.color }"
        >
          {{ tag.name }}
        </router-link>
      </li>
      <li class="item-author">
        <router-link :to="buildUserPath(discussion.user)" class="username">
          {{ discussion.user?.display_name || discussion.user?.username }}
        </router-link>
        发起于 {{ formatRelativeTime(discussion.created_at) }}
      </li>
      <li v-if="discussion.last_posted_at" class="item-last-post">
        <i class="fas fa-reply"></i>
        最后回复 {{ formatRelativeTime(discussion.last_posted_at) }}
      </li>
    </ul>
  </div>
</template>

<script setup>
defineProps({
  discussion: {
    type: Object,
    required: true
  },
  isUnread: {
    type: Boolean,
    default: false
  },
  buildDiscussionPath: {
    type: Function,
    required: true
  },
  buildTagPath: {
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

.item-tags {
  display: flex;
  gap: 6px;
  min-width: 0;
  max-width: 100%;
}

.tag-label {
  display: inline-flex;
  min-width: 0;
  max-width: 160px;
  padding: 2px 8px;
  border-radius: 3px;
  color: white;
  font-size: 11px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subscription-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--forum-radius-pill);
  background: #edf4fb;
  color: var(--forum-primary-color);
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.approval-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--forum-radius-pill);
  background: #fff3cd;
  color: #856404;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.approval-pill--rejected {
  background: #fdeeee;
  color: #b14545;
}

.approval-note {
  margin: 0 0 6px;
  color: #9a5050;
  font-size: 12px;
  line-height: 1.6;
}

.unread-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--forum-radius-pill);
  background: var(--forum-primary-color);
  color: var(--forum-text-inverse);
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
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

  .discussion-list-item-title {
    font-size: 14px;
    line-height: 1.35;
    white-space: normal;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    word-break: break-word;
  }

  .approval-note {
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

  .item-tags {
    flex-wrap: wrap;
  }

  .item-author,
  .item-last-post {
    flex: 1 1 100%;
  }

  .username {
    max-width: min(58vw, 220px);
  }

  .tag-label {
    max-width: min(52vw, 180px);
  }

  .tag-label,
  .subscription-pill,
  .approval-pill,
  .unread-pill {
    font-size: 10px;
  }
}
</style>
