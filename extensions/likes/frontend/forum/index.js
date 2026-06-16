import {
  ref,
  api
} from '@bias/core'
import { extendForum,
  getUiCopy
} from '@bias/forum'
import {
  buildLikeSummary,
  canLikePost,
  getPostLikeCount,
  isPostLiked,
} from './likeRuntime.js'

export const extend = [
  extendForum(registerLikesForum),
]

const pendingPostIds = ref([])

function registerLikesForum(forum) {
  forum.postAction({
    key: 'toggle-post-like-primary',
    action: 'toggle-post-like',
    moduleId: 'likes',
    order: 10,
    surfaces: ['discussion-post-primary'],
    isVisible: ({ authStore, post }) => Boolean(authStore?.isAuthenticated && canLikePost(post)),
    resolve: ({ post }) => ({
      key: 'toggle-post-like-primary',
      action: 'toggle-post-like',
      label: getUiCopy({ surface: 'discussion-post-like-action' })?.text || '赞',
      icon: 'fas fa-thumbs-up',
      active: isPostLiked(post),
      disabled: isPending(post),
      order: 10,
    }),
  })

  forum.postAction({
    key: 'post-like-feedback',
    action: 'toggle-post-like',
    moduleId: 'likes',
    order: 10,
    surfaces: ['discussion-post-feedback'],
    isVisible: ({ post }) => getPostLikeCount(post) > 0,
    resolve: ({ authStore, isSuspended, post }) => {
      const canInteract = Boolean(authStore?.isAuthenticated && !isSuspended && canLikePost(post))
      return {
        key: 'post-like-feedback',
        action: 'toggle-post-like',
        label: formatLikeSummary(post),
        icon: 'fas fa-thumbs-up',
        active: isPostLiked(post),
        disabled: isPending(post),
        readonly: !canInteract,
        order: 10,
      }
    },
  })

  forum.postActionHandler({
    key: 'toggle-post-like',
    moduleId: 'likes',
    order: 10,
    handle: handleTogglePostLike,
  })

  forum.notificationRenderer({
    type: 'postLiked',
    key: 'postLiked',
    moduleId: 'likes',
    label: '回复被点赞',
    icon: 'fas fa-thumbs-up',
    navigationScope: 'post',
    groupLabel: '互动反馈',
    order: 20,
    getText(notification) {
      const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
      return `${fromUser} 点赞了你的回复`
    },
  })

  registerLikesUiCopy(forum)
}

async function handleTogglePostLike({
  authStore,
  isSuspended,
  patchPost,
  post,
  router,
  showActionError,
  showSuspensionAlert,
}) {
  if (!post) return

  if (!authStore?.isAuthenticated) {
    router?.push?.('/login')
    return
  }
  if (isSuspended) {
    await showSuspensionAlert?.()
    return
  }
  if (!canLikePost(post) || isPending(post)) {
    return
  }

  const previousLiked = isPostLiked(post)
  const previousLikeCount = getPostLikeCount(post)
  setPending(post, true)

  try {
    if (previousLiked) {
      patchPost?.(post.id, {
        like_count: Math.max(0, previousLikeCount - 1),
        is_liked: false,
      })
      await api.delete(`/posts/${post.id}/like`)
      return
    }

    patchPost?.(post.id, {
      like_count: previousLikeCount + 1,
      is_liked: true,
    })
    await api.post(`/posts/${post.id}/like`)
  } catch (error) {
    patchPost?.(post.id, {
      like_count: previousLikeCount,
      is_liked: previousLiked,
    })
    console.error('点赞失败:', error)
    await showActionError?.('点赞', error)
  } finally {
    setPending(post, false)
  }
}

function isPending(post) {
  return pendingPostIds.value.includes(post?.id)
}

function setPending(post, value) {
  if (!post?.id) return
  if (value) {
    if (!isPending(post)) {
      pendingPostIds.value.push(post.id)
    }
    return
  }
  pendingPostIds.value = pendingPostIds.value.filter(id => id !== post.id)
}

function formatLikeSummary(post) {
  const count = getPostLikeCount(post)
  return getUiCopy({
    surface: 'discussion-detail-like-summary',
    count,
    isLiked: isPostLiked(post),
  })?.text || buildLikeSummary(post)
}

function registerLikesUiCopy(forum) {
  forum.uiCopy({
    key: 'discussion-detail-like-summary',
    moduleId: 'likes',
    order: 479,
    surfaces: ['discussion-detail-like-summary'],
    resolve: ({ count, isLiked }) => {
      if (Number(count || 0) <= 0) {
        return { text: '' }
      }

      if (isLiked) {
        return {
          text: Number(count) === 1 ? '你赞了这条回复' : `你和其他 ${Number(count) - 1} 人赞了这条回复`,
        }
      }

      return {
        text: `${Number(count)} 人赞了这条回复`,
      }
    },
  })

  forum.uiCopy({
    key: 'discussion-post-like-action',
    moduleId: 'likes',
    order: 479,
    surfaces: ['discussion-post-like-action'],
    resolve: () => ({ text: '赞' }),
  })
}
