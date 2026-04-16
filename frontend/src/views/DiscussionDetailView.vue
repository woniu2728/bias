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
              <span v-if="discussion.approval_status === 'pending'" class="badge badge-pending">待审核</span>
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

          <div v-if="hasPrevious" ref="previousTrigger" class="load-more load-previous">
            <button @click="loadPreviousPosts" class="secondary" :disabled="loadingPrevious">
              {{ loadingPrevious ? '加载中...' : '加载前面的回复' }}
            </button>
          </div>

          <!-- 帖子列表 -->
          <div class="posts">
            <template v-for="post in posts" :key="post.id">
              <div
                v-if="showUnreadDivider(post)"
                class="post-unread-divider"
              >
                <span>从这里开始是未读回复</span>
              </div>

              <article
                :id="`post-${post.number}`"
                class="post-item"
                :class="{ 'is-hidden': post.is_hidden, 'is-target': highlightedPostNumber === post.number }"
              >
                <div class="post-container">
                  <aside class="post-side">
                    <router-link :to="buildUserPath(post.user)" class="post-avatar-link" :title="getUserDisplayName(post.user)">
                      <div
                        v-if="!post.user.avatar_url"
                        class="post-avatar avatar-placeholder"
                        :style="{ backgroundColor: getUserAvatarColor(post.user) }"
                      >
                        {{ getUserInitial(post.user) }}
                      </div>
                      <img
                        v-else
                        class="post-avatar"
                        :src="post.user.avatar_url"
                        :alt="getUserDisplayName(post.user)"
                      />
                    </router-link>
                  </aside>

                  <div class="post-main">
                    <header class="post-header">
                      <div class="post-header-main">
                        <router-link :to="buildUserPath(post.user)" class="post-author">{{ getUserDisplayName(post.user) }}</router-link>
                        <button
                          type="button"
                          class="post-meta-link post-number"
                          :title="`跳转到第 ${post.number} 楼`"
                          @click="jumpToPost(post.number)"
                        >
                          #{{ post.number }}
                        </button>
                        <time class="post-time" :datetime="post.created_at" :title="formatAbsoluteDate(post.created_at)">
                          {{ formatDate(post.created_at) }}
                        </time>
                        <span v-if="post.edited_at" class="post-edited" :title="formatAbsoluteDate(post.edited_at)">已编辑</span>
                        <span v-if="post.approval_status === 'pending'" class="post-status">待审核</span>
                      </div>

                      <aside class="post-actions" :class="{ 'is-open': activePostMenuId === post.id }">
                        <button
                          v-if="canLikePost(post)"
                          type="button"
                          class="post-action"
                          :class="{ 'is-active': post.is_liked }"
                          :disabled="likePendingPostIds.includes(post.id)"
                          @click="toggleLike(post)"
                        >
                          <i class="fas fa-thumbs-up"></i>
                          <span>赞</span>
                        </button>
                        <button
                          v-if="authStore.isAuthenticated && !discussion.is_locked && !isSuspended"
                          type="button"
                          class="post-action"
                          @click="replyToPost(post)"
                        >
                          <i class="fas fa-reply"></i>
                          <span>回复</span>
                        </button>
                        <div v-if="hasPostControls(post)" class="post-controls" :class="{ 'is-open': activePostMenuId === post.id }">
                          <button
                            type="button"
                            class="post-action post-action--icon"
                            :aria-expanded="activePostMenuId === post.id"
                            @click.stop="togglePostMenu(post.id)"
                          >
                            <i class="fas fa-ellipsis-h"></i>
                          </button>
                          <div v-if="activePostMenuId === post.id" class="post-controls-menu">
                            <button v-if="canEditPost(post)" type="button" @click="handlePostMenuAction(() => editPost(post))">
                              编辑
                            </button>
                            <button v-if="canDeletePost(post)" type="button" class="is-danger" @click="handlePostMenuAction(() => deletePost(post))">
                              删除
                            </button>
                            <button v-if="canReportPost(post)" type="button" @click="handlePostMenuAction(() => openReportModal(post))">
                              举报
                            </button>
                          </div>
                        </div>
                      </aside>
                    </header>

                    <div class="post-body" v-html="post.content_html"></div>

                    <footer v-if="post.like_count > 0" class="post-footer">
                      <button
                        v-if="canLikePost(post)"
                        type="button"
                        class="post-feedback"
                        :class="{ 'is-active': post.is_liked }"
                        :disabled="likePendingPostIds.includes(post.id)"
                        @click="toggleLike(post)"
                      >
                        <i class="fas fa-thumbs-up"></i>
                        <span>{{ formatLikeSummary(post) }}</span>
                      </button>
                      <div
                        v-else
                        class="post-feedback"
                        :class="{ 'is-active': post.is_liked }"
                      >
                        <i class="fas fa-thumbs-up"></i>
                        <span>{{ formatLikeSummary(post) }}</span>
                      </div>
                    </footer>
                  </div>
                </div>
              </article>
            </template>
          </div>

          <!-- 加载更多 -->
          <div v-if="hasMore" ref="nextTrigger" class="load-more">
            <button @click="loadMorePosts" class="secondary" :disabled="loadingMore">
              {{ loadingMore ? '加载中...' : '加载更多' }}
            </button>
          </div>

          <div v-if="authStore.isAuthenticated && isSuspended" class="suspended-notice">
            {{ suspensionNotice }}
          </div>
          <div v-else-if="authStore.isAuthenticated && discussion.can_reply" class="reply-placeholder">
            <button @click="openComposer" class="primary">
              {{ hasActiveComposer ? '继续编辑回复' : '发表回复' }}
            </button>
            <span v-if="hasActiveComposer">已有未发布内容</span>
          </div>

          <div v-else-if="discussion.is_locked" class="locked-notice">
            此讨论已被锁定，无法回复
          </div>
          <div v-else-if="authStore.isAuthenticated" class="locked-notice">
            当前没有在此讨论下回复的权限
          </div>
          <div v-else class="login-notice">
            <router-link to="/login">登录</router-link> 后才能回复
          </div>
        </main>

        <!-- 侧边栏 -->
        <aside class="sidebar">
          <div
            v-if="discussion"
            ref="discussionActionsRef"
            class="sidebar-section sidebar-section--actions"
          >
            <button
              v-if="authStore.isAuthenticated"
              type="button"
              class="discussion-primary-action"
              :disabled="discussion.is_locked || isSuspended"
              @click="openComposer"
            >
              <i class="fas fa-reply"></i>
              {{ hasActiveComposer ? '继续回复' : '回复' }}
            </button>
            <button
              v-else
              type="button"
              class="discussion-primary-action"
              @click="goToLoginForReply"
            >
              <i class="fas fa-sign-in-alt"></i>
              登录后回复
            </button>

            <div v-if="authStore.isAuthenticated && !isSuspended" class="discussion-secondary-row">
              <button
                type="button"
                class="discussion-follow-action"
                :class="{
                  'is-active': discussion.is_subscribed,
                  'is-standalone': !canManageDiscussion
                }"
                :disabled="togglingSubscription"
                @click="toggleSubscription"
              >
                <i :class="discussion.is_subscribed ? 'fas fa-bell-slash' : 'far fa-star'"></i>
                {{ togglingSubscription ? '提交中...' : (discussion.is_subscribed ? '取消关注' : '关注') }}
              </button>
              <button
                v-if="canManageDiscussion"
                type="button"
                class="discussion-menu-toggle"
                :class="{ 'is-active': showDiscussionMenu }"
                @click="toggleDiscussionMenu"
              >
                <i class="fas fa-chevron-down"></i>
              </button>
            </div>

            <div
              v-if="showDiscussionMenu && canManageDiscussion"
              class="discussion-actions-menu"
            >
              <button type="button" @click="handleDiscussionMenuAction(togglePin)">
                {{ discussion.is_sticky ? '取消置顶' : '置顶讨论' }}
              </button>
              <button type="button" @click="handleDiscussionMenuAction(toggleLock)">
                {{ discussion.is_locked ? '解除锁定' : '锁定讨论' }}
              </button>
              <button type="button" @click="handleDiscussionMenuAction(toggleHide)">
                {{ discussion.is_hidden ? '恢复显示' : '隐藏讨论' }}
              </button>
              <button type="button" class="is-danger" @click="handleDiscussionMenuAction(deleteDiscussion)">
                删除讨论
              </button>
            </div>

            <p v-if="authStore.isAuthenticated && hasActiveComposer" class="discussion-action-copy">
              当前讨论已有未发布回复草稿。
            </p>
            <p v-else-if="authStore.isAuthenticated && discussion.is_subscribed" class="discussion-action-copy">
              你会收到这条讨论后续回复的通知。
            </p>
            <p v-else-if="authStore.isAuthenticated && discussion.is_locked" class="discussion-action-copy">
              当前讨论已锁定，暂时无法继续回复。
            </p>
            <p v-else-if="authStore.isAuthenticated && isSuspended" class="discussion-action-copy discussion-action-copy--warning">
              {{ suspensionNotice }}
            </p>
          </div>

          <div v-if="authStore.isAuthenticated && isSuspended" class="sidebar-section sidebar-section--warning">
            <h3>账号状态</h3>
            <p class="subscription-copy">{{ suspensionNotice }}</p>
          </div>

          <div class="sidebar-section sidebar-section--scrubber">
            <div ref="scrubberPanel" class="scrubber-panel">
              <button type="button" class="scrubber-link" @click="jumpToPost(1)">
                <i class="fas fa-angle-double-up"></i>
                原帖
              </button>

              <div
                ref="scrubberTrack"
                class="scrubber-scrollbar"
                :style="scrubberScrollbarStyle"
                @click="handleScrubberTrackClick"
              >
                <div class="scrubber-before" :style="{ height: `${scrubberBeforePercent}%` }"></div>
                <div
                  v-if="unreadCount"
                  class="scrubber-unread"
                  :style="{
                    top: `${unreadTopPercent}%`,
                    height: `${unreadHeightPercent}%`
                  }"
                >
                  <span>{{ unreadCount }} 未读</span>
                </div>
                <div
                  class="scrubber-handle"
                  :style="{
                    top: `${scrubberBeforePercent}%`,
                    height: `${scrubberHandlePercent}%`
                  }"
                  :class="{ 'is-dragging': scrubberDragging }"
                  @mousedown="handleScrubberMouseDown"
                  @touchstart="handleScrubberMouseDown"
                  @click.stop
                >
                  <div class="scrubber-bar"></div>
                  <div class="scrubber-info">
                    <strong>{{ scrubberPositionText }}</strong>
                    <span class="scrubber-description">{{ scrubberDescription }}</span>
                  </div>
                </div>
                <div class="scrubber-after" :style="{ height: `${scrubberAfterPercent}%` }"></div>
              </div>

              <button type="button" class="scrubber-link" @click="jumpToPost(maxPostNumber)">
                <i class="fas fa-angle-double-down"></i>
                现在
              </button>
            </div>
          </div>

        </aside>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import { useModalStore } from '@/stores/modal'
