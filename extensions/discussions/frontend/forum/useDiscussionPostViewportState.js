import { nextTick, onBeforeUnmount, onMounted, ref } from '@bias/core'

export function resolveVisiblePostMetrics({
  postRects = [],
  viewportTop = 96,
  viewportBottom = 0,
  anchorY = 120,
  maxPostNumber = 1,
  scrollBottom = 0,
  documentBottom = 0,
}) {
  if (!postRects.length) {
    return {
      trackedPostNumber: 1,
      progress: 1,
    }
  }

  let closestPostNumber = Number(postRects[0].number || 1)
  let closestDistance = Number.POSITIVE_INFINITY
  let indexFromViewport = null
  let lastVisiblePostNumber = closestPostNumber

  for (const postRect of postRects) {
    const rect = postRect.rect || {}
    if (rect.bottom < viewportTop) continue
    if (rect.top > viewportBottom) break

    const height = rect.height || 1
    const visibleTop = Math.max(0, viewportTop - rect.top)
    const visibleBottom = Math.min(height, viewportBottom - rect.top)
    const visiblePart = visibleBottom - visibleTop

    if (indexFromViewport === null) {
      indexFromViewport = Number(postRect.number || 1) + visibleTop / height
    }

    if (visiblePart > 0) {
      lastVisiblePostNumber = Number(postRect.number || lastVisiblePostNumber || 1)
    }

    const distance = Math.abs(rect.top - anchorY)
    if (distance < closestDistance) {
      closestDistance = distance
      closestPostNumber = Number(postRect.number || closestPostNumber || 1)
    }
  }

  const isAtPageBottom = documentBottom - scrollBottom <= 24
  const trackedPostNumber = isAtPageBottom ? lastVisiblePostNumber : closestPostNumber
  const clampedProgress = clampPostPosition(indexFromViewport ?? trackedPostNumber, maxPostNumber)

  return {
    trackedPostNumber,
    progress: isAtPageBottom ? maxPostNumber : clampedProgress,
  }
}

export function resolveAnchorScrollDelta({
  anchorTop = null,
  currentTop = null,
  threshold = 1,
}) {
  if (typeof anchorTop !== 'number' || typeof currentTop !== 'number') {
    return null
  }

  const delta = currentTop - anchorTop
  if (Math.abs(delta) <= threshold) {
    return null
  }

  return delta
}

export async function settleAnchorScrollPosition({
  anchorTop = null,
  getCurrentTop,
  scrollBy,
  scheduleFrame = callback => requestAnimationFrame(callback),
  maxFrames = 4,
  threshold = 1,
}) {
  if (typeof anchorTop !== 'number' || typeof getCurrentTop !== 'function' || typeof scrollBy !== 'function') {
    return false
  }

  for (let frame = 0; frame < maxFrames; frame += 1) {
    const delta = resolveAnchorScrollDelta({
      anchorTop,
      currentTop: getCurrentTop(),
      threshold,
    })

    if (delta === null) {
      return frame > 0
    }

    scrollBy(delta)

    if (frame < maxFrames - 1) {
      await waitForNextFrame(scheduleFrame)
    }
  }

  return true
}

export function useDiscussionPostViewportState({
  currentVisiblePostNumber,
  hasMore,
  hasPrevious,
  loadingMore,
  loadingPrevious,
  loadMorePosts,
  loadPreviousPosts,
  maxPostNumber,
  posts,
  scheduleNearUrlSync,
  scheduleReadStateSync,
  setCurrentVisiblePostNumber,
  setCurrentVisiblePostProgress,
  syncScrubberTrackMetrics,
}) {
  const previousTrigger = ref(null)
  const nextTrigger = ref(null)
  const settlingPreviousAnchor = ref(false)
  let scrollFrame = null

  onMounted(() => {
    window.addEventListener('scroll', handlePostScroll, { passive: true })
    window.addEventListener('resize', handlePostScroll, { passive: true })
    nextTick(() => {
      updateVisiblePostFromScroll()
    })
  })

  onBeforeUnmount(() => {
    window.removeEventListener('scroll', handlePostScroll)
    window.removeEventListener('resize', handlePostScroll)
    if (scrollFrame) {
      cancelAnimationFrame(scrollFrame)
    }
  })

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
    if (settlingPreviousAnchor.value) {
      return
    }

    if (hasPrevious.value && !loadingPrevious.value && previousTrigger.value) {
      const previousRect = previousTrigger.value.getBoundingClientRect()
      if (previousRect.top <= 220) {
        void loadPreviousPostsWithAnchor()
      }
    }

    if (hasMore.value && !loadingMore.value && nextTrigger.value) {
      const nextRect = nextTrigger.value.getBoundingClientRect()
      if (nextRect.top - window.innerHeight <= 280) {
        void loadMorePostsAndSync()
      }
    }
  }

  async function loadMorePostsAndSync() {
    await loadMorePosts()
    await nextTick()
    syncScrubberTrackMetrics()
    updateVisiblePostFromScroll()
    maybeAutoLoadPosts()
  }

  async function loadPreviousPostsWithAnchor() {
    const anchorNumber = posts.value[0]?.number
    const getAnchorTop = () => {
      if (!anchorNumber) return null
      return document.getElementById(`post-${anchorNumber}`)?.getBoundingClientRect().top ?? null
    }
    const anchorTop = getAnchorTop()
    await loadPreviousPosts()
    await nextTick()
    if (anchorNumber && anchorTop !== null) {
      settlingPreviousAnchor.value = true
      try {
        await settleAnchorScrollPosition({
          anchorTop,
          getCurrentTop: getAnchorTop,
          scrollBy: delta => {
            window.scrollBy({ top: delta })
          },
        })
      } finally {
        settlingPreviousAnchor.value = false
      }
    }
    syncScrubberTrackMetrics()
    updateVisiblePostFromScroll()
    maybeAutoLoadPosts()
  }

  function updateVisiblePostFromScroll() {
    if (!posts.value.length) return

    const viewportTop = 96
    const viewportBottom = window.innerHeight
    const postRects = posts.value
      .map(post => ({
        number: Number(post?.number || 1),
        rect: document.getElementById(`post-${post.number}`)?.getBoundingClientRect(),
      }))
      .filter(item => item.rect)

    const metrics = resolveVisiblePostMetrics({
      postRects,
      viewportTop,
      viewportBottom,
      anchorY: 120,
      maxPostNumber: maxPostNumber.value,
      scrollBottom: window.scrollY + window.innerHeight,
      documentBottom: document.documentElement.scrollHeight,
    })

    setCurrentVisiblePostProgress(metrics.progress)

    if (metrics.trackedPostNumber !== currentVisiblePostNumber.value) {
      setCurrentVisiblePostNumber(metrics.trackedPostNumber)
      scheduleNearUrlSync(metrics.trackedPostNumber)
      scheduleReadStateSync(metrics.trackedPostNumber)
    }
  }

  return {
    handlePostScroll,
    loadMorePostsAndSync,
    loadPreviousPostsWithAnchor,
    nextTrigger,
    previousTrigger,
    updateVisiblePostFromScroll,
  }
}

function clampPostPosition(value, maxPostNumber) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return 1
  return Math.min(Number(maxPostNumber || 1), Math.max(1, parsed))
}

function waitForNextFrame(scheduleFrame) {
  return new Promise(resolve => {
    scheduleFrame(() => resolve())
  })
}
