<template>
  <div class="discussion-detail-page">
    <div class="container">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="!discussion" class="error">讨论不存在</div>
      <div v-else class="layout">
        <!-- 主内容区 -->
        <main class="main-content">
          <!-- 讨论标题 -->
          <div class="discussion-header">
            <div class="discussion-badges">
              <span v-if="discussion.is_sticky" class="badge badge-pinned">置顶</span>
              <span v-if="discussion.is_locked" class="badge badge-locked">锁定</span>
              <span v-if="discussion.is_hidden" class="badge badge-hidden">隐藏</span>
            </div>
            <h1>{{ discussion.title }}</h1>
            <div class="discussion-tags" v-if="discussion.tags && discussion.tags.length">
              <router-link
                v-for="tag in discussion.tags"
                :key="tag.id"
                class="tag"
                :to="buildTagPath(tag)"
                :style="{ backgroundColor: tag.color }"
              >
                {{ tag.name }}
              </router-link>
            </div>
          </div>

          <div v-if="hasPrevious" class="load-more load-previous">
            <button @click="loadPreviousPosts" class="secondary" :disabled="loadingPrevious">
              {{ loadingPrevious ? '加载中...' : '加载前面的回复' }}
            </button>
          </div>

          <!-- 帖子列表 -->
          <div class="posts">
            <div
              v-for="post in posts"
              :key="post.id"
              :id="`post-${post.number}`"
              class="post-item"
              :class="{ 'is-hidden': post.is_hidden, 'is-target': highlightedPostNumber === post.number }"
            >
              <div class="post-avatar">
                <div v-if="!post.user.avatar_url" class="avatar-placeholder">
                  {{ post.user.username.charAt(0).toUpperCase() }}
                </div>
                <img
                  v-else
                  :src="post.user.avatar_url"
                  :alt="post.user.username"
                />
              </div>

              <div class="post-content">
                <div class="post-header">
                  <router-link :to="buildUserPath(post.user)" class="post-author">{{ post.user.username }}</router-link>
                  <span class="post-number">#{{ post.number }}</span>
                  <span class="post-time">{{ formatDate(post.created_at) }}</span>
                  <span v-if="post.edited_at" class="post-edited">(已编辑)</span>
                </div>

                <div class="post-body" v-html="post.content_html"></div>

                <div class="post-footer">
                  <button
                    @click="toggleLike(post)"
                    class="post-action"
                    :class="{ 'is-liked': post.is_liked }"
                  >
                    ❤️ {{ post.like_count || 0 }}
                  </button>
                  <button
                    @click="replyToPost(post)"
                    class="post-action"
                    v-if="authStore.isAuthenticated && !discussion.is_locked"
                  >
                    💬 回复
                  </button>
                  <button
                    @click="editPost(post)"
                    class="post-action"
                    v-if="canEditPost(post)"
                  >
                    ✏️ 编辑
                  </button>
                  <button
                    @click="deletePost(post)"
                    class="post-action danger"
                    v-if="canDeletePost(post)"
                  >
                    🗑️ 删除
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- 加载更多 -->
          <div v-if="hasMore" class="load-more">
            <button @click="loadMorePosts" class="secondary" :disabled="loadingMore">
              {{ loadingMore ? '加载中...' : '加载更多' }}
            </button>
          </div>

          <div v-if="authStore.isAuthenticated && !discussion.is_locked" class="reply-placeholder">
            <button @click="openComposer" class="primary">
              {{ replyContent.trim() ? '继续编辑回复' : '发表回复' }}
            </button>
            <span v-if="replyContent.trim()">已有未发布内容</span>
          </div>

          <div v-else-if="discussion.is_locked" class="locked-notice">
            此讨论已被锁定，无法回复
          </div>
          <div v-else class="login-notice">
            <router-link to="/login">登录</router-link> 后才能回复
          </div>
        </main>

        <!-- 侧边栏 -->
        <aside class="sidebar">
          <div v-if="authStore.isAuthenticated" class="sidebar-section">
            <h3>关注讨论</h3>
            <p class="subscription-copy">
              {{ discussion.is_subscribed ? '你会收到这条讨论的新回复通知。' : '关注后，这条讨论的新回复会进入你的通知列表。' }}
            </p>
            <button @click="toggleSubscription" class="secondary full-width" :disabled="togglingSubscription">
              {{ togglingSubscription ? '提交中...' : (discussion.is_subscribed ? '取消关注' : '关注讨论') }}
            </button>
          </div>

          <div class="sidebar-section">
            <h3>讨论信息</h3>
            <div class="info-item">
              <span class="label">发起人</span>
              <router-link :to="buildUserPath(discussion.user)" class="value value-link">{{ discussion.user.username }}</router-link>
            </div>
            <div class="info-item">
              <span class="label">创建时间</span>
              <span class="value">{{ formatDate(discussion.created_at) }}</span>
            </div>
            <div class="info-item">
              <span class="label">最后回复</span>
              <span class="value">{{ formatDate(discussion.last_posted_at) }}</span>
            </div>
            <div class="info-item">
              <span class="label">回复数</span>
              <span class="value">{{ discussion.comment_count }}</span>
            </div>
          </div>

          <div class="sidebar-section">
            <h3>帖子导航</h3>
            <div class="scrubber">
              <div class="scrubber-status">
                <span>已加载 {{ loadedRangeText }}</span>
                <span>正在阅读 #{{ currentVisiblePostNumber }}</span>
                <span>共 {{ totalPosts || discussion.comment_count }} 楼</span>
              </div>
              <input
                v-model.number="jumpPostNumber"
                type="range"
                min="1"
                :max="discussion.last_post_number || discussion.comment_count || 1"
                class="scrubber-range"
                @change="jumpToPost(jumpPostNumber)"
              />
              <div class="scrubber-actions">
                <button @click="jumpToPost(1)" class="secondary">首帖</button>
                <button @click="jumpToPost(jumpPostNumber)" class="secondary">跳转</button>
                <button @click="jumpToPost(discussion.last_post_number || discussion.comment_count || 1)" class="secondary">最新</button>
              </div>
            </div>
          </div>

          <div class="sidebar-section" v-if="canManageDiscussion">
            <h3>管理操作</h3>
            <button @click="togglePin" class="secondary full-width">
              {{ discussion.is_sticky ? '取消置顶' : '置顶' }}
            </button>
            <button @click="toggleLock" class="secondary full-width">
              {{ discussion.is_locked ? '解锁' : '锁定' }}
            </button>
            <button @click="toggleHide" class="secondary full-width">
              {{ discussion.is_hidden ? '显示' : '隐藏' }}
            </button>
            <button @click="deleteDiscussion" class="danger full-width">
              删除讨论
            </button>
          </div>
        </aside>
      </div>
    </div>

    <div
      v-if="discussion && authStore.isAuthenticated && !discussion.is_locked && composerOpen"
      class="floating-composer"
      :class="{ 'is-minimized': composerMinimized, 'is-expanded': composerExpanded }"
    >
      <div class="composer-handle" aria-hidden="true"></div>
      <div class="composer-header">
        <div class="composer-title">
          <span>{{ composerTitle }}</span>
          <small v-if="replyingTo">回复 #{{ replyingTo.number }} {{ replyingTo.user.username }}</small>
          <small v-else>{{ composerStatusText }}</small>
        </div>
        <div class="composer-controls">
          <button
            v-if="!editingPost"
            @click="saveComposerDraft()"
            type="button"
            title="保存草稿"
            :disabled="!discussion"
          >
            <i class="far fa-save"></i>
          </button>
          <button @click="toggleComposerMinimized" type="button" :title="composerMinimized ? '展开' : '最小化'">
            <i :class="composerMinimized ? 'far fa-window-restore' : 'fas fa-minus minimize'"></i>
          </button>
          <button @click="toggleComposerExpanded" type="button" :title="composerExpanded ? '退出全屏' : '全屏'">
            <i :class="composerExpanded ? 'fas fa-compress' : 'fas fa-expand'"></i>
          </button>
          <button @click="closeComposer" type="button" title="关闭">
            <i class="fas fa-times"></i>
          </button>
        </div>
      </div>

      <div v-show="!composerMinimized" class="composer-body">
        <textarea
          ref="composerTextarea"
          v-model="replyContent"
          placeholder="输入你的回复... 支持 Markdown、@用户名 和代码块"
          rows="7"
        ></textarea>

        <div class="composer-toolbar">
          <button @click="submitReply" class="composer-submit" :disabled="submitting || !replyContent.trim()" type="button">
            <i class="fas fa-paper-plane"></i>
            {{ submitting ? '提交中...' : (editingPost ? '更新回复' : 'Post Reply') }}
          </button>

          <div class="composer-formatting" aria-label="格式化工具栏">
            <button
              v-for="tool in composerTools"
              :key="tool.key"
              @click="applyComposerTool(tool)"
              type="button"
              :title="tool.title"
            >
              <i v-if="tool.icon" :class="tool.icon"></i>
              <span v-else>{{ tool.label }}</span>
            </button>
          </div>

          <button
            v-if="composerDraftSavedAt && !editingPost"
            @click="clearComposerDraft"
            class="composer-secondary"
            type="button"
          >
            清除草稿
          </button>
          <button v-if="editingPost" @click="cancelEdit" class="composer-secondary" type="button">取消编辑</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/api'
