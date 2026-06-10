import { computed, nextTick, onBeforeUnmount, onMounted, ref } from '@bias/core'

function formatScrubberRelativeTime(dateString) {
  if (!dateString) return '暂无'

  const date = new Date(dateString)
  const diff = Date.now() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 30) return `${days}天前`

  return date.toLocaleDateString('zh-CN')
}

export function useDiscussionSidebarScrubber({
  currentVisiblePostNumber,
  currentVisiblePostProgress,
  jumpToPost,
  maxPostNumber,
  posts,
  unreadCount,
  unreadStartPostNumber,
}) {
  const discussionSidebarRef = ref(null)
  const scrubberTrackHeight = ref(300)
  const scrubberTrackMaxHeight = ref(null)
  const scrubberDragging = ref(false)
  const scrubberPreviewNumber = ref(null)

  let scrubberResizeObserver = null
  let scrubberDragPointerOffset = 0

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

    return formatScrubberRelativeTime(createdAt)
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

  onMounted(() => {
    if (typeof window !== 'undefined') {
      window.addEventListener('resize', syncScrubberTrackMetrics, { passive: true })
    }
    nextTick(() => {
      syncScrubberTrackMetrics()
      attachScrubberObserver()
    })
  })

  onBeforeUnmount(() => {
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', syncScrubberTrackMetrics)
    }
    detachScrubberDragListeners()
    detachScrubberObserver()
  })

  function resetScrubberPreview() {
    scrubberPreviewNumber.value = null
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
    const targetNumber = sanitizePostNumber(scrubberPreviewNumber.value ?? currentVisiblePostNumber.value)
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

    if (panelRect && trackRect && typeof window !== 'undefined' && window.innerWidth > 768) {
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

  function clampPostPosition(value) {
    const parsed = Number(value)
    if (!Number.isFinite(parsed)) return 1
    return Math.min(maxPostNumber.value, Math.max(1, parsed))
  }

  function sanitizePostNumber(value) {
    return Math.floor(clampPostPosition(value))
  }

  return {
    discussionSidebarRef,
    handleScrubberMouseDown,
    handleScrubberTrackClick,
    resetScrubberPreview,
    scrubberAfterPercent,
    scrubberBeforePercent,
    scrubberDescription,
    scrubberDragging,
    scrubberHandlePercent,
    scrubberPositionText,
    scrubberScrollbarStyle,
    syncScrubberTrackMetrics,
    unreadHeightPercent,
    unreadTopPercent,
  }
}
