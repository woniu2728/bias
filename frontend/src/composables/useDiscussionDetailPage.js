import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import api from '@/api'
import {
  formatRelativeTime,
  normalizeDiscussion,
  normalizePost,
  unwrapList
} from '@/utils/forum'

export function useDiscussionDetailPage({
  authStore,
  composerStore,
  route,
  router
}) {
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
  const discussionSidebarRef = ref(null)
  const discussionMobileNavRef = ref(null)
  const highlightedPostNumber = ref(null)
  const currentVisiblePostNumber = ref(1)
  const currentVisiblePostProgress = ref(1)
  const showDiscussionMenu = ref(false)
  const activePostMenuId = ref(null)
  const scrubberTrackHeight = ref(300)
  const scrubberTrackMaxHeight = ref(null)
  const scrubberDragging = ref(false)
  const scrubberPreviewNumber = ref(null)

  let scrollFrame = null
  let nearUrlTimer = null
  let readStateTimer = null
  let lastReportedReadNumber = 0
  let scrubberResizeObserver = null
  let scrubberDragPointerOffset = 0

  const isSuspended = computed(() => Boolean(authStore.user?.is_suspended))
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
  const hasMobileDiscussionMenuActions = computed(() => Boolean(
    !discussion.value
      ? false
      : (!authStore.isAuthenticated)
          || Boolean(
            authStore.isAuthenticated
            && discussion.value?.can_reply
            && !discussion.value?.is_locked
            && !isSuspended.value
          )
          || (authStore.isAuthenticated && !isSuspended.value)
          || Boolean(
            authStore.isAuthenticated
            && discussion.value?.can_edit
            && !isSuspended.value
          )
          || Boolean(authStore.user?.is_staff)
  ))
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
  const scrubberHandlePercent = computed(() => {
    const total = Math.max(maxPostNumber.value, 1)
    if (total <= 1) return 100

    const trackHeight = Math.max(scrubberTrackHeight.value, 1)
    const minHandlePercent = (28 / trackHeight) * 100
    return Math.min(16, Math.max(minHandlePercent, 100 / total))
  })
  const scrubberBeforePercent = computed(() => {
    return getScrubberHandleTopPercent(scrubberDisplayNumber.value)
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
    window.addEventListener('bias:mobile-header-action', handleMobileHeaderAction)
    window.addEventListener('bias:reply-created', handleReplyCreated)
    window.addEventListener('bias:post-updated', handlePostUpdated)
    window.addEventListener('bias:discussion-updated', handleDiscussionUpdated)
    document.addEventListener('mousedown', handleDocumentMouseDown)
    await nextTick()
    syncScrubberTrackMetrics()
    attachScrubberObserver()
    updateVisiblePostFromScroll()
    syncMobileHeader()
  })

  onBeforeUnmount(() => {
    window.removeEventListener('scroll', handlePostScroll)
    window.removeEventListener('resize', handlePostScroll)
    window.removeEventListener('resize', syncScrubberTrackMetrics)
    window.removeEventListener('bias:mobile-header-action', handleMobileHeaderAction)
    window.removeEventListener('bias:reply-created', handleReplyCreated)
    window.removeEventListener('bias:post-updated', handlePostUpdated)
    window.removeEventListener('bias:discussion-updated', handleDiscussionUpdated)
    document.removeEventListener('mousedown', handleDocumentMouseDown)
    detachScrubberDragListeners()
    detachScrubberObserver()
    resetMobileHeader()
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
      resetMobileHeader()
      resetPostStream()
      loading.value = true
      await refreshDiscussion()
    }
  )

  watch(
    () => [
      currentVisiblePostProgress.value,
      maxPostNumber.value,
      discussion.value?.title,
      hasMobileDiscussionMenuActions.value
    ],
    () => {
      syncMobileHeader()
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
      authStore.isAuthenticated
      && unreadStartPostNumber.value
      && unreadCount.value > 0
      && Number(post?.number) === Number(unreadStartPostNumber.value)
    )
  }

  function handleDocumentMouseDown(event) {
    if (showDiscussionMenu.value && !(event.target instanceof Element && event.target.closest('.discussion-actions-scope'))) {
      showDiscussionMenu.value = false
    }

    if (activePostMenuId.value && !(event.target instanceof Element && event.target.closest('.post-controls'))) {
      activePostMenuId.value = null
    }
  }

  function handleMobileHeaderAction(event) {
    if (event.detail?.action !== 'discussion-menu') return

    showDiscussionMenu.value = !showDiscussionMenu.value

    if (!showDiscussionMenu.value) return

    nextTick(() => {
      getDiscussionMobileNavEl()?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }

  function syncMobileHeader() {
    if (typeof window === 'undefined' || !discussion.value) return

    window.dispatchEvent(new CustomEvent('bias:mobile-header-update', {
      detail: {
        route: 'discussion-detail',
        title: `${sanitizePostNumber(currentVisiblePostProgress.value)} / ${maxPostNumber.value}`,
        leftAction: 'back',
        rightAction: hasMobileDiscussionMenuActions.value ? 'discussion-menu' : 'none'
      }
    }))
  }

  function resetMobileHeader() {
    if (typeof window === 'undefined') return

    window.dispatchEvent(new CustomEvent('bias:mobile-header-reset', {
      detail: {
        route: 'discussion-detail'
      }
    }))
  }

  function updateVisiblePostFromScroll() {
    if (!posts.value.length) return

    const anchorY = 120
    const viewportTop = 96
    const viewportBottom = window.innerHeight
    let closestPostNumber = posts.value[0].number
    let closestDistance = Number.POSITIVE_INFINITY
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

  function getScrubberHandleTopPercent(value) {
    const handle = scrubberHandlePercent.value
    if (handle >= 100) return 0

    const centerPercent = getPostProgressPercent(clampPostPosition(value))
    return Math.max(0, Math.min(100 - handle, centerPercent - handle / 2))
  }

  function handleScrubberTrackClick(event) {
    if (scrubberDragging.value) return

    const track = getScrubberTrackEl()
    if (!track) return

    const rect = track.getBoundingClientRect()
    if (!rect.height) return

    const percent = Math.max(0, Math.min(1, (getPointerClientY(event) - rect.top) / rect.height))
    const targetNumber = getPostNumberFromTrackPercent(percent)
    jumpToPost(targetNumber)
  }

  function handleScrubberMouseDown(event) {
    const clientY = getPointerClientY(event)
    if (clientY === null) return

    event.preventDefault()
    const track = getScrubberTrackEl()
    const rect = track?.getBoundingClientRect()
    const handleTopPx = rect ? (scrubberBeforePercent.value / 100) * rect.height : 0
    scrubberDragging.value = true
    scrubberPreviewNumber.value = scrubberDisplayNumber.value
    scrubberDragPointerOffset = Math.max(0, clientY - (rect?.top || 0) - handleTopPx)
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

    const track = getScrubberTrackEl()
    const rect = track?.getBoundingClientRect()
    if (!rect?.height) return

    const handleHeightPx = (scrubberHandlePercent.value / 100) * rect.height
    const maxTopPx = Math.max(0, rect.height - handleHeightPx)
    const topPx = Math.max(0, Math.min(maxTopPx, clientY - rect.top - scrubberDragPointerOffset))
    const centerPercent = rect.height ? (topPx + handleHeightPx / 2) / rect.height : 0

    scrubberPreviewNumber.value = getPostNumberFromTrackPercent(centerPercent)
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
    const track = getScrubberTrackEl()
    if (!track || typeof ResizeObserver === 'undefined') return

    scrubberResizeObserver = new ResizeObserver(() => {
      syncScrubberTrackMetrics()
    })
    scrubberResizeObserver.observe(track)
  }

  function detachScrubberObserver() {
    scrubberResizeObserver?.disconnect()
    scrubberResizeObserver = null
  }

  function syncScrubberTrackMetrics() {
    const panelRect = getScrubberPanelEl()?.getBoundingClientRect()
    const trackRect = getScrubberTrackEl()?.getBoundingClientRect()
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

  function getPostNumberFromTrackPercent(percent) {
    const total = Math.max(maxPostNumber.value, 1)
    if (total <= 1) return 1

    const clampedPercent = Math.max(0, Math.min(1, Number(percent) || 0))
    if (clampedPercent >= 1) return total

    return Math.min(total, Math.floor(clampedPercent * total) + 1)
  }

  function getPointerClientY(event) {
    if (typeof event?.clientY === 'number') return event.clientY
    const touch = event?.touches?.[0] || event?.changedTouches?.[0]
    return typeof touch?.clientY === 'number' ? touch.clientY : null
  }

  function getScrubberPanelEl() {
    return discussionSidebarRef.value?.getScrubberPanelEl?.() || null
  }

  function getScrubberTrackEl() {
    return discussionSidebarRef.value?.getScrubberTrackEl?.() || null
  }

  function getDiscussionMobileNavEl() {
    return discussionMobileNavRef.value?.getRootEl?.() || null
  }

  function toggleDiscussionMenu() {
    showDiscussionMenu.value = !showDiscussionMenu.value
  }

  function togglePostMenu(postId) {
    activePostMenuId.value = activePostMenuId.value === postId ? null : postId
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
        window.dispatchEvent(new CustomEvent('bias:discussion-read-state-updated', {
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

    window.dispatchEvent(new CustomEvent('bias:discussion-read-state-updated', {
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

    upsertPost(detail.post)
  }

  async function handleDiscussionUpdated(event) {
    const detail = event.detail || {}
    if (!discussion.value || Number(detail.discussionId) !== Number(discussion.value.id)) return

    await refreshDiscussion()
  }

  function upsertPost(rawPost) {
    const updatedPost = normalizePost(rawPost)
    const index = posts.value.findIndex(post => post.id === updatedPost.id)
    if (index !== -1) {
      posts.value[index] = updatedPost
    }
  }

  return {
    activePostMenuId,
    discussion,
    discussionMobileNavRef,
    discussionSidebarRef,
    hasActiveComposer,
    hasMore,
    hasPrevious,
    handleScrubberMouseDown,
    handleScrubberTrackClick,
    highlightedPostNumber,
    jumpToPost,
    loadMorePosts,
    loading,
    loadingMore,
    loadingPrevious,
    loadPreviousPosts,
    maxPostNumber,
    nextTrigger,
    posts,
    previousTrigger,
    refreshDiscussion,
    scrollToPost,
    scrubberAfterPercent,
    scrubberBeforePercent,
    scrubberDescription,
    scrubberDragging,
    scrubberHandlePercent,
    scrubberPositionText,
    scrubberScrollbarStyle,
    showDiscussionMenu,
    showUnreadDivider,
    toggleDiscussionMenu,
    togglePostMenu,
    totalPosts,
    unreadCount,
    unreadHeightPercent,
    unreadTopPercent,
    upsertPost
  }
}