import {
  buildTagPath,
  buildUserPath,
  formatRelativeTime,
  normalizeDiscussion,
  normalizePost,
  unwrapList
} from '@/utils/forum'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const discussion = ref(null)
const posts = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const loadingPrevious = ref(false)
const firstLoadedPage = ref(1)
const lastLoadedPage = ref(1)
const totalPosts = ref(0)
const pageLimit = 20

const replyContent = ref('')
const submitting = ref(false)
const editingPost = ref(null)
const replyingTo = ref(null)
const togglingSubscription = ref(false)
const composerOpen = ref(false)
const composerMinimized = ref(false)
const composerExpanded = ref(false)
const composerTextarea = ref(null)
const composerDraftSavedAt = ref('')
const highlightedPostNumber = ref(null)
const jumpPostNumber = ref(1)
const currentVisiblePostNumber = ref(1)
let scrollFrame = null
let nearUrlTimer = null
const composerTools = [
  { key: 'upload', title: '附件占位', icon: 'fas fa-file-upload' },
  { key: 'heading', title: '标题', label: 'H', before: '## ', after: '' },
  { key: 'bold', title: '加粗', label: 'B', before: '**', after: '**' },
  { key: 'italic', title: '斜体', label: 'I', before: '*', after: '*' },
  { key: 'strike', title: '删除线', label: 'S', before: '~~', after: '~~' },
  { key: 'quote', title: '引用', icon: 'fas fa-quote-left' },
  { key: 'spoiler', title: '提示/警告', icon: 'fas fa-exclamation-triangle', before: '> **提示：** ', after: '' },
  { key: 'code', title: '代码', icon: 'fas fa-code', before: '`', after: '`' },
  { key: 'link', title: '链接', icon: 'fas fa-link' },
  { key: 'image', title: '图片', icon: 'fas fa-image' },
  { key: 'bullets', title: '无序列表', icon: 'fas fa-list-ul' },
  { key: 'ordered', title: '有序列表', icon: 'fas fa-list-ol' },
  { key: 'mention', title: '@ 提及', icon: 'fas fa-at', before: '@', after: '' },
  { key: 'emoji', title: '表情', icon: 'far fa-smile', before: '😊', after: '' }
]

