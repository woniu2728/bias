<template>
  <div class="profile-section">
    <ForumStateBlock v-if="loading" class="section-state-block">{{ loadingStateText }}</ForumStateBlock>
    <ForumStateBlock v-else-if="posts.length === 0" class="section-state-block">
      {{ emptyStateText }}
    </ForumStateBlock>
    <div v-else class="post-list">
      <div v-for="post in posts" :key="post.id" class="post-item">
        <div class="post-header">
          <div class="post-header-main">
            <router-link
              :to="buildDiscussionPath(post.discussion?.id || post.discussion_id)"
              class="post-discussion-link"
            >
              <i class="fas fa-arrow-right"></i>
              {{ post.discussion?.title || '讨论' }}
            </router-link>
            <ForumStateBadge
              v-for="badge in getStateBadges(post)"
              :key="badge.key"
              :label="badge.label"
              :tone="badge.tone"
              :size="badge.size || 'sm'"
              :icon="badge.icon || ''"
              :title="badge.title || ''"
            />
          </div>
          <span class="post-time">{{ formatDate(post.created_at) }}</span>
        </div>
        <p v-if="getFeedbackNoteText(post)" class="feedback-note">
          {{ getFeedbackNoteText(post) }}
        </p>
        <div class="post-content" v-html="post.content_html || post.content"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { toRef } from 'vue'
import ForumStateBlock from '@/components/forum/ForumStateBlock.vue'
import ForumStateBadge from '@/components/forum/ForumStateBadge.vue'
import { useProfileContentSectionState } from '@/composables/useProfileContentSectionState'

const props = defineProps({
  posts: {
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
  items: toRef(props, 'posts'),
  kind: 'post',
  loading: toRef(props, 'loading'),
})
</script>

<style scoped>
.section-state-block {
  margin: 0;
}

.post-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.post-item {
  padding: 20px 0;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.15s;
}

.post-item:hover {
  background: #fafbfc;
  margin: 0 -25px;
  padding: 20px 25px;
}

.post-item:last-child {
  border-bottom: none;
}

.post-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
  min-width: 0;
}

.post-header-main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  min-width: 0;
}

.post-discussion-link {
  color: #4d698e;
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow-wrap: anywhere;
}

.post-discussion-link:hover {
  text-decoration: none;
  color: #3d5875;
}

.post-discussion-link i {
  font-size: 12px;
}

.post-time {
  font-size: 13px;
  color: #aaa;
  flex-shrink: 0;
  white-space: nowrap;
}

.post-content {
  color: #555;
  line-height: 1.7;
  font-size: 15px;
  overflow-wrap: anywhere;
  min-width: 0;
  max-width: 100%;
}

.post-content :deep(img) {
  display: block;
  max-width: 100%;
  height: auto;
}

.post-content :deep(video),
.post-content :deep(iframe),
.post-content :deep(table),
.post-content :deep(pre),
.post-content :deep(code) {
  max-width: 100%;
}

.post-content :deep(pre) {
  overflow-x: auto;
}

.post-content :deep(table) {
  display: block;
  overflow-x: auto;
}

.post-content :deep(a) {
  overflow-wrap: anywhere;
}

.feedback-note {
  margin: 10px 0 0;
  color: #9a5050;
  font-size: 13px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

@media (max-width: 640px) {
  .post-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }
}
</style>
