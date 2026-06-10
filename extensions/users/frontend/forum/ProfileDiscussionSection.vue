<template>
  <div class="profile-section">
    <ForumStateBlock v-if="loading" class="section-state-block">{{ loadingStateText }}</ForumStateBlock>
    <ForumStateBlock v-else-if="discussions.length === 0" class="section-state-block">
      {{ emptyStateText }}
    </ForumStateBlock>
    <div v-else class="discussion-list">
      <div
        v-for="discussion in discussions"
        :key="discussion.id"
        class="discussion-item"
      >
        <div class="discussion-main">
          <div class="discussion-title-row">
            <router-link :to="buildDiscussionPath(discussion)" class="discussion-title">
              {{ discussion.title }}
            </router-link>
            <ForumStateBadge
              v-for="badge in getStateBadges(discussion)"
              :key="badge.key"
              :label="badge.label"
              :tone="badge.tone"
              :size="badge.size || 'sm'"
              :icon="badge.icon || ''"
              :title="badge.title || ''"
            />
          </div>
          <p v-if="getFeedbackNoteText(discussion)" class="feedback-note">
            {{ getFeedbackNoteText(discussion) }}
          </p>
          <div class="discussion-meta">
            <span>{{ formatDate(discussion.created_at) }}</span>
          </div>
        </div>
        <div class="discussion-stats">
          <div class="stat">
            <i class="fas fa-comment"></i>
            {{ discussion.comment_count }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  toRef } from '@bias/core'
import { ForumStateBadge,
  ForumStateBlock
} from '@bias/forum'
import { useProfileContentSectionState } from './useProfileContentSectionState'

const props = defineProps({
  discussions: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  isOwnProfile: {
    type: Boolean,
    default: false
  },
  buildDiscussionPath: {
    type: Function,
    required: true
  },
  formatDate: {
    type: Function,
    required: true
  }
})

const {
  emptyStateText,
  getFeedbackNoteText,
  getStateBadges,
  loadingStateText,
} = useProfileContentSectionState({
  isOwnProfile: toRef(props, 'isOwnProfile'),
  items: toRef(props, 'discussions'),
  kind: 'discussion',
  loading: toRef(props, 'loading'),
})
</script>

<style scoped>
.section-state-block {
  margin: 0;
}

.discussion-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.discussion-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 18px 0;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.15s;
}

.discussion-item:hover {
  background: #fafbfc;
  margin: 0 -25px;
  padding: 18px 25px;
}

.discussion-item:last-child {
  border-bottom: none;
}

.discussion-main {
  flex: 1;
  min-width: 0;
}

.discussion-title {
  font-size: 16px;
  color: #333;
  font-weight: 500;
  display: block;
  margin-bottom: 6px;
  line-height: 1.4;
  min-width: 0;
  overflow-wrap: anywhere;
}

.discussion-title:hover {
  color: #4d698e;
  text-decoration: none;
}

.discussion-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  min-width: 0;
}

.discussion-meta {
  font-size: 13px;
  color: #aaa;
}

.discussion-stats {
  display: flex;
  gap: 15px;
  color: #aaa;
  font-size: 14px;
  flex-shrink: 0;
}

.stat {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat i {
  font-size: 14px;
}

.feedback-note {
  margin: 10px 0 0;
  color: #9a5050;
  font-size: 13px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

@media (max-width: 640px) {
  .discussion-item {
    align-items: flex-start;
  }

  .discussion-stats {
    padding-top: 2px;
  }
}
</style>