const canManageDiscussion = computed(() => {
  return authStore.user?.is_staff || authStore.user?.id === discussion.value?.user.id
})

const hasPrevious = computed(() => firstLoadedPage.value > 1)
const hasMore = computed(() => totalPosts.value > 0 && lastLoadedPage.value * pageLimit < totalPosts.value)
const targetNearPost = computed(() => {
  const value = Number(route.query.near)
  return Number.isFinite(value) && value > 0 ? value : null
})
const loadedRangeText = computed(() => {
  if (!posts.value.length) return '暂无'
  return `#${posts.value[0].number} - #${posts.value[posts.value.length - 1].number}`
})
const composerTitle = computed(() => {
  if (editingPost.value) return `编辑 #${editingPost.value.number}`
  if (replyingTo.value) return '回复帖子'
  return `回复：${discussion.value?.title || ''}`
})
const composerStatusText = computed(() => {
  if (editingPost.value) return '编辑模式下不会恢复已保存草稿。'
  if (composerDraftSavedAt.value) return `草稿已保存于 ${formatDraftTime(composerDraftSavedAt.value)}。`
  return '支持 Markdown，可保存草稿并最小化继续编辑。'
})

onMounted(async () => {
  await refreshDiscussion()
  window.addEventListener('scroll', handlePostScroll, { passive: true })
  window.addEventListener('resize', handlePostScroll, { passive: true })
  await nextTick()
  updateVisiblePostFromScroll()
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', handlePostScroll)
  window.removeEventListener('resize', handlePostScroll)
  if (scrollFrame) {
    cancelAnimationFrame(scrollFrame)
  }
  if (nearUrlTimer) {
    clearTimeout(nearUrlTimer)
  }
})

watch(
  () => [route.params.id, route.query.near],
  async () => {
    resetPostStream()
    loading.value = true
    await refreshDiscussion()
  }
)

async function refreshDiscussion() {
  await loadDiscussion()
  await loadInitialPosts()
}

async function loadDiscussion() {
  try {
    const data = await api.get(`/discussions/${route.params.id}`)
    discussion.value = normalizeDiscussion(data)
  } catch (error) {
    console.error('加载讨论失败:', error)
  } finally {
    loading.value = false
  }
}