import PostReportModal from '@/components/modals/PostReportModal.vue'
import api from '@/api'
import {
  buildTagPath,
  buildUserPath,
  formatRelativeTime,
  getUserAvatarColor,
  getUserDisplayName,
  getUserInitial,
  normalizeDiscussion,
  normalizePost,
  unwrapList
} from '@/utils/forum'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()
const modalStore = useModalStore()

const discussion = ref(null)
const posts = ref([])
const loading = ref(true)
const loadingMore = ref(false)
const loadingPrevious = ref(false)
const firstLoadedPage = ref(1)
const lastLoadedPage = ref(1)
const totalPosts = ref(0)
const pageLimit = 20
const previousTrigger = ref(null)
const nextTrigger = ref(null)
const scrubberPanel = ref(null)
const scrubberTrack = ref(null)
const discussionActionsRef = ref(null)

const togglingSubscription = ref(false)
const highlightedPostNumber = ref(null)
const currentVisiblePostNumber = ref(1)
const currentVisiblePostProgress = ref(1)
const visiblePostCount = ref(1)
const showDiscussionMenu = ref(false)
const activePostMenuId = ref(null)
const likePendingPostIds = ref([])
const scrubberTrackHeight = ref(300)
const scrubberTrackMaxHeight = ref(null)
const scrubberDragging = ref(false)
const scrubberPreviewNumber = ref(null)
let scrollFrame = null
let nearUrlTimer = null
let readStateTimer = null
let lastReportedReadNumber = 0
let scrubberResizeObserver = null
let scrubberDragStartY = 0
let scrubberDragStartNumber = 1

