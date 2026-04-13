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
                  <span v-if="post.approval_status === 'pending'" class="post-status">待审核</span>
                  <span v-if="post.edited_at" class="post-edited">(已编辑)</span>
                </div>

                <div class="post-body" v-html="post.content_html"></div>

                <div class="post-footer">
                  <button
                    @click="toggleLike(post)"
                    class="post-action"
                    :class="{ 'is-liked': post.is_liked }"
                    :disabled="isSuspended"
                  >
                    ❤️ {{ post.like_count || 0 }}
                  </button>
                  <button
                    @click="replyToPost(post)"
                    class="post-action"
                    v-if="authStore.isAuthenticated && !discussion.is_locked && !isSuspended"
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
                  <button
                    @click="openReportModal(post)"
                    class="post-action warning"
                    v-if="canReportPost(post)"
                  >
                    🚩 举报
                  </button>
                </div>
              </div>
            </div>
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
          <div v-else-if="authStore.isAuthenticated && !discussion.is_locked" class="reply-placeholder">
            <button @click="openComposer" class="primary">
              {{ hasActiveComposer ? '继续编辑回复' : '发表回复' }}
            </button>
            <span v-if="hasActiveComposer">已有未发布内容</span>
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
          <div v-if="authStore.isAuthenticated && !isSuspended" class="sidebar-section">
            <h3>关注讨论</h3>
            <p class="subscription-copy">
              {{ discussion.is_subscribed ? '你会收到这条讨论的新回复通知。' : '关注后，这条讨论的新回复会进入你的通知列表。' }}
            </p>
            <button @click="toggleSubscription" class="secondary full-width" :disabled="togglingSubscription">
              {{ togglingSubscription ? '提交中...' : (discussion.is_subscribed ? '取消关注' : '关注讨论') }}
            </button>
          </div>
          <div v-else-if="authStore.isAuthenticated && isSuspended" class="sidebar-section sidebar-section--warning">
            <h3>账号状态</h3>
            <p class="subscription-copy">{{ suspensionNotice }}</p>
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

          <div class="sidebar-section sidebar-section--scrubber">
            <div class="scrubber-panel">
              <button type="button" class="scrubber-link" @click="jumpToPost(1)">
                <i class="fas fa-angle-double-up"></i>
                原帖
              </button>

              <div ref="scrubberTrack" class="scrubber-scrollbar" @click="handleScrubberTrackClick">
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
                  @click.stop
                >
                  <div class="scrubber-bar"></div>
                  <div class="scrubber-info">
                    <strong>{{ scrubberPositionText }}</strong>
                    <span class="scrubber-description">{{ currentVisiblePostDateLabel }}</span>
                    <span class="scrubber-description">{{ loadedRangeText }}</span>
                  </div>
                </div>
                <div class="scrubber-after" :style="{ height: `${scrubberAfterPercent}%` }"></div>
              </div>

              <div class="scrubber-links">
                <button
                  v-if="unreadStartPostNumber"
                  type="button"
                  class="scrubber-link scrubber-link--muted"
                  @click="jumpToPost(unreadStartPostNumber)"
                >
                  <i class="fas fa-angle-down"></i>
                  未读
                </button>
                <div v-else class="scrubber-link scrubber-link--muted is-disabled">
                  <i class="fas fa-angle-down"></i>
                  已读
                </div>
                <button type="button" class="scrubber-link" @click="jumpToPost(maxPostNumber)">
                  <i class="fas fa-angle-double-down"></i>
                  现在
                </button>
              </div>

              <div class="scrubber-jump-inline">
                <span>#</span>
                <input
                  id="discussion-post-jump"
                  v-model.number="jumpPostNumber"
                  type="number"
                  min="1"
                  :max="maxPostNumber"
                  class="scrubber-number"
                  @keydown.enter.prevent="jumpToPost(jumpPostNumber)"
                  @blur="normalizeJumpPostNumber"
                />
                <button type="button" class="secondary" @click="jumpToPost(jumpPostNumber)">跳转</button>
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

    <div v-if="showReportModal" class="report-modal" @click.self="closeReportModal">
      <div class="report-dialog">
        <div class="report-header">
          <h3>举报帖子</h3>
          <button @click="closeReportModal" type="button" class="report-close">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="report-body">
          <div class="form-group">
            <label>举报原因</label>
            <select v-model="reportForm.reason" class="report-select">
              <option value="垃圾广告">垃圾广告</option>
              <option value="骚扰攻击">骚扰攻击</option>
              <option value="违规内容">违规内容</option>
              <option value="剧透/灌水">剧透/灌水</option>
              <option value="其他">其他</option>
            </select>
          </div>

          <div class="form-group">
            <label>补充说明</label>
            <textarea
              v-model="reportForm.message"
              rows="4"
              class="report-textarea"
              placeholder="告诉管理员这条帖子为什么需要处理"
            ></textarea>
          </div>
        </div>

        <div class="report-footer">
          <button @click="closeReportModal" type="button" class="composer-secondary">取消</button>
          <button @click="submitReport" type="button" class="composer-submit" :disabled="reportSubmitting">
            {{ reportSubmitting ? '提交中...' : '提交举报' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
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
const composerStore = useComposerStore()

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
const scrubberTrack = ref(null)

const togglingSubscription = ref(false)
const highlightedPostNumber = ref(null)
const jumpPostNumber = ref(1)
const currentVisiblePostNumber = ref(1)
const visiblePostCount = ref(1)
const showReportModal = ref(false)
const reportSubmitting = ref(false)
const reportingPost = ref(null)
const reportForm = ref({
  reason: '垃圾广告',
  message: ''
})
let scrollFrame = null
let nearUrlTimer = null
let readStateTimer = null
let lastReportedReadNumber = 0

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
const loadedRangeText = computed(() => {
  if (!posts.value.length) return '暂无'
  return `#${posts.value[0].number} - #${posts.value[posts.value.length - 1].number}`
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
const currentVisiblePost = computed(() => {
  return posts.value.find(post => post.number === currentVisiblePostNumber.value) || posts.value[0] || null
})
const currentVisiblePostDateLabel = computed(() => {
  const createdAt = currentVisiblePost.value?.created_at
  if (!createdAt) return '当前阅读位置'

  const date = new Date(createdAt)
  if (Number.isNaN(date.getTime())) return '当前阅读位置'

  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long'
  })
})
const scrubberPositionText = computed(() => {
  return `第 ${currentVisiblePostNumber.value} / ${maxPostNumber.value} 楼`
})
const scrubberHandlePercent = computed(() => {
  const total = Math.max(maxPostNumber.value, 1)
  const visible = Math.min(total, Math.max(visiblePostCount.value, 1))
  return Math.min(100, Math.max((visible / total) * 100, 12))
})
const scrubberBeforePercent = computed(() => {
  const total = Math.max(maxPostNumber.value, 1)
  const handle = scrubberHandlePercent.value
  const visible = Math.min(total, Math.max(visiblePostCount.value, 1))
  if (total <= visible) return 0

  const progress = (Math.min(total, Math.max(1, currentVisiblePostNumber.value)) - 1) / (total - visible)
  return Math.max(0, Math.min(100 - handle, progress * (100 - handle)))
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
  window.addEventListener('pyflarum:reply-created', handleReplyCreated)
  window.addEventListener('pyflarum:post-updated', handlePostUpdated)
  await nextTick()
  updateVisiblePostFromScroll()
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', handlePostScroll)
  window.removeEventListener('resize', handlePostScroll)
  window.removeEventListener('pyflarum:reply-created', handleReplyCreated)
  window.removeEventListener('pyflarum:post-updated', handlePostUpdated)
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
  syncJumpNumber()
  nextTick(() => {
    updateVisiblePostFromScroll()
    maybeAutoLoadPosts()
  })
}

function appendPosts(data) {
  const items = unwrapList(data).map(normalizePost)
  posts.value.push(...items)
  lastLoadedPage.value = data.page || lastLoadedPage.value + 1
  totalPosts.value = data.total || totalPosts.value
  syncJumpNumber()
  nextTick(() => {
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
  syncJumpNumber()
  nextTick(() => {
    if (anchorNumber && anchorTop !== null) {
      const newTop = document.getElementById(`post-${anchorNumber}`)?.getBoundingClientRect().top
      if (typeof newTop === 'number') {
        window.scrollBy({ top: newTop - anchorTop })
      }
    }
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
  jumpPostNumber.value = normalizePostNumber(route.query.near) || 1
  currentVisiblePostNumber.value = jumpPostNumber.value
}

function syncJumpNumber() {
  if (targetNearPost.value) {
    jumpPostNumber.value = normalizePostNumber(targetNearPost.value)
  } else if (posts.value.length) {
    jumpPostNumber.value = normalizePostNumber(posts.value[posts.value.length - 1].number)
  }
}

function handlePostScroll() {
  if (scrollFrame) return

  scrollFrame = requestAnimationFrame(() => {
    scrollFrame = null
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

function updateVisiblePostFromScroll() {
  if (!posts.value.length) return

  const anchorY = 120
  let closestPostNumber = posts.value[0].number
  let closestDistance = Number.POSITIVE_INFINITY
  let visibleCount = 0

  for (const post of posts.value) {
    const element = document.getElementById(`post-${post.number}`)
    if (!element) continue

    const rect = element.getBoundingClientRect()
    if (rect.bottom < 0 || rect.top > window.innerHeight) continue
    visibleCount += 1

    const distance = Math.abs(rect.top - anchorY)
    if (distance < closestDistance) {
      closestDistance = distance
      closestPostNumber = post.number
    }
  }

  visiblePostCount.value = Math.max(1, visibleCount)

  if (closestPostNumber !== currentVisiblePostNumber.value) {
    currentVisiblePostNumber.value = closestPostNumber
    jumpPostNumber.value = closestPostNumber
    scheduleNearUrlSync(closestPostNumber)
    scheduleReadStateSync(closestPostNumber)
  }
}

function normalizeJumpPostNumber() {
  jumpPostNumber.value = normalizePostNumber(jumpPostNumber.value)
}

function normalizePostNumber(value) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return 1
  return Math.min(maxPostNumber.value, Math.max(1, Math.round(parsed)))
}

function getPostProgressPercent(value) {
  const total = Math.max(maxPostNumber.value, 1)
  const number = Math.min(total, Math.max(1, Number(value) || 1))
  if (total <= 1) return 0
  return ((number - 1) / (total - 1)) * 100
}

function handleScrubberTrackClick(event) {
  const track = scrubberTrack.value
  if (!track) return

  const rect = track.getBoundingClientRect()
  if (!rect.height) return

  const percent = Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))
  const targetNumber = Math.round(1 + percent * Math.max(maxPostNumber.value - 1, 0))
  jumpToPost(targetNumber)
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
  if (isSuspended.value) {
    alert(suspensionNotice.value)
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
    alert('点赞失败: ' + (error.response?.data?.error || error.message || '未知错误'))
  }
}

function replyToPost(post) {
  if (isSuspended.value) {
    alert(suspensionNotice.value)
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
    alert(suspensionNotice.value)
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
    alert(suspensionNotice.value)
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

async function handleReplyCreated(event) {
  const detail = event.detail || {}
  if (!discussion.value || Number(detail.discussionId) !== Number(discussion.value.id)) return
  if (!detail.post) return

  const newPost = normalizePost(detail.post)
  if (posts.value.some(post => post.id === newPost.id)) return

  posts.value.push(newPost)
  discussion.value.comment_count = (discussion.value.comment_count || 0) + 1
  discussion.value.last_post_number = Math.max(discussion.value.last_post_number || 0, newPost.number || 0)
  discussion.value.last_posted_at = newPost.created_at || discussion.value.last_posted_at
  totalPosts.value = Math.max(totalPosts.value + 1, posts.value.length)
  lastLoadedPage.value = Math.max(lastLoadedPage.value, Math.ceil(totalPosts.value / pageLimit))
  if (authStore.user?.preferences?.follow_after_reply) {
    discussion.value.is_subscribed = true
  }

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
  if (isSuspended.value) return false
  return authStore.user?.id === post.user.id || authStore.user?.is_staff
}

function canDeletePost(post) {
  if (isSuspended.value) return false
  return authStore.user?.id === post.user.id || authStore.user?.is_staff
}

function canReportPost(post) {
  if (!authStore.isAuthenticated) return false
  if (isSuspended.value) return false
  if (!post?.user?.id) return false
  if (post.user.id === authStore.user?.id) return false
  return true
}

function openReportModal(post) {
  if (isSuspended.value) {
    alert(suspensionNotice.value)
    return
  }
  reportingPost.value = post
  reportForm.value = {
    reason: '垃圾广告',
    message: ''
  }
  showReportModal.value = true
}

function closeReportModal() {
  showReportModal.value = false
  reportSubmitting.value = false
  reportingPost.value = null
  reportForm.value = {
    reason: '垃圾广告',
    message: ''
  }
}

async function submitReport() {
  if (!reportingPost.value) return

  reportSubmitting.value = true
  try {
    await api.post(`/posts/${reportingPost.value.id}/report`, reportForm.value)
    closeReportModal()
    alert('举报已提交，管理员会尽快处理。')
  } catch (error) {
    console.error('举报失败:', error)
    alert('举报失败: ' + (error.response?.data?.error || error.message || '未知错误'))
  } finally {
    reportSubmitting.value = false
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
  if (isSuspended.value) {
    alert(suspensionNotice.value)
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
    alert('操作失败: ' + (error.response?.data?.error || error.message || '未知错误'))
  } finally {
    togglingSubscription.value = false
  }
}

function formatDate(dateString) {
  return formatRelativeTime(dateString)
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

.post-status {
  color: #856404;
  background: #fff3cd;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 600;
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

.post-action:disabled {
  cursor: not-allowed;
  opacity: 0.55;
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

.post-action.warning:hover {
  border-color: #e67e22;
  color: #e67e22;
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

.sidebar-section--scrubber {
  padding: 18px 18px 16px;
}

.scrubber-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.scrubber-link,
.scrubber-link--muted {
  border: 0;
  background: transparent;
  color: #6d7b88;
  padding: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
}

.scrubber-link:hover {
  color: #41505f;
}

.scrubber-link--muted {
  color: #8b98a6;
}

.scrubber-link.is-disabled {
  cursor: default;
}

.scrubber-scrollbar {
  margin: 6px 0 2px 3px;
  height: 320px;
  min-height: 120px;
  position: relative;
  cursor: pointer;
}

.scrubber-before,
.scrubber-after {
  position: absolute;
  left: 0;
  width: 100%;
  border-left: 1px solid #d6dee7;
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
  border-left: 1px solid #b8c4d1;
  background-image: linear-gradient(to right, rgba(222, 228, 236, 0.9), transparent 12px, transparent);
  display: flex;
  align-items: center;
  color: #7d8894;
  text-transform: uppercase;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  padding-left: 13px;
}

.scrubber-handle {
  position: absolute;
  left: 0;
  width: 100%;
  padding: 5px 0;
  cursor: pointer;
  z-index: 1;
}

.scrubber-bar {
  height: 100%;
  width: 5px;
  background: var(--forum-primary-color);
  border-radius: 999px;
  margin-left: -2px;
  transition: background 0.2s;
}

.scrubber-info {
  margin-top: -1.6em;
  position: absolute;
  top: 50%;
  left: 16px;
  width: calc(100% - 16px);
}

.scrubber-info strong {
  display: block;
  color: #2f3b47;
  font-size: 12px;
}

.scrubber-description {
  display: block;
  color: #7b8794;
  font-size: 12px;
}

.scrubber-links {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-top: -2px;
}

.scrubber-jump-inline {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 4px;
  border-top: 1px solid #eef2f6;
}

.scrubber-jump-inline span {
  color: #66717c;
  font-size: 13px;
  font-weight: 600;
}

.scrubber-number {
  width: 80px;
  padding: 7px 10px;
  border: 1px solid #d7dee6;
  border-radius: 6px;
  color: #2f3b47;
  font-size: 13px;
}

.scrubber-number:focus {
  outline: none;
  border-color: #4d698e;
  box-shadow: 0 0 0 3px rgba(77, 105, 142, 0.12);
}

.scrubber-jump-inline button {
  margin-bottom: 0;
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

.report-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
}

.report-dialog {
  width: min(520px, calc(100vw - 32px));
  background: white;
  border-radius: 8px;
  overflow: hidden;
}

.report-header,
.report-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px;
}

.report-header {
  border-bottom: 1px solid #e3e8ed;
}

.report-footer {
  justify-content: flex-end;
  border-top: 1px solid #e3e8ed;
}

.report-header h3 {
  margin: 0;
}

.report-close {
  border: 0;
  background: transparent;
  color: #99a1ab;
  font-size: 18px;
  cursor: pointer;
}

.report-body {
  padding: 20px;
}

.report-select,
.report-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d7dee6;
  border-radius: 4px;
  font-size: 14px;
  font-family: inherit;
}

.report-textarea {
  resize: vertical;
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

  .scrubber-scrollbar {
    height: 42vh;
  }

  .scrubber-links,
  .scrubber-jump-inline {
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