async function loadInitialPosts() {
  try {
    const data = await fetchPosts(1, targetNearPost.value)
    replacePosts(data)

    if (targetNearPost.value) {
      await scrollToPost(targetNearPost.value)
    }
  } catch (error) {
    console.error('加载帖子失败:', error)
  }
}

async function fetchPosts(page, near = null) {
  const params = {
    page,
    limit: pageLimit
  }

  if (near) {
    params.near = near
  }

  return api.get(`/discussions/${route.params.id}/posts`, { params })
}

function replacePosts(data) {
  const items = unwrapList(data).map(normalizePost)
  posts.value = items
  firstLoadedPage.value = data.page || 1
  lastLoadedPage.value = data.page || 1
  totalPosts.value = data.total || items.length
  syncJumpNumber()
  nextTick(updateVisiblePostFromScroll)
}

function appendPosts(data) {
  const items = unwrapList(data).map(normalizePost)
  posts.value.push(...items)
  lastLoadedPage.value = data.page || lastLoadedPage.value + 1
  totalPosts.value = data.total || totalPosts.value
  syncJumpNumber()
  nextTick(updateVisiblePostFromScroll)
}

function prependPosts(data) {
  const anchorNumber = posts.value[0]?.number
  const anchorTop = anchorNumber ? document.getElementById(`post-${anchorNumber}`)?.getBoundingClientRect().top : null
  const items = unwrapList(data).map(normalizePost)
  posts.value.unshift(...items)
  firstLoadedPage.value = data.page || Math.max(1, firstLoadedPage.value - 1)
  totalPosts.value = data.total || totalPosts.value
  syncJumpNumber()
  nextTick(() => {
    if (anchorNumber && anchorTop !== null) {
      const newTop = document.getElementById(`post-${anchorNumber}`)?.getBoundingClientRect().top
      if (typeof newTop === 'number') {
        window.scrollBy({ top: newTop - anchorTop })
      }
    }
    updateVisiblePostFromScroll()
  })
}

async function loadMorePosts() {
  loadingMore.value = true
  try {
    const data = await fetchPosts(lastLoadedPage.value + 1)
    appendPosts(data)
  } finally {
    loadingMore.value = false
  }
}

async function loadPreviousPosts() {
  if (!hasPrevious.value) return

  loadingPrevious.value = true
  try {
    const data = await fetchPosts(firstLoadedPage.value - 1)
    prependPosts(data)
  } finally {
    loadingPrevious.value = false
  }
}

async function jumpToPost(number) {
  const targetNumber = Number(number)
  if (!targetNumber) return

  if (posts.value.some(post => post.number === targetNumber)) {
    await scrollToPost(targetNumber)
    replaceNearInAddressBar(targetNumber)
    return
  }

  router.replace({
    path: route.path,
    query: {
      ...route.query,
      near: targetNumber
    }
  })
}

async function scrollToPost(number) {
  await nextTick()
  const target = document.getElementById(`post-${number}`)
  if (!target) return

  highlightedPostNumber.value = number
  currentVisiblePostNumber.value = number
  jumpPostNumber.value = number
  target.scrollIntoView({ behavior: 'smooth', block: 'center' })
  setTimeout(() => {
    if (highlightedPostNumber.value === number) {
      highlightedPostNumber.value = null
    }
  }, 2400)
}

function resetPostStream() {
  posts.value = []
  firstLoadedPage.value = 1
  lastLoadedPage.value = 1
  totalPosts.value = 0
  highlightedPostNumber.value = null
  jumpPostNumber.value = Number(route.query.near) || 1
  currentVisiblePostNumber.value = jumpPostNumber.value
}

function syncJumpNumber() {
  if (targetNearPost.value) {
    jumpPostNumber.value = targetNearPost.value
  } else if (posts.value.length) {
    jumpPostNumber.value = posts.value[posts.value.length - 1].number
  }
}

function handlePostScroll() {
  if (scrollFrame) return

  scrollFrame = requestAnimationFrame(() => {
    scrollFrame = null
    updateVisiblePostFromScroll()
  })
}

function updateVisiblePostFromScroll() {
  if (!posts.value.length) return

  const anchorY = 120
  let closestPostNumber = posts.value[0].number
  let closestDistance = Number.POSITIVE_INFINITY

  for (const post of posts.value) {
    const element = document.getElementById(`post-${post.number}`)
    if (!element) continue

    const rect = element.getBoundingClientRect()
    if (rect.bottom < 0 || rect.top > window.innerHeight) continue

    const distance = Math.abs(rect.top - anchorY)
    if (distance < closestDistance) {
      closestDistance = distance
      closestPostNumber = post.number
    }
  }

  if (closestPostNumber !== currentVisiblePostNumber.value) {
    currentVisiblePostNumber.value = closestPostNumber
    jumpPostNumber.value = closestPostNumber
    scheduleNearUrlSync(closestPostNumber)
  }
}

