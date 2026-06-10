<template>
  <main class="index-content">
    <DiscussionListHeaderSection
      :auth-store="authStore"
      :context-subject="contextSubject"
      :discussion-list-contexts="discussionListContexts"
      :is-following-page="isFollowingPage"
      :list-filter="listFilter"
      :sort-by="sortBy"
      :sort-options="sortOptions"
      :marking-all-read="markingAllRead"
      :refreshing="refreshing"
      @change-sort="$emit('change-sort', $event)"
      @mark-all-read="$emit('mark-all-read')"
      @refresh="$emit('refresh')"
    />

    <ForumStateBlock v-if="loading" class="discussion-list-state">
      {{ loadingStateText }}
    </ForumStateBlock>

    <template v-else>
      <div v-if="refreshing" class="discussion-list-refreshing" aria-live="polite">
        <i class="fas fa-sync-alt fa-spin"></i>
        {{ refreshingText }}
      </div>

      <ForumStateBlock v-if="discussions.length === 0" class="discussion-list-state">
        {{ emptyStateText }}
      </ForumStateBlock>

      <template v-else>
        <ul class="discussion-list">
          <DiscussionListItem
            v-for="discussion in discussions"
            :key="discussion.id"
            :discussion="discussion"
            :build-discussion-path="buildDiscussionPath"
            :build-user-path="buildUserPath"
            :format-relative-time="formatRelativeTime"
            :get-user-avatar-color="getUserAvatarColor"
            :get-user-display-name="getUserDisplayName"
            :get-user-initial="getUserInitial"
          />
        </ul>

        <ForumLoadMoreButton
          v-if="hasMore"
          :loading="loadingMore"
          :text="loadMoreText"
          :loading-text="loadingMoreText"
          @click="$emit('load-more')"
        />
      </template>
    </template>
  </main>
</template>

<script setup>
import DiscussionListHeaderSection from './DiscussionListHeaderSection.vue'
import DiscussionListItem from './DiscussionListItem.vue'
import {
  ForumLoadMoreButton,
  ForumStateBlock
} from '@bias/forum'
import { useDiscussionListContentState } from '../useDiscussionListContentState'

defineProps({
  authStore: {
    type: Object,
    required: true
  },
  contextSubject: {
    type: Object,
    default: null
  },
  discussionListContexts: {
    type: Array,
    default: () => []
  },
  isFollowingPage: {
    type: Boolean,
    default: false
  },
  listFilter: {
    type: String,
    default: 'all'
  },
  sortBy: {
    type: String,
    default: 'latest'
  },
  sortOptions: {
    type: Array,
    default: () => []
  },
  markingAllRead: {
    type: Boolean,
    default: false
  },
  refreshing: {
    type: Boolean,
    default: false
  },
  loading: {
    type: Boolean,
    default: false
  },
  discussions: {
    type: Array,
    default: () => []
  },
  emptyStateText: {
    type: String,
    default: '暂无讨论'
  },
  loadingStateText: {
    type: String,
    default: '正在加载讨论...'
  },
  hasMore: {
    type: Boolean,
    default: false
  },
  loadingMore: {
    type: Boolean,
    default: false
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

defineEmits(['change-sort', 'mark-all-read', 'refresh', 'load-more'])

const {
  loadMoreText,
  loadingMoreText,
  refreshingText,
} = useDiscussionListContentState()
</script>

<style scoped>
.index-content {
  flex: 1;
  background: var(--forum-bg-elevated);
  position: relative;
}

.discussion-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.discussion-list-state {
  margin: 24px;
}

.discussion-list-refreshing {
  position: absolute;
  top: 16px;
  right: 24px;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--forum-radius-pill);
  background: rgba(255, 255, 255, 0.92);
  color: var(--forum-text-muted);
  font-size: 13px;
  box-shadow: var(--forum-shadow-sm);
}

@media (max-width: 768px) {
  .discussion-list-state {
    margin: 15px;
  }

  .discussion-list-refreshing {
    top: 12px;
    right: 15px;
  }
}
</style>
