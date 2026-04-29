<template>
  <div class="tags-page">
    <div class="page-container">
      <aside class="tags-sidebar">
        <button
          v-if="!authStore.isAuthenticated || authStore.canStartDiscussion"
          class="btn-start-discussion"
          @click="handleStartDiscussion"
        >
          <i class="fas fa-edit"></i>
          发起讨论
        </button>

        <nav class="side-nav">
          <router-link to="/" class="nav-item">
            <i class="far fa-comments"></i>
            全部讨论
          </router-link>
          <router-link v-if="authStore.user" to="/following" class="nav-item">
            <i class="fas fa-bell"></i>
            关注中
          </router-link>
          <router-link to="/tags" class="nav-item active">
            <i class="fas fa-tags"></i>
            全部标签
          </router-link>
          <router-link v-if="authStore.user" :to="`/u/${authStore.user.id}`" class="nav-item">
            <i class="fas fa-user"></i>
            我的主页
          </router-link>
        </nav>
      </aside>

      <main class="tags-content">
        <section class="tags-hero">
          <h1>全部标签</h1>
        </section>

        <div v-if="loading" class="state-block">加载中...</div>
        <div v-else-if="tags.length === 0" class="state-block">暂无标签</div>

        <template v-else>
          <div class="tag-grid">
            <article
              v-for="tag in tags"
              :key="tag.id"
              class="tag-tile"
              :style="{ '--tag-color': tag.color }"
            >
              <router-link :to="buildTagPath(tag)" class="tag-main">
                <div class="tag-header">
                  <span class="tag-badge" :style="{ backgroundColor: tag.color }"></span>
                  <h2>{{ tag.name }}</h2>
                </div>
                <p class="tag-description">
                  {{ tag.description || '这个标签还没有填写描述。' }}
                </p>
                <div v-if="tag.children.length" class="tag-children">
                  <router-link
                    v-for="child in tag.children"
                    :key="child.id"
                    :to="buildTagPath(child)"
                    class="tag-chip"
                  >
                    {{ child.name }}
                  </router-link>
                </div>
              </router-link>

              <router-link
                v-if="tag.last_posted_discussion"
                :to="buildDiscussionPath(tag.last_posted_discussion.id)"
                class="tag-last-discussion"
              >
                <span class="tag-last-title">{{ tag.last_posted_discussion.title }}</span>
                <span class="tag-last-time">{{ formatRelativeTime(tag.last_posted_discussion.last_posted_at) }}</span>
              </router-link>
              <div v-else class="tag-last-discussion tag-last-discussion-empty">
                暂无讨论
              </div>
            </article>
          </div>

          <div v-if="cloudTags.length" class="tag-cloud">
            <router-link
              v-for="tag in cloudTags"
              :key="tag.id"
              :to="buildTagPath(tag)"
              class="tag-cloud-item"
              :style="{ '--tag-color': tag.color }"
            >
              {{ tag.name }}
            </router-link>
          </div>
        </template>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import { useRouter } from 'vue-router'
import api from '@/api'
import {
  buildDiscussionPath,
  buildTagPath,
  flattenTags,
  formatRelativeTime,
  normalizeTag,
  unwrapList
} from '@/utils/forum'

const authStore = useAuthStore()
const composerStore = useComposerStore()
const router = useRouter()

const tags = ref([])
const loading = ref(true)

const cloudTags = computed(() => flattenTags(tags.value.filter(tag => tag.children.length === 0)).slice(0, 12))

onMounted(async () => {
  await loadTags()
})

async function loadTags() {
  loading.value = true
  try {
    const response = await api.get('/tags', {
      params: {
        include_children: true
      }
    })
    tags.value = unwrapList(response).map(normalizeTag)
  } catch (error) {
    console.error('加载标签失败:', error)
  } finally {
    loading.value = false
  }
}

function handleStartDiscussion() {
  if (!authStore.isAuthenticated) {
    router.push('/login')
    return
  }
  if (!authStore.canStartDiscussion) return

  composerStore.openDiscussionComposer({
    source: 'tags'
  })
}
</script>

<style scoped>
.tags-page {
  background: #f5f8fa;
  min-height: calc(100vh - 56px);
}

.page-container {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 240px 1fr;
}

.tags-sidebar {
  padding: 20px 15px;
  background: white;
  border-right: 1px solid #e3e8ed;
  min-height: calc(100vh - 56px);
}

.btn-start-discussion {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: #e7672e;
  color: white;
  margin-bottom: 16px;
}

.btn-start-discussion:hover {
  background: #d85b1e;
}

.side-nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 3px;
  color: #555;
}

.nav-item:hover,
.nav-item.active {
  background: #4d698e;
  color: white;
  text-decoration: none;
}

.tags-content {
  padding: 24px 28px 40px;
}

.tags-hero {
  margin-bottom: 24px;
  padding: 28px 32px;
  border-radius: 14px;
  background: linear-gradient(135deg, #f9fbfc 0%, #e8eef4 100%);
  border: 1px solid #d9e4ec;
}

.tags-hero h1 {
  font-size: 32px;
  font-weight: 300;
  margin-bottom: 8px;
  color: #2f3c4d;
}

.tags-hero p {
  color: #607080;
  max-width: 680px;
}

.state-block {
  padding: 60px 24px;
  background: white;
  border-radius: 8px;
  text-align: center;
  color: #8897a5;
}

.tag-grid {
  display: grid;
  gap: 18px;
}

.tag-tile {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 20px;
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 10px;
  overflow: hidden;
}

.tag-main {
  padding: 22px 24px;
  color: inherit;
}

.tag-main:hover {
  text-decoration: none;
}

.tag-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.tag-badge {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--tag-color) 14%, white);
}

.tag-header h2 {
  font-size: 20px;
  font-weight: 500;
  color: #24313f;
}

.tag-description {
  color: #6a7988;
  line-height: 1.6;
}

.tag-children {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
}

.tag-chip,
.tag-cloud-item {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--tag-color) 25%, white);
  color: #314150;
  background: color-mix(in srgb, var(--tag-color) 10%, white);
}

.tag-chip:hover,
.tag-cloud-item:hover {
  text-decoration: none;
  background: color-mix(in srgb, var(--tag-color) 18%, white);
}

.tag-last-discussion {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 22px 24px;
  background: #fbfcfd;
  border-left: 1px solid #edf2f6;
}

.tag-last-title {
  color: #24313f;
  line-height: 1.5;
}

.tag-last-time,
.tag-last-discussion-empty {
  color: #8a98a6;
  font-size: 13px;
  margin-top: 8px;
}

.tag-cloud {
  margin-top: 22px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

@media (max-width: 900px) {
  .page-container {
    grid-template-columns: 1fr;
  }

  .tags-sidebar {
    min-height: auto;
    border-right: none;
    border-bottom: 1px solid #e3e8ed;
  }

  .tag-tile {
    grid-template-columns: 1fr;
  }

  .tag-last-discussion {
    border-left: none;
    border-top: 1px solid #edf2f6;
  }
}
</style>