const canManageDiscussion = computed(() => {
  return authStore.user?.is_staff || authStore.user?.id === discussion.value?.user.id
})
const isSuspended = computed(() => Boolean(authStore.user?.is_suspended))
const suspensionNotice = computed(() => {
  if (!isSuspended.value) return ''

  const user = authStore.user || {}
  if (user.suspend_message) {
    return user.suspended_until
      ? `账号已被封禁至 ${formatAbsoluteDate(user.suspended_until)}。${user.suspend_message}`
      : `账号当前已被封禁。${user.suspend_message}`
  }

  return user.suspended_until
    ? `账号已被封禁至 ${formatAbsoluteDate(user.suspended_until)}，暂时无法回复、点赞、举报或关注讨论。`
    : '账号当前已被封禁，暂时无法回复、点赞、举报或关注讨论。'
})

function getUiErrorMessage(error, fallback = '操作失败，请稍后重试') {
  return error.response?.data?.error || error.response?.data?.detail || error.message || fallback
}

function showSuspensionAlert() {
  return modalStore.alert({
    title: '账号已被封禁',
    message: suspensionNotice.value,
    tone: 'danger'
  })
}

const hasPrevious = computed(() => firstLoadedPage.value > 1)
const hasMore = computed(() => totalPosts.value > 0 && lastLoadedPage.value * pageLimit < totalPosts.value)
const hasActiveComposer = computed(() => {
  if (!discussion.value) return false
  if (!['reply', 'edit'].includes(composerStore.current.type)) return false
  return Number(composerStore.current.discussionId) === Number(discussion.value.id)
})
const targetNearPost = computed(() => {
  const value = Number(route.query.near)
  return Number.isFinite(value) && value > 0 ? value : null
})
const maxPostNumber = computed(() => {
  return discussion.value?.last_post_number || discussion.value?.comment_count || 1
})
const unreadCount = computed(() => {
  return Math.max(Number(discussion.value?.unread_count || 0), 0)
})
const unreadStartPostNumber = computed(() => {
  if (!unreadCount.value) return null
  const lastRead = Number(discussion.value?.last_read_post_number || 0)
  return Math.min(maxPostNumber.value, Math.max(1, lastRead + 1))
})
const scrubberDisplayNumber = computed(() => {
  return clampPostPosition(scrubberPreviewNumber.value ?? currentVisiblePostProgress.value)
})
const scrubberDisplayPostNumber = computed(() => {
  return sanitizePostNumber(scrubberDisplayNumber.value)
})
const scrubberScrollbarStyle = computed(() => {
  if (!scrubberTrackMaxHeight.value) return {}
  return {
    maxHeight: `${scrubberTrackMaxHeight.value}px`
  }
})
const scrubberHasExactLoadedPost = computed(() => {
  return posts.value.some(post => post.number === scrubberDisplayPostNumber.value)
})
const scrubberDisplayPost = computed(() => {
  if (!posts.value.length) return null

  const exactMatch = posts.value.find(post => post.number === scrubberDisplayPostNumber.value)
  if (exactMatch) return exactMatch

  return posts.value.reduce((closest, post) => {
    if (!closest) return post
    return Math.abs(post.number - scrubberDisplayPostNumber.value) < Math.abs(closest.number - scrubberDisplayPostNumber.value)
      ? post
      : closest
  }, null)
})
const scrubberDescription = computed(() => {
  if (scrubberDragging.value && !scrubberHasExactLoadedPost.value) {
    return `松开后跳转到第 ${scrubberDisplayPostNumber.value} 楼`
  }

  const createdAt = scrubberDisplayPost.value?.created_at
  if (!createdAt) {
    return scrubberDragging.value ? '松开后跳转到该楼层' : '当前阅读位置'
  }

  return formatRelativeTime(createdAt)
})
const scrubberPositionText = computed(() => {
  return `${scrubberDisplayPostNumber.value} / ${maxPostNumber.value}`
})
const scrubberPercentPerPost = computed(() => {
  const total = Math.max(maxPostNumber.value, 1)
  const visible = Math.min(total, Math.max(visiblePostCount.value, 1))
  const trackHeight = Math.max(scrubberTrackHeight.value, 1)
  const minPercentVisible = (50 / trackHeight) * 100
  const visiblePercent = Math.max(100 / total, minPercentVisible / visible)
  const indexPercent = total === visible ? 0 : (100 - visiblePercent * visible) / (total - visible)

  return {
    total,
    visible,
    visiblePercent,
    indexPercent
  }
})
const scrubberHandlePercent = computed(() => {
  const { total, visible, visiblePercent } = scrubberPercentPerPost.value
  return Math.min(100, Math.max(visiblePercent * visible, total === visible ? 100 : 0))
})
const scrubberBeforePercent = computed(() => {
  const { total, visible, indexPercent } = scrubberPercentPerPost.value
  const handle = scrubberHandlePercent.value
  if (total <= visible) return 0

  const displayNumber = Math.min(total, Math.max(1, scrubberDisplayNumber.value))
  return Math.max(0, Math.min(100 - handle, indexPercent * Math.min(displayNumber - 1, total - visible)))
})
const scrubberAfterPercent = computed(() => {
  return Math.max(0, 100 - scrubberBeforePercent.value - scrubberHandlePercent.value)
})
const unreadTopPercent = computed(() => {
  return getPostProgressPercent(unreadStartPostNumber.value || 1)
})
const unreadHeightPercent = computed(() => {
  return unreadCount.value ? Math.max(0, 100 - unreadTopPercent.value) : 0
})

