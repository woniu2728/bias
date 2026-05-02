<template>
  <div class="tags-page">
    <ForumPageWithSidebar>
      <template #sidebar>
        <DiscussionListSidebarStartButton
          v-if="!authStore.isAuthenticated || authStore.canStartDiscussion"
          :current-tag="null"
          :start-discussion-button-style="{}"
          @click="handleStartDiscussion"
        />

        <ForumPrimaryNav :auth-store="authStore" active-key="tags" />
      </template>

      <main class="tags-content">
        <ForumHeroPanel title="全部标签" variant="default" />

        <ForumStateBlock v-if="loading">加载中...</ForumStateBlock>
        <ForumStateBlock v-else-if="tags.length === 0">暂无标签</ForumStateBlock>

        <template v-else>
          <div class="tag-grid">
            <ForumTagTile
              v-for="tag in tags"
              :key="tag.id"
              :tag="tag"
            />
          </div>

          <ForumTagCloud v-if="cloudTags.length" :tags="cloudTags" />
        </template>
      </main>
    </ForumPageWithSidebar>
  </div>
</template>

<script setup>
import { watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import { useForumStore } from '@/stores/forum'
import { useRouter } from 'vue-router'
import ForumHeroPanel from '@/components/forum/ForumHeroPanel.vue'
import ForumPageWithSidebar from '@/components/forum/ForumPageWithSidebar.vue'
import ForumPrimaryNav from '@/components/forum/ForumPrimaryNav.vue'
import ForumStateBlock from '@/components/forum/ForumStateBlock.vue'
import ForumTagCloud from '@/components/forum/ForumTagCloud.vue'
import ForumTagTile from '@/components/forum/ForumTagTile.vue'
import DiscussionListSidebarStartButton from '@/components/discussion/DiscussionListSidebarStartButton.vue'
import { useStartDiscussionAction } from '@/composables/useStartDiscussionAction'
import { useTagsPage } from '@/composables/useTagsPage'

const authStore = useAuthStore()
const composerStore = useComposerStore()
const forumStore = useForumStore()
const router = useRouter()
const { startDiscussion } = useStartDiscussionAction({
  authStore,
  composerStore,
  router
})

const { cloudTags, loading, tags } = useTagsPage()

watch(
  tags,
  value => {
    forumStore.setPageMeta({
      title: '全部标签',
      description: value.length ? `浏览 ${value.length} 个论坛标签，按主题发现相关讨论。` : '浏览论坛标签，按主题发现相关讨论。',
      canonicalUrl: '/tags',
    })
  },
  { immediate: true }
)

function handleStartDiscussion() {
  startDiscussion({
    source: 'tags'
  })
}
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