function scheduleNearUrlSync(number) {
  if (nearUrlTimer) {
    clearTimeout(nearUrlTimer)
  }

  nearUrlTimer = setTimeout(() => {
    replaceNearInAddressBar(number)
  }, 300)
}

function replaceNearInAddressBar(number) {
  if (typeof window === 'undefined') return

  const url = new URL(window.location.href)
  if (url.searchParams.get('near') === String(number)) return

  url.searchParams.set('near', number)
  window.history.replaceState(window.history.state, '', `${url.pathname}${url.search}${url.hash}`)
}

async function toggleLike(post) {
  if (!authStore.isAuthenticated) {
    router.push('/login')
    return
  }

  try {
    if (post.is_liked) {
      await api.delete(`/posts/${post.id}/like`)
      post.like_count--
      post.is_liked = false
    } else {
      await api.post(`/posts/${post.id}/like`)
      post.like_count++
      post.is_liked = true
    }
  } catch (error) {
    console.error('点赞失败:', error)
  }
}

function replyToPost(post) {
  replyingTo.value = post
  replyContent.value = `@${post.user.username} `
  openComposer()
}

function editPost(post) {
  editingPost.value = post
  replyContent.value = post.content
  replyingTo.value = null
  openComposer()
}

function cancelEdit() {
  closeComposer(true)
}

async function openComposer() {
  composerOpen.value = true
  composerMinimized.value = false
  if (!editingPost.value && !replyContent.value.trim()) {
    restoreComposerDraft()
  }
  await nextTick()
  composerTextarea.value?.focus()
}

function toggleComposerMinimized() {
  composerMinimized.value = !composerMinimized.value
  if (!composerMinimized.value) {
    nextTick(() => composerTextarea.value?.focus())
  }
}

function toggleComposerExpanded() {
  composerExpanded.value = !composerExpanded.value
  if (composerMinimized.value) {
    composerMinimized.value = false
  }
  nextTick(() => composerTextarea.value?.focus())
}

function closeComposer(force = false) {
  if (!force && replyContent.value.trim() && !confirm('确定要关闭回复框吗？当前草稿会被清空。')) {
    return
  }

  resetComposerState()
}

function resetComposerState() {
  composerOpen.value = false
  composerMinimized.value = false
  composerExpanded.value = false
  composerDraftSavedAt.value = ''
  editingPost.value = null
  replyingTo.value = null
  replyContent.value = ''
}

async function applyComposerTool(tool) {
  composerOpen.value = true
  composerMinimized.value = false
  await nextTick()

  const textarea = composerTextarea.value
  if (!textarea) return

  const start = textarea.selectionStart ?? replyContent.value.length
  const end = textarea.selectionEnd ?? replyContent.value.length
  const selected = replyContent.value.slice(start, end)
  const replacement = buildComposerToolReplacement(tool, selected)

  replyContent.value = `${replyContent.value.slice(0, start)}${replacement}${replyContent.value.slice(end)}`

  await nextTick()
  textarea.focus()
  const cursor = selected
    ? start + replacement.length
    : start + defaultToolCursorOffset(tool)
  textarea.setSelectionRange(cursor, cursor)
}

function buildComposerToolReplacement(tool, selected) {
  if (tool.key === 'link') {
    return selected ? `[${selected}](https://)` : '[链接文字](https://)'
  }
  if (tool.key === 'image') {
    return selected ? `![图片描述](${selected})` : '![图片描述](https://)'
  }
  if (tool.key === 'upload') {
    return selected ? `[附件说明](${selected})` : '[附件说明](上传后的附件地址)'
  }
  if (tool.key === 'quote') {
    return prefixLines(selected || '引用内容', '> ')
  }
  if (tool.key === 'bullets') {
    return prefixLines(selected || '列表项', '- ')
  }
  if (tool.key === 'ordered') {
    return prefixOrderedLines(selected || '列表项')
  }

  const before = tool.before || ''
  const after = tool.after || ''
  return `${before}${selected || defaultToolText(tool)}${after}`
}

function defaultToolCursorOffset(tool) {
  const replacement = buildComposerToolReplacement(tool, '')
  if (tool.key === 'image') return replacement.indexOf('https://') + 'https://'.length
  if (tool.key === 'upload') return replacement.indexOf('上传后的附件地址')
  if (tool.key === 'link') return replacement.indexOf('链接文字') + '链接文字'.length
  if (tool.key === 'emoji') return replacement.length
  return replacement.length
}