onMounted(async () => {
  await refreshDiscussion()
  window.addEventListener('scroll', handlePostScroll, { passive: true })
  window.addEventListener('resize', handlePostScroll, { passive: true })
  window.addEventListener('resize', syncScrubberTrackMetrics, { passive: true })
  window.addEventListener('pyflarum:reply-created', handleReplyCreated)
  window.addEventListener('pyflarum:post-updated', handlePostUpdated)
  document.addEventListener('mousedown', handleDocumentMouseDown)
  await nextTick()
  syncScrubberTrackMetrics()
  attachScrubberObserver()
  updateVisiblePostFromScroll()
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', handlePostScroll)
  window.removeEventListener('resize', handlePostScroll)
  window.removeEventListener('resize', syncScrubberTrackMetrics)
  window.removeEventListener('pyflarum:reply-created', handleReplyCreated)
  window.removeEventListener('pyflarum:post-updated', handlePostUpdated)
  document.removeEventListener('mousedown', handleDocumentMouseDown)
  detachScrubberDragListeners()
  detachScrubberObserver()
  if (scrollFrame) {
    cancelAnimationFrame(scrollFrame)
  }
  if (nearUrlTimer) {
    clearTimeout(nearUrlTimer)
  }
  if (readStateTimer) {
    clearTimeout(readStateTimer)
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
    lastReportedReadNumber = Number(discussion.value?.last_read_post_number || 0)
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
  nextTick(() => {
    syncScrubberTrackMetrics()
    updateVisiblePostFromScroll()
    maybeAutoLoadPosts()
  })
}

function appendPosts(data) {
  const items = unwrapList(data).map(normalizePost)
  posts.value.push(...items)
  lastLoadedPage.value = data.page || lastLoadedPage.value + 1
  totalPosts.value = data.total || totalPosts.value
  nextTick(() => {
    syncScrubberTrackMetrics()
    updateVisiblePostFromScroll()
    maybeAutoLoadPosts()
  })
}

function prependPosts(data) {
  const anchorNumber = posts.value[0]?.number
  const anchorTop = anchorNumber ? document.getElementById(`post-${anchorNumber}`)?.getBoundingClientRect().top : null
  const items = unwrapList(data).map(normalizePost)
  posts.value.unshift(...items)
  firstLoadedPage.value = data.page || Math.max(1, firstLoadedPage.value - 1)
  totalPosts.value = data.total || totalPosts.value
  nextTick(() => {
    if (anchorNumber && anchorTop !== null) {
      const newTop = document.getElementById(`post-${anchorNumber}`)?.getBoundingClientRect().top
      if (typeof newTop === 'number') {
        window.scrollBy({ top: newTop - anchorTop })
      }
    }
    syncScrubberTrackMetrics()
    updateVisiblePostFromScroll()
    maybeAutoLoadPosts()
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
  const targetNumber = normalizePostNumber(number)
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
  activePostMenuId.value = null
  currentVisiblePostNumber.value = normalizePostNumber(route.query.near) || 1
  currentVisiblePostProgress.value = currentVisiblePostNumber.value
  scrubberPreviewNumber.value = null
}

function handlePostScroll() {
  if (scrollFrame) return

  scrollFrame = requestAnimationFrame(() => {
    scrollFrame = null
    syncScrubberTrackMetrics()
    updateVisiblePostFromScroll()
    maybeAutoLoadPosts()
  })
}

function maybeAutoLoadPosts() {
  if (hasPrevious.value && !loadingPrevious.value && previousTrigger.value) {
    const previousRect = previousTrigger.value.getBoundingClientRect()
    if (previousRect.top <= 220) {
      loadPreviousPosts()
    }
  }

  if (hasMore.value && !loadingMore.value && nextTrigger.value) {
    const nextRect = nextTrigger.value.getBoundingClientRect()
    if (nextRect.top - window.innerHeight <= 280) {
      loadMorePosts()
    }
  }
}

function showUnreadDivider(post) {
  return Boolean(
    authStore.isAuthenticated &&
    unreadStartPostNumber.value &&
    unreadCount.value > 0 &&
    Number(post?.number) === Number(unreadStartPostNumber.value)
  )
}

function handleDocumentMouseDown(event) {
  if (showDiscussionMenu.value && !discussionActionsRef.value?.contains(event.target)) {
    showDiscussionMenu.value = false
  }

  if (activePostMenuId.value && !(event.target instanceof Element && event.target.closest('.post-controls'))) {
    activePostMenuId.value = null
  }
}

function updateVisiblePostFromScroll() {
  if (!posts.value.length) return

  const anchorY = 120
  const viewportTop = 96
  const viewportBottom = window.innerHeight
  let closestPostNumber = posts.value[0].number
  let closestDistance = Number.POSITIVE_INFINITY
  let visibleCount = 0
  let indexFromViewport = null
  let lastVisiblePostNumber = posts.value[0].number

  for (const post of posts.value) {
    const element = document.getElementById(`post-${post.number}`)
    if (!element) continue

    const rect = element.getBoundingClientRect()
    if (rect.bottom < viewportTop) continue
    if (rect.top > viewportBottom) break

    const height = rect.height || 1
    const visibleTop = Math.max(0, viewportTop - rect.top)
    const visibleBottom = Math.min(height, viewportBottom - rect.top)
    const visiblePart = visibleBottom - visibleTop

    if (indexFromViewport === null) {
      indexFromViewport = post.number + visibleTop / height
    }

    if (visiblePart > 0) {
      visibleCount += visiblePart / height
      lastVisiblePostNumber = post.number
    }

    const distance = Math.abs(rect.top - anchorY)
    if (distance < closestDistance) {
      closestDistance = distance
      closestPostNumber = post.number
    }
  }

  const scrollBottom = window.scrollY + window.innerHeight
  const documentBottom = document.documentElement.scrollHeight
  const isAtPageBottom = documentBottom - scrollBottom <= 24
  const trackedPostNumber = isAtPageBottom ? lastVisiblePostNumber : closestPostNumber

  visiblePostCount.value = Math.max(1, visibleCount)
  currentVisiblePostProgress.value = isAtPageBottom
    ? maxPostNumber.value
    : clampPostPosition(indexFromViewport ?? trackedPostNumber)

  if (trackedPostNumber !== currentVisiblePostNumber.value) {
    currentVisiblePostNumber.value = trackedPostNumber
    scheduleNearUrlSync(trackedPostNumber)
    scheduleReadStateSync(trackedPostNumber)
  }
}

function clampPostPosition(value) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return 1
  return Math.min(maxPostNumber.value, Math.max(1, parsed))
}

function sanitizePostNumber(value) {
  return Math.floor(clampPostPosition(value))
}

function normalizePostNumber(value) {
  return sanitizePostNumber(value)
}

function getPostProgressPercent(value) {
  const total = Math.max(maxPostNumber.value, 1)
  const number = Math.min(total, Math.max(1, Number(value) || 1))
  if (total <= 1) return 0
  return ((number - 1) / (total - 1)) * 100
}

function handleScrubberTrackClick(event) {
  if (scrubberDragging.value) return

  const track = scrubberTrack.value
  if (!track) return

  const rect = track.getBoundingClientRect()
  if (!rect.height) return

  const percent = Math.max(0, Math.min(1, (getPointerClientY(event) - rect.top) / rect.height))
  const targetNumber = getPostNumberFromTrackPercent(percent, true)
  jumpToPost(targetNumber)
}

function handleScrubberMouseDown(event) {
  const clientY = getPointerClientY(event)
  if (clientY === null) return

  event.preventDefault()
  scrubberDragging.value = true
  scrubberPreviewNumber.value = scrubberDisplayNumber.value
  scrubberDragStartY = clientY
  scrubberDragStartNumber = scrubberDisplayNumber.value
  document.body.classList.add('scrubber-dragging')
  window.addEventListener('mousemove', handleScrubberMouseMove)
  window.addEventListener('mouseup', handleScrubberMouseUp)
  window.addEventListener('touchmove', handleScrubberMouseMove, { passive: false })
  window.addEventListener('touchend', handleScrubberMouseUp)
}

function handleScrubberMouseMove(event) {
  if (!scrubberDragging.value) return

  event.preventDefault()
  const clientY = getPointerClientY(event)
  if (clientY === null) return

  const trackHeight = Math.max(scrubberTrackHeight.value, 1)
  const deltaPixels = clientY - scrubberDragStartY
  const deltaPercent = (deltaPixels / trackHeight) * 100
  const percentPerPost = scrubberPercentPerPost.value.indexPercent
  const nextNumber = percentPerPost > 0
    ? scrubberDragStartNumber + deltaPercent / percentPerPost
    : 1 + (deltaPercent / 100) * Math.max(maxPostNumber.value - 1, 0)

  scrubberPreviewNumber.value = clampPostPosition(nextNumber)
}

function handleScrubberMouseUp() {
  if (!scrubberDragging.value) return

  scrubberDragging.value = false
  detachScrubberDragListeners()
  const targetNumber = normalizePostNumber(scrubberPreviewNumber.value ?? currentVisiblePostNumber.value)
  scrubberPreviewNumber.value = null
  jumpToPost(targetNumber)
}

function detachScrubberDragListeners() {
  document.body.classList.remove('scrubber-dragging')
  window.removeEventListener('mousemove', handleScrubberMouseMove)
  window.removeEventListener('mouseup', handleScrubberMouseUp)
  window.removeEventListener('touchmove', handleScrubberMouseMove)
  window.removeEventListener('touchend', handleScrubberMouseUp)
}

function attachScrubberObserver() {
  detachScrubberObserver()
  if (!scrubberTrack.value || typeof ResizeObserver === 'undefined') return

  scrubberResizeObserver = new ResizeObserver(() => {
    syncScrubberTrackMetrics()
  })
  scrubberResizeObserver.observe(scrubberTrack.value)
}

function detachScrubberObserver() {
  scrubberResizeObserver?.disconnect()
  scrubberResizeObserver = null
}

function syncScrubberTrackMetrics() {
  const panelRect = scrubberPanel.value?.getBoundingClientRect()
  const trackRect = scrubberTrack.value?.getBoundingClientRect()
  const height = trackRect?.height

  if (panelRect && trackRect && window.innerWidth > 768) {
    const panelChrome = panelRect.height - trackRect.height
    const availableHeight = Math.floor(window.innerHeight - panelRect.top - panelChrome - 24)
    scrubberTrackMaxHeight.value = Math.max(50, availableHeight)
  } else {
    scrubberTrackMaxHeight.value = null
  }

  if (height) {
    scrubberTrackHeight.value = height
  }
}

function getPostNumberFromTrackPercent(percent, centerHandle = false) {
  const clampedPercent = Math.max(0, Math.min(100, percent * 100))
  const { total, visible, indexPercent } = scrubberPercentPerPost.value

  if (total <= visible || indexPercent <= 0) {
    return normalizePostNumber(1 + (clampedPercent / 100) * Math.max(total - 1, 0))
  }

  const centeredPercent = clampedPercent - (centerHandle ? scrubberHandlePercent.value / 2 : 0)
  return normalizePostNumber(1 + centeredPercent / indexPercent)
}

function getPointerClientY(event) {
  if (typeof event?.clientY === 'number') return event.clientY
  const touch = event?.touches?.[0] || event?.changedTouches?.[0]
  return typeof touch?.clientY === 'number' ? touch.clientY : null
}

function toggleDiscussionMenu() {
  showDiscussionMenu.value = !showDiscussionMenu.value
}

function hasPostControls(post) {
  return canEditPost(post) || canDeletePost(post) || canReportPost(post)
}

function togglePostMenu(postId) {
  activePostMenuId.value = activePostMenuId.value === postId ? null : postId
}

async function handlePostMenuAction(action) {
  activePostMenuId.value = null
  await action()
}

async function handleDiscussionMenuAction(action) {
  showDiscussionMenu.value = false
  await action()
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

function scheduleReadStateSync(number) {
  if (!authStore.isAuthenticated || !discussion.value) return

  const targetNumber = normalizePostNumber(number)
  const currentRead = Number(discussion.value.last_read_post_number || 0)
  if (targetNumber <= Math.max(currentRead, lastReportedReadNumber)) return

  if (readStateTimer) {
    clearTimeout(readStateTimer)
  }

  readStateTimer = setTimeout(async () => {
    try {
      const data = await api.post(`/discussions/${discussion.value.id}/read`, {
        last_read_post_number: targetNumber
      })
      if (!discussion.value) return
      lastReportedReadNumber = Number(data.last_read_post_number || targetNumber)
      discussion.value.last_read_post_number = lastReportedReadNumber
      discussion.value.last_read_at = data.last_read_at || discussion.value.last_read_at
      discussion.value.unread_count = Math.max((discussion.value.last_post_number || 0) - lastReportedReadNumber, 0)
      discussion.value.is_unread = discussion.value.unread_count > 0
      window.dispatchEvent(new CustomEvent('pyflarum:discussion-read-state-updated', {
        detail: {
          discussionId: discussion.value.id,
          lastReadPostNumber: lastReportedReadNumber,
          lastReadAt: discussion.value.last_read_at,
          unreadCount: discussion.value.unread_count
        }
      }))
    } catch (error) {
      console.error('更新讨论阅读状态失败:', error)
    }
  }, 400)
}

async function toggleLike(post) {
  if (!authStore.isAuthenticated) {
    router.push('/login')
    return
  }
  if (!canLikePost(post)) {
    return
  }
  if (isSuspended.value) {
    await showSuspensionAlert()
    return
  }
  if (likePendingPostIds.value.includes(post.id)) {
    return
  }

  likePendingPostIds.value.push(post.id)
  const previousLiked = Boolean(post.is_liked)
  const previousLikeCount = Number(post.like_count || 0)
  try {
    if (previousLiked) {
      post.like_count = Math.max(0, previousLikeCount - 1)
      post.is_liked = false
      await api.delete(`/posts/${post.id}/like`)
    } else {
      post.like_count = previousLikeCount + 1
      post.is_liked = true
      await api.post(`/posts/${post.id}/like`)
    }
  } catch (error) {
    post.like_count = previousLikeCount
    post.is_liked = previousLiked
    console.error('点赞失败:', error)
    await modalStore.alert({
      title: '点赞失败',
      message: getUiErrorMessage(error, '请稍后重试'),
      tone: 'danger'
    })
  } finally {
    likePendingPostIds.value = likePendingPostIds.value.filter(id => id !== post.id)
  }
}

function replyToPost(post) {
  if (isSuspended.value) {
    showSuspensionAlert()
    return
  }
  composerStore.openReplyComposer({
    source: 'discussion-detail',
    discussionId: discussion.value?.id,
    discussionTitle: discussion.value?.title || '',
    postId: post.id,
    postNumber: post.number,
    username: post.user.username,
    initialContent: `@${post.user.username} `
  })
}

function editPost(post) {
  if (isSuspended.value) {
    showSuspensionAlert()
    return
  }
  composerStore.openEditPostComposer({
    source: 'discussion-detail',
    discussionId: discussion.value?.id,
    discussionTitle: discussion.value?.title || '',
    postId: post.id,
    postNumber: post.number,
    username: post.user.username,
    initialContent: post.content
  })
}

function openComposer() {
  if (isSuspended.value) {
    showSuspensionAlert()
    return
  }
  if (hasActiveComposer.value) {
    composerStore.showComposer()
    return
  }

  composerStore.openReplyComposer({
    source: 'discussion-detail',
    discussionId: discussion.value?.id,
    discussionTitle: discussion.value?.title || '',
    postId: null,
    postNumber: null,
    username: '',
    initialContent: ''
  })
}

function goToLoginForReply() {
  router.push({
    name: 'login',
    query: {
      redirect: route.fullPath
    }
  })
}

async function handleReplyCreated(event) {
  const detail = event.detail || {}
  if (!discussion.value || Number(detail.discussionId) !== Number(discussion.value.id)) return
  if (!detail.post) return

  const newPost = normalizePost(detail.post)
  if (posts.value.some(post => post.id === newPost.id)) return

  posts.value.push(newPost)
  discussion.value.comment_count = (discussion.value.comment_count || 0) + 1
  discussion.value.last_post_id = newPost.id
  discussion.value.last_post_number = Math.max(discussion.value.last_post_number || 0, newPost.number || 0)
  discussion.value.last_posted_at = newPost.created_at || discussion.value.last_posted_at
  totalPosts.value = Math.max(totalPosts.value + 1, posts.value.length)
  lastLoadedPage.value = Math.max(lastLoadedPage.value, Math.ceil(totalPosts.value / pageLimit))
  lastReportedReadNumber = Math.max(lastReportedReadNumber, newPost.number || 0)
  discussion.value.last_read_post_number = Math.max(Number(discussion.value.last_read_post_number || 0), newPost.number || 0)
  discussion.value.last_read_at = newPost.created_at || discussion.value.last_read_at
  discussion.value.unread_count = Math.max((discussion.value.last_post_number || 0) - discussion.value.last_read_post_number, 0)
  discussion.value.is_unread = discussion.value.unread_count > 0
  if (authStore.user?.preferences?.follow_after_reply) {
    discussion.value.is_subscribed = true
  }

  window.dispatchEvent(new CustomEvent('pyflarum:discussion-read-state-updated', {
    detail: {
      discussionId: discussion.value.id,
      lastReadPostNumber: discussion.value.last_read_post_number,
      lastReadAt: discussion.value.last_read_at,
      unreadCount: discussion.value.unread_count
    }
  }))

  await scrollToPost(newPost.number)
}

function handlePostUpdated(event) {
  const detail = event.detail || {}
  if (!discussion.value || Number(detail.discussionId) !== Number(discussion.value.id)) return
  if (!detail.post) return

  const updatedPost = normalizePost(detail.post)
  const index = posts.value.findIndex(post => post.id === updatedPost.id)
  if (index !== -1) {
    posts.value[index] = updatedPost
  }
}

async function deletePost(post) {
  const confirmed = await modalStore.confirm({
    title: '删除回复',
    message: '确定要删除这条回复吗？',
    confirmText: '删除',
    cancelText: '取消',
    tone: 'danger'
  })
  if (!confirmed) return

  try {
    await api.delete(`/posts/${post.id}`)
    posts.value = posts.value.filter(p => p.id !== post.id)
    discussion.value.comment_count--
    totalPosts.value = Math.max(0, totalPosts.value - 1)
  } catch (error) {
    console.error('删除失败:', error)
    await modalStore.alert({
      title: '删除失败',
      message: '请稍后重试',
      tone: 'danger'
    })
  }
}

function canEditPost(post) {
  if (isSuspended.value) return false
  return authStore.user?.id === post.user.id || authStore.user?.is_staff
}

function canDeletePost(post) {
  if (isSuspended.value) return false
  return authStore.user?.id === post.user.id || authStore.user?.is_staff
}

function canLikePost(post) {
  if (!authStore.isAuthenticated) return false
  if (isSuspended.value) return false
  return Boolean(post?.can_like ?? (post?.user?.id !== authStore.user?.id))
}

function canReportPost(post) {
  if (!authStore.isAuthenticated) return false
  if (isSuspended.value) return false
  if (!post?.user?.id) return false
  if (post.user.id === authStore.user?.id) return false
  return true
}

async function openReportModal(post) {
  if (isSuspended.value) {
    await showSuspensionAlert()
    return
  }
  activePostMenuId.value = null

  try {
    const result = await modalStore.show(
      PostReportModal,
      {
        post,
        submitReport: payload => api.post(`/posts/${post.id}/report`, payload)
      },
      {
        size: 'small'
      }
    )

    if (result?.reported) {
      await modalStore.alert({
        title: '举报已提交',
        message: '管理员会尽快处理。'
      })
    }
  } catch (error) {
    console.error('举报失败:', error)
    await modalStore.alert({
      title: '举报失败',
      message: getUiErrorMessage(error, '请稍后重试'),
      tone: 'danger'
    })
  }
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
  const confirmed = await modalStore.confirm({
    title: '删除讨论',
    message: '确定要删除这个讨论吗？此操作不可恢复！',
    confirmText: '删除',
    cancelText: '取消',
    tone: 'danger'
  })
  if (!confirmed) return

  try {
    await api.delete(`/discussions/${discussion.value.id}`)
    router.push('/')
  } catch (error) {
    console.error('删除失败:', error)
    await modalStore.alert({
      title: '删除失败',
      message: '请稍后重试',
      tone: 'danger'
    })
  }
}

async function toggleSubscription() {
  if (!authStore.isAuthenticated || !discussion.value) {
    router.push('/login')
    return
  }
  if (isSuspended.value) {
    await showSuspensionAlert()
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
    await modalStore.alert({
      title: '更新关注失败',
      message: getUiErrorMessage(error, '请稍后重试'),
      tone: 'danger'
    })
  } finally {
    togglingSubscription.value = false
  }
}

function formatDate(dateString) {
  return formatRelativeTime(dateString)
}

function formatLikeSummary(post) {
  const count = Number(post?.like_count || 0)
  if (count <= 0) return ''

  if (post?.is_liked) {
    return count === 1 ? '你赞了这条回复' : `你和其他 ${count - 1} 人赞了这条回复`
  }

  return `${count} 人赞了这条回复`
}

function formatAbsoluteDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知时间'
  return date.toLocaleString('zh-CN')
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

.badge-pending {
  background: #fff3cd;
  color: #856404;
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
  gap: 0;
  margin-bottom: 30px;
}

.post-unread-divider {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 10px 0 4px;
  color: #cf6a2b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.post-unread-divider::before,
.post-unread-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(207, 106, 43, 0.28);
}

.post-item {
  position: relative;
  padding: 22px 0 24px;
  transition: opacity 0.2s, transform 0.2s;
}

.post-item::after {
  content: '';
  display: block;
  width: calc(100% - 84px);
  height: 1px;
  margin-left: auto;
  background: #e6ecf1;
}

.post-item:last-of-type::after {
  display: none;
}

.post-item.is-hidden {
  opacity: 0.52;
}

.post-item.is-target .post-main {
  background: #fffaf0;
  box-shadow: 0 0 0 2px rgba(231, 124, 47, 0.18);
  border-radius: 10px;
  margin: -12px -16px 0 0;
  padding: 12px 16px 16px;
}

.post-container {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 0;
}

.post-side {
  padding-top: 2px;
}

.post-avatar-link {
  display: inline-flex;
  text-decoration: none;
}

.post-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  object-fit: cover;
  display: block;
}

.avatar-placeholder.post-avatar {
  background: #56739a;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
}

.post-main {
  min-width: 0;
  padding-top: 2px;
}

.post-header {
  margin-bottom: 15px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.post-header-main {
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  color: #7b8794;
  font-size: 14px;
}

.post-author {
  color: #1f2d3d;
  font-weight: 700;
  font-size: 15px;
}

.post-author:hover {
  text-decoration: none;
  color: #2c4f7b;
}

.post-meta-link,
.post-time,
.post-edited {
  color: #7b8794;
  font-size: 13px;
}

.post-meta-link {
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
}

.post-meta-link:hover,
.post-time:hover {
  color: #516174;
}

.post-edited {
  cursor: default;
}

.post-status {
  color: #8b6a17;
  background: #fff3cd;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 700;
}

.post-body {
  position: relative;
  overflow: auto;
  overflow-wrap: break-word;
  color: #2c3a47;
  font-size: 14px;
  line-height: 1.7;
}

.post-body :deep(p),
.post-body :deep(ul),
.post-body :deep(ol),
.post-body :deep(blockquote) {
  margin-bottom: 1em;
}

.post-body :deep(a) {
  border-bottom: 1px solid #dde5ec;
  font-weight: 600;
}

.post-body :deep(a:hover),
.post-body :deep(a:focus),
.post-body :deep(a:active) {
  text-decoration: none;
  border-color: #4c6b90;
}

.post-body :deep(blockquote) {
  margin: 1em 0;
  border: 0;
  border-top: 2px dotted #f5f7fa;
  border-bottom: 2px dotted #f5f7fa;
  border-radius: 10px;
  padding: 8px 15px;
  background: #eef3f7;
  color: #66717c;
}

.post-body :deep(code) {
  font-family: source-code-pro, Monaco, Consolas, 'Courier New', monospace;
  padding: 5px;
  border-radius: 4px;
  background: #edf2f7;
  color: #4a5663;
  line-height: 1.3;
  font-size: 90%;
}

.post-body :deep(pre) {
  border: 0;
  padding: 0;
  border-radius: 10px;
  background: #24313d;
  color: #eef3f7;
  font-size: 90%;
  overflow-wrap: normal;
}

.post-body :deep(pre code) {
  display: block;
  padding: 1em;
  border-radius: 0;
  background: none;
  color: inherit;
  line-height: inherit;
  font-size: 100%;
  overflow-x: auto;
  max-height: max(50vh, 250px);
}

.post-body :deep(h1),
.post-body :deep(h2),
.post-body :deep(h3),
.post-body :deep(h4),
.post-body :deep(h5),
.post-body :deep(h6) {
  margin-top: 1em;
  margin-bottom: 16px;
  font-weight: 700;
}

.post-body :deep(*:first-child) {
  margin-top: 0 !important;
}

.post-body :deep(img),
.post-body :deep(iframe) {
  max-width: 100%;
}

.post-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-top: -4px;
  opacity: 0;
  transition: opacity 0.2s;
  position: relative;
}

.post-item:hover .post-actions,
.post-item:focus-within .post-actions,
.post-actions.is-open {
  opacity: 1;
}

.post-action {
  border: 0;
  background: transparent;
  color: #72808d;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.post-action:hover {
  background: #eef3f7;
  color: #3f5165;
}

.post-action:disabled,
.post-feedback:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.post-action.is-active,
.post-feedback.is-active {
  color: #d5652a;
}

.post-action--icon {
  padding-left: 7px;
  padding-right: 7px;
}

.post-controls {
  position: relative;
}

.post-controls-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 138px;
  padding: 8px;
  border: 1px solid #dce4ec;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 14px 30px rgba(31, 45, 61, 0.14);
  z-index: 8;
}

.post-controls-menu button {
  width: 100%;
  border: 0;
  background: transparent;
  color: #495869;
  text-align: left;
  padding: 9px 10px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}

.post-controls-menu button:hover {
  background: #f3f7fa;
}

.post-controls-menu button.is-danger {
  color: #b54b4b;
}

.post-controls-menu button.is-danger:hover {
  background: #fff2f2;
}

.post-footer {
  display: inline-block;
  margin-top: 12px;
  margin-bottom: 2px;
}

.post-feedback {
  border: 0;
  background: transparent;
  color: #738191;
  padding: 0;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
}

.post-feedback:hover {
  color: #4c5c6d;
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

.suspended-notice {
  padding: 18px 20px;
  background: #fff3cd;
  border: 1px solid #ffe69c;
  border-radius: 8px;
  margin-bottom: 20px;
  color: #856404;
  line-height: 1.6;
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

.sidebar-section--warning {
  background: #fffaf0;
  border: 1px solid #fde7b2;
}

.sidebar-section--actions {
  position: relative;
  padding: 16px;
}

.discussion-primary-action {
  width: 100%;
  border: 0;
  border-radius: 8px;
  padding: 12px 16px;
  background: #e86f2d;
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
}

.discussion-primary-action:hover {
  filter: brightness(0.96);
}

.discussion-primary-action:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.discussion-secondary-row {
  display: flex;
  margin-top: 12px;
}

.discussion-follow-action,
.discussion-menu-toggle {
  border: 0;
  background: #edf2f7;
  color: #627284;
  cursor: pointer;
  height: 44px;
}

.discussion-follow-action {
  flex: 1;
  border-radius: 8px 0 0 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}

.discussion-follow-action.is-standalone {
  border-radius: 8px;
}

.discussion-follow-action.is-active {
  color: #405469;
}

.discussion-menu-toggle {
  width: 48px;
  border-left: 1px solid #dde5ee;
  border-radius: 0 8px 8px 0;
}

.discussion-follow-action:hover,
.discussion-menu-toggle:hover,
.discussion-menu-toggle.is-active {
  background: #e3ebf4;
}

.discussion-follow-action:disabled,
.discussion-menu-toggle:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.discussion-actions-menu {
  position: absolute;
  left: 16px;
  right: 16px;
  top: 72px;
  padding: 8px;
  border: 1px solid #dbe3ec;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 12px 28px rgba(31, 45, 61, 0.14);
  z-index: 5;
}

.discussion-actions-menu button {
  width: 100%;
  margin: 0;
  border: 0;
  background: transparent;
  color: #465567;
  padding: 9px 10px;
  border-radius: 6px;
  text-align: left;
  font-size: 13px;
  cursor: pointer;
}

.discussion-actions-menu button:hover {
  background: #f2f6fa;
}

.discussion-actions-menu button.is-danger {
  color: #b64545;
}

.discussion-actions-menu button.is-danger:hover {
  background: #fff1f1;
}

.discussion-action-copy {
  margin: 12px 0 0;
  color: #738090;
  font-size: 13px;
  line-height: 1.6;
}

.discussion-action-copy--warning {
  color: #8a6b19;
}

.subscription-copy {
  color: #66717c;
  line-height: 1.6;
  margin-bottom: 14px;
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

.sidebar-section--scrubber {
  padding: 18px 18px 14px;
}

.scrubber-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scrubber-link {
  border: 0;
  background: transparent;
  color: #6d7b88;
  padding: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  width: fit-content;
  cursor: pointer;
}

.scrubber-link:hover {
  color: #41505f;
}

.scrubber-scrollbar {
  margin: 8px 0 8px 3px;
  height: 300px;
  min-height: 50px;
  position: relative;
  cursor: pointer;
  user-select: none;
}

.scrubber-before,
.scrubber-after {
  position: absolute;
  left: 0;
  width: 100%;
  border-left: 1px solid #d8e0e8;
}

.scrubber-before {
  top: 0;
}

.scrubber-after {
  bottom: 0;
}

.scrubber-unread {
  position: absolute;
  left: 0;
  width: 100%;
  border-left: 1px solid #c1ccd8;
  background-image: linear-gradient(to right, rgba(230, 235, 241, 0.92), transparent 10px, transparent);
  display: flex;
  align-items: center;
  color: #7d8894;
  text-transform: uppercase;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  padding-left: 13px;
  pointer-events: none;
}

.scrubber-handle {
  position: absolute;
  left: 0;
  width: 100%;
  padding: 5px 0;
  cursor: move;
  z-index: 1;
}

.scrubber-bar {
  height: 100%;
  width: 5px;
  background: var(--forum-primary-color);
  border-radius: 4px;
  margin-left: -2px;
  transition: background 0.2s;
}

.scrubber-info {
  margin-top: -1.5em;
  position: absolute;
  top: 50%;
  left: 15px;
  width: calc(100% - 15px);
}

.scrubber-info strong {
  display: block;
  color: #35424f;
  font-size: 13px;
  line-height: 1.3;
}

.scrubber-description {
  display: block;
  color: #7b8794;
  font-size: 12px;
}

.scrubber-handle.is-dragging .scrubber-bar,
:global(body.scrubber-dragging) .scrubber-bar {
  background: #d46a2c;
}

:global(body.scrubber-dragging) {
  cursor: move;
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
    padding: 18px 0 20px;
  }

  .post-item::after {
    width: 100%;
  }

  .post-item.is-target .post-main {
    margin: -10px -12px 0;
    padding: 10px 12px 14px;
  }

  .post-container {
    grid-template-columns: 52px minmax(0, 1fr);
    gap: 10px;
  }

  .post-avatar {
    width: 40px;
    height: 40px;
  }

  .avatar-placeholder.post-avatar {
    font-size: 16px;
  }

  .post-header {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
    margin-bottom: 12px;
  }

  .post-actions {
    opacity: 1;
    margin-top: 0;
    flex-wrap: wrap;
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

  .scrubber-scrollbar {
    height: 42vh;
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
