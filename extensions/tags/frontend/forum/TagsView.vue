<template>
  <div class="tags-page">
    <ForumPageWithSidebar>
      <template #sidebar>
        <DiscussionListSidebarStartButton
          v-if="sidebarBindings.showStartDiscussionButton"
          :current-tag="null"
          :start-discussion-button-style="{}"
          @click="sidebarEvents.startDiscussion"
        />

        <ForumPrimaryNav :auth-store="sidebarBindings.authStore" :notification-store="null" active-key="tags" />
      </template>

      <main class="tags-content">
        <ForumHeroPanel v-bind="heroBindings" />

        <ForumStateBlock v-if="contentBindings.loading">{{ contentBindings.loadingStateText }}</ForumStateBlock>
        <ForumStateBlock v-else-if="contentBindings.tags.length === 0">{{ contentBindings.emptyStateText }}</ForumStateBlock>

        <template v-else>
          <div class="tag-grid">
            <TagTile
              v-for="tag in contentBindings.tags"
              :key="tag.id"
              :tag="tag"
            />
          </div>

          <TagCloud v-if="contentBindings.cloudTags.length" :tags="contentBindings.cloudTags" />
        </template>
      </main>
    </ForumPageWithSidebar>
  </div>
</template>

<script setup>
import {
  DiscussionListSidebarStartButton,
  ForumHeroPanel,
  ForumPageWithSidebar,
  ForumPrimaryNav,
  ForumStateBlock,
  useAuthStore,
  useComposerStore,
  useForumStore,
  useRouter,
} from '@bias/forum'
import TagCloud from './TagCloud.vue'
import TagTile from './TagTile.vue'
import { useTagsViewModel } from './useTagsViewModel.js'

const authStore = useAuthStore()
const composerStore = useComposerStore()
const forumStore = useForumStore()
const router = useRouter()
const {
  contentBindings,
  heroBindings,
  sidebarBindings,
  sidebarEvents,
} = useTagsViewModel({
  authStore,
  composerStore,
  forumStore,
  router,
})
</script>

<style scoped>
.tags-page {
  background: var(--forum-bg-canvas);
  min-height: calc(100vh - 56px);
}

.tags-content {
  padding: 24px 28px 40px;
}

.tag-grid {
  display: grid;
  gap: 18px;
}
</style>
