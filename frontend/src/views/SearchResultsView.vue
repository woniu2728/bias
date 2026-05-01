<template>
  <div class="search-page">
    <ForumPageWithSidebar>
      <template #sidebar>
        <div class="search-sidebar-stack">
          <DiscussionListSidebarStartButton
            v-if="!authStore.isAuthenticated || authStore.canStartDiscussion"
            :current-tag="null"
            :start-discussion-button-style="{}"
            @click="handleStartDiscussion"
          />

          <ForumSearchFilterNav
            :items="filterItems"
            :active-value="searchType"
            @change="changeType"
          />
        </div>
      </template>

      <main class="search-content">
        <ForumHeroPanel
          pill="全局搜索"
          :title="`“${normalizedQuery || '未输入关键词'}”`"
          :description="heroText"
          variant="primary"
        >
          <template #meta>
            <ForumSearchStats
              v-if="normalizedQuery"
              :discussion-total="discussionTotal"
              :post-total="postTotal"
              :user-total="userTotal"
            />
          </template>
        </ForumHeroPanel>

        <ForumStateBlock v-if="!normalizedQuery">
          请输入关键词后再搜索。
        </ForumStateBlock>
        <ForumStateBlock v-else-if="loading">
          搜索中...
        </ForumStateBlock>
        <ForumStateBlock v-else-if="isEmpty">
          没有找到相关讨论、帖子或用户。
        </ForumStateBlock>
        <template v-else>
          <ForumSearchDiscussionSection
            v-if="showDiscussions"
            :discussions="discussions"
            :get-title-html="getDiscussionTitleHtml"
            :get-excerpt-html="getDiscussionExcerptHtml"
            :format-relative-time="formatRelativeTime"
            :show-more="searchType === 'all' && discussionTotal > discussions.length"
            @show-more="changeType('discussions')"
          />

          <ForumSearchPostSection
            v-if="showPosts"
            :posts="posts"
            :get-title-html="getPostTitleHtml"
            :get-excerpt-html="getPostExcerptHtml"
            :format-relative-time="formatRelativeTime"
            :show-more="searchType === 'all' && postTotal > posts.length"
            @show-more="changeType('posts')"
          />

          <ForumSearchUserSection
            v-if="showUsers"
            :users="users"
            :get-title-html="getUserTitleHtml"
            :get-subtitle-html="getUserSubtitleHtml"
            :show-more="searchType === 'all' && userTotal > users.length"
            @show-more="changeType('users')"
          />

          <ForumPagination
            v-if="searchType !== 'all' && totalPages > 1"
            :current-page="page"
            :total-pages="totalPages"
            @change="changePage"
          />
        </template>
      </main>
    </ForumPageWithSidebar>
  </div>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import ForumHeroPanel from '@/components/forum/ForumHeroPanel.vue'
import ForumPagination from '@/components/forum/ForumPagination.vue'
import ForumPageWithSidebar from '@/components/forum/ForumPageWithSidebar.vue'
import ForumSearchDiscussionSection from '@/components/forum/ForumSearchDiscussionSection.vue'
import ForumSearchFilterNav from '@/components/forum/ForumSearchFilterNav.vue'
import ForumSearchPostSection from '@/components/forum/ForumSearchPostSection.vue'
import ForumSearchStats from '@/components/forum/ForumSearchStats.vue'
import ForumSearchUserSection from '@/components/forum/ForumSearchUserSection.vue'
import ForumStateBlock from '@/components/forum/ForumStateBlock.vue'
import DiscussionListSidebarStartButton from '@/components/discussion/DiscussionListSidebarStartButton.vue'
import { useSearchResultsPage } from '@/composables/useSearchResultsPage'
import { useStartDiscussionAction } from '@/composables/useStartDiscussionAction'
import { formatRelativeTime } from '@/utils/forum'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()
const { startDiscussion } = useStartDiscussionAction({
  authStore,
  composerStore,
  router
})
const {
  changePage,
  changeType,
  discussionTotal,
  discussions,
  filterItems,
  getDiscussionExcerptHtml,
  getDiscussionTitleHtml,
  getPostExcerptHtml,
  getPostTitleHtml,
  getUserSubtitleHtml,
  getUserTitleHtml,
  heroText,
  isEmpty,
  loading,
  normalizedQuery,
  page,
  postTotal,
  posts,
  searchType,
  showDiscussions,
  showPosts,
  showUsers,
  totalPages,
  userTotal,
  users
} = useSearchResultsPage({
  route,
  router
})

function handleStartDiscussion() {
  startDiscussion({
    source: 'search'
  })
}

</script>

<style scoped>
.search-page {
  background: var(--forum-bg-canvas);
  min-height: calc(100vh - 56px);
}

.search-content {
  padding: 24px 28px 40px;
}

.search-sidebar-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

</style>