function prefixLines(content, prefix) {
  return content
    .split('\n')
    .map(line => `${prefix}${line || '内容'}`)
    .join('\n')
}

function prefixOrderedLines(content) {
  return content
    .split('\n')
    .map((line, index) => `${index + 1}. ${line || '内容'}`)
    .join('\n')
}

function defaultToolText(tool) {
  if (tool.key === 'link') return '链接文字'
  if (tool.key === 'code') return 'code'
  if (tool.key === 'heading') return '标题'
  if (tool.key === 'upload') return '附件'
  if (tool.key === 'image') return 'https://'
  if (tool.key === 'emoji') return ''
  return '文本'
}

function getComposerDraftKey() {
  if (!discussion.value?.id || editingPost.value) return null
  return `pyflarum:discussion:${discussion.value.id}:draft:${authStore.user?.id || 'guest'}`
}

function restoreComposerDraft() {
  if (typeof window === 'undefined') return false

  composerDraftSavedAt.value = ''
  const key = getComposerDraftKey()
  if (!key) return false

  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return false

    const draft = JSON.parse(raw)
    if (!draft?.content?.trim()) return false

    replyContent.value = draft.content
    composerDraftSavedAt.value = draft.updatedAt || ''
    return true
  } catch (error) {
    console.error('恢复草稿失败:', error)
    return false
  }
}

function saveComposerDraft() {
  if (typeof window === 'undefined' || editingPost.value) return

  const key = getComposerDraftKey()
  if (!key) return

  const content = replyContent.value.trim()
  if (!content) {
    window.localStorage.removeItem(key)
    composerDraftSavedAt.value = ''
    return
  }

  const updatedAt = new Date().toISOString()
  window.localStorage.setItem(
    key,
    JSON.stringify({
      content: replyContent.value,
      updatedAt
    })
  )
  composerDraftSavedAt.value = updatedAt
}

function clearComposerDraft() {
  if (typeof window === 'undefined') return

  const key = getComposerDraftKey()
  if (!key) return

  window.localStorage.removeItem(key)
  composerDraftSavedAt.value = ''
}

function formatDraftTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '刚刚'

  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function submitReply() {
  if (!replyContent.value.trim()) return

  submitting.value = true
  try {
    if (editingPost.value) {
      // 编辑帖子
      const data = await api.patch(`/posts/${editingPost.value.id}`, {
        content: replyContent.value
      })
      const index = posts.value.findIndex(p => p.id === editingPost.value.id)
      if (index !== -1) {
        posts.value[index] = normalizePost(data)
      }
    } else {
      // 创建新回复
      const data = await api.post(`/discussions/${route.params.id}/posts`, {
        content: replyContent.value
      })
      const newPost = normalizePost(data)
      const shouldJumpToNewPost = hasMore.value
      discussion.value.comment_count++
      totalPosts.value++
      lastLoadedPage.value = Math.max(lastLoadedPage.value, Math.ceil(totalPosts.value / pageLimit))
      if (shouldJumpToNewPost) {
        await jumpToPost(newPost.number)
      } else {
        posts.value.push(newPost)
        await scrollToPost(newPost.number)
      }
      if (authStore.user?.preferences?.follow_after_reply) {
        discussion.value.is_subscribed = true
      }
      clearComposerDraft()
    }

    resetComposerState()
  } catch (error) {
    console.error('提交失败:', error)
    alert('提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}

async function deletePost(post) {
  if (!confirm('确定要删除这条回复吗？')) return

  try {
    await api.delete(`/posts/${post.id}`)
    posts.value = posts.value.filter(p => p.id !== post.id)
    discussion.value.comment_count--
    totalPosts.value = Math.max(0, totalPosts.value - 1)
  } catch (error) {
    console.error('删除失败:', error)
    alert('删除失败，请稍后重试')
  }
}

function canEditPost(post) {
  return authStore.user?.id === post.user.id || authStore.user?.is_staff
}

function canDeletePost(post) {
  return authStore.user?.id === post.user.id || authStore.user?.is_staff
}

async function togglePin() {
  try {
    await api.post(`/discussions/${discussion.value.id}/pin`)
    discussion.value.is_sticky = !discussion.value.is_sticky
  } catch (error) {
    console.error('操作失败:', error)
  }
}

async function toggleLock() {
  try {
    await api.post(`/discussions/${discussion.value.id}/lock`)
    discussion.value.is_locked = !discussion.value.is_locked
  } catch (error) {
    console.error('操作失败:', error)
  }
}

async function toggleHide() {
  try {
    await api.post(`/discussions/${discussion.value.id}/hide`)
    discussion.value.is_hidden = !discussion.value.is_hidden
  } catch (error) {
    console.error('操作失败:', error)
  }
}

async function deleteDiscussion() {
  if (!confirm('确定要删除这个讨论吗？此操作不可恢复！')) return

  try {
    await api.delete(`/discussions/${discussion.value.id}`)
    router.push('/')
  } catch (error) {
    console.error('删除失败:', error)
    alert('删除失败，请稍后重试')
  }
}

async function toggleSubscription() {
  if (!authStore.isAuthenticated || !discussion.value) {
    router.push('/login')
    return
  }

  togglingSubscription.value = true
  try {
    if (discussion.value.is_subscribed) {
      await api.delete(`/discussions/${discussion.value.id}/subscribe`)
      discussion.value.is_subscribed = false
    } else {
      await api.post(`/discussions/${discussion.value.id}/subscribe`)
      discussion.value.is_subscribed = true
    }
  } catch (error) {
    console.error('更新关注状态失败:', error)
    alert('操作失败，请稍后重试')
  } finally {
    togglingSubscription.value = false
  }
}

function formatDate(dateString) {
  return formatRelativeTime(dateString)
}
</script>

<style scoped>
.discussion-detail-page {
  padding: 30px 0;
  background: #f5f5f5;
  min-height: calc(100vh - 200px);
}

.layout {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 30px;
}

.main-content {
  background: white;
  padding: 30px;
  border-radius: 8px;
}

.discussion-header {
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 2px solid #f0f0f0;
}

.discussion-badges {
  display: flex;
  gap: 8px;
  margin-bottom: 15px;
}

.badge {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.badge-pinned {
  background: #ffc107;
  color: white;
}

.badge-locked {
  background: #999;
  color: white;
}

.badge-hidden {
  background: #e74c3c;
  color: white;
}

.discussion-header h1 {
  font-size: 32px;
  color: #333;
  margin-bottom: 15px;
}

.discussion-tags {
  display: flex;
  gap: 8px;
}

.tag {
  padding: 4px 12px;
  border-radius: 4px;
  color: white;
  font-size: 13px;
}

.tag:hover {
  text-decoration: none;
  filter: brightness(0.96);
}

.posts {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 30px;
}

.post-item {
  display: flex;
  gap: 20px;
  padding: 20px;
  background: #fafafa;
  border-radius: 8px;
  transition: all 0.2s;
}

.post-item:hover {
  background: #f5f5f5;
}

.post-item.is-hidden {
  opacity: 0.5;
}

.post-item.is-target {
  background: #fff8e1;
  box-shadow: 0 0 0 2px rgba(255, 193, 7, 0.38);
}

.post-avatar img {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  object-fit: cover;
}

.post-avatar .avatar-placeholder {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: #667eea;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 600;
}

.post-content {
  flex: 1;
}

.post-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  font-size: 14px;
}

.post-author {
  font-weight: 600;
  color: #667eea;
}

.post-author:hover {
  text-decoration: none;
}

.post-number {
  color: #999;
}

.post-time {
  color: #999;
}

.post-edited {
  color: #999;
  font-style: italic;
}

.post-body {
  margin-bottom: 15px;
  line-height: 1.6;
  color: #333;
}

.post-body :deep(pre) {
  background: #2d2d2d;
  color: #f8f8f2;
  padding: 15px;
  border-radius: 6px;
  overflow-x: auto;
}

.post-body :deep(code) {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
}

.post-body :deep(blockquote) {
  border-left: 4px solid #667eea;
  padding-left: 15px;
  margin: 15px 0;
  color: #666;
}

.post-footer {
  display: flex;
  gap: 15px;
}

.post-action {
  padding: 6px 12px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.post-action:hover {
  border-color: #667eea;
  color: #667eea;
}

.post-action.is-liked {
  background: #ffe0e0;
  border-color: #ff6b6b;
  color: #ff6b6b;
}

.post-action.danger:hover {
  border-color: #e74c3c;
  color: #e74c3c;
}

.load-more {
  text-align: center;
  margin-bottom: 30px;
}

.load-previous {
  margin-top: -10px;
}

.reply-placeholder {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
  background: #fafafa;
  border: 1px dashed #d7dee6;
  border-radius: 8px;
  margin-bottom: 20px;
  color: #7b8794;
  font-size: 13px;
}

.locked-notice, .login-notice {
  text-align: center;
  padding: 20px;
  background: #fff3cd;
  border-radius: 6px;
  color: #856404;
}

.sidebar {
  height: fit-content;
  position: sticky;
  top: 20px;
}

.sidebar-section {
  background: white;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.sidebar-section h3 {
  font-size: 16px;
  margin-bottom: 15px;
  color: #333;
}

.subscription-copy {
  color: #66717c;
  line-height: 1.6;
  margin-bottom: 14px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}

.info-item:last-child {
  border-bottom: none;
}

.info-item .label {
  color: #999;
  font-size: 14px;
}

.info-item .value {
  color: #333;
  font-size: 14px;
  font-weight: 500;
}

.value-link:hover {
  color: #4d698e;
  text-decoration: none;
}

.sidebar-section button {
  margin-bottom: 10px;
}

.sidebar-section button:last-child {
  margin-bottom: 0;
}

.full-width {
  width: 100%;
}

.scrubber {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.scrubber-status {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: #66717c;
  font-size: 13px;
}

.scrubber-range {
  width: 100%;
  accent-color: #4d698e;
}

.scrubber-actions {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.scrubber-actions button {
  margin-bottom: 0;
  padding: 8px;
  font-size: 12px;
}

.floating-composer {
  position: fixed;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  width: min(760px, calc(100vw - 32px));
  background: #f7f9fb;
  border: 1px solid #dbe2ea;
  border-radius: 10px 10px 0 0;
  box-shadow: 0 2px 8px rgba(31, 45, 61, 0.18);
  z-index: 900;
  overflow: hidden;
}

.floating-composer.is-minimized {
  width: min(540px, calc(100vw - 32px));
}

.floating-composer.is-expanded {
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  transform: none;
  width: auto;
  border-radius: 0;
  box-shadow: none;
}

.composer-handle {
  height: 14px;
  cursor: row-resize;
}

.composer-handle::before {
  content: '';
  display: block;
  width: 64px;
  height: 4px;
  border-radius: 999px;
  background: #d7dee6;
  margin: 6px auto 0;
}

.composer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 20px 10px;
  color: #4a5665;
}

.composer-title {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-weight: 400;
}

.composer-title span,
.composer-title small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.composer-title span {
  font-size: 14px;
  color: #445161;
}

.composer-title small {
  color: #7b8794;
  font-size: 12px;
  font-weight: 400;
}

.composer-controls {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.composer-controls button {
  border: 0;
  background: transparent;
  color: #6c7a89;
  border-radius: 4px;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.composer-controls button:hover {
  background: #e8edf3;
  color: #3f4b59;
}

.composer-controls button i {
  font-size: 13px;
}

.composer-controls button:disabled {
  cursor: default;
  opacity: 0.45;
}

.composer-body {
  padding: 0 20px 0;
}

.composer-body textarea {
  width: 100%;
  padding: 4px 0 12px;
  border: 0;
  border-radius: 0;
  background: transparent;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.7;
  resize: none;
  min-height: 176px;
  max-height: 42vh;
}

.floating-composer.is-expanded .composer-body textarea {
  min-height: calc(100vh - 170px);
  max-height: none;
}

.composer-body textarea:focus {
  outline: none;
  border: 0;
  box-shadow: none;
}

.composer-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 -20px;
  padding: 10px 20px;
  border-top: 1px solid #dbe2ea;
  flex-wrap: nowrap;
}

.composer-submit,
.composer-secondary {
  border: 0;
  border-radius: 4px;
  padding: 8px 14px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.composer-submit {
  background: #4d698e;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
}

.composer-submit:disabled {
  cursor: default;
  opacity: 0.6;
}

.composer-submit i {
  font-size: 13px;
}

.composer-formatting {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  white-space: nowrap;
}

.composer-formatting button {
  border: 0;
  background: transparent;
  color: #5b6776;
  border-radius: 4px;
  min-width: 28px;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}

.composer-formatting button:hover {
  background: #e8edf3;
  color: #354152;
}

.composer-formatting button i {
  font-size: 14px;
}

.composer-formatting button span {
  font-weight: 700;
  font-size: 14px;
  line-height: 1;
  white-space: nowrap;
}

.composer-secondary {
  background: transparent;
  color: #6b7786;
}

.composer-secondary:hover {
  background: #e8edf3;
  color: #425062;
}

.loading, .error {
  text-align: center;
  padding: 60px 20px;
  color: #666;
}

@media (max-width: 768px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .sidebar {
    position: static;
  }

  .post-item {
    flex-direction: column;
  }

  .floating-composer {
    bottom: 0;
    width: 100vw;
    border-radius: 10px 10px 0 0;
  }

  .floating-composer.is-expanded {
    width: 100vw;
  }

  .composer-toolbar {
    align-items: stretch;
    flex-wrap: wrap;
  }

  .composer-submit,
  .composer-secondary {
    justify-content: center;
  }

  .composer-formatting {
    order: 3;
    flex: 0 0 100%;
    padding-bottom: 2px;
  }
}
</style>
