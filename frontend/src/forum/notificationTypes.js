import api from '@/api'
import { buildDiscussionPath } from '@/utils/forum'

const notificationTypeDefinitions = []
const postPathCache = new Map()

function normalizeType(type) {
  return String(type || '').trim()
}

function normalizeDiscussionId(notification) {
  return Number(
    notification?.data?.discussion_id
    || (notification?.subject_type === 'discussion' ? notification?.subject_id : 0)
    || 0
  )
}

function normalizePostId(notification) {
  return Number(
    notification?.data?.post_id
    || (notification?.subject_type === 'post' ? notification?.subject_id : 0)
    || 0
  )
}

function normalizePostNumber(notification) {
  return Number(notification?.data?.post_number || 0)
}

async function resolveDiscussionOrPostPath(notification) {
  const discussionId = normalizeDiscussionId(notification)
  const postId = normalizePostId(notification)
  const postNumber = normalizePostNumber(notification)

  if (discussionId && postNumber) {
    return `/d/${discussionId}?near=${postNumber}`
  }

  if (postId) {
    if (postPathCache.has(postId)) {
      return postPathCache.get(postId)
    }

    try {
      const post = await api.get(`/posts/${postId}`)
      const resolvedDiscussionId = Number(post?.discussion_id || discussionId || 0)
      const resolvedPostNumber = Number(post?.number || 0)

      if (resolvedDiscussionId && resolvedPostNumber) {
        const resolvedPath = `/d/${resolvedDiscussionId}?near=${resolvedPostNumber}`
        postPathCache.set(postId, resolvedPath)
        return resolvedPath
      }

      if (resolvedDiscussionId) {
        const resolvedPath = buildDiscussionPath(resolvedDiscussionId)
        postPathCache.set(postId, resolvedPath)
        return resolvedPath
      }
    } catch (error) {
      console.error('解析通知跳转帖子失败:', error)
    }
  }

  if (discussionId) {
    return buildDiscussionPath(discussionId)
  }

  return '/notifications'
}

function getFallbackDefinition(type) {
  const normalizedType = normalizeType(type)
  return {
    type: normalizedType,
    label: normalizedType || '通知',
    icon: 'fas fa-bell',
    navigationScope: 'notifications',
    order: 999,
    isFallback: true,
  }
}

function describeNotificationActor(notification) {
  return notification?.from_user?.display_name || notification?.from_user?.username || '有人'
}

function describeDiscussionTitle(notification) {
  return notification?.data?.discussion_title || ''
}

function describeApprovalNote(notification) {
  return notification?.data?.approval_note ? `：${notification.data.approval_note}` : ''
}

function describeSuspendMessage(notification) {
  return notification?.data?.suspend_message ? `：${notification.data.suspend_message}` : ''
}

export function registerNotificationType(definition) {
  const normalizedType = normalizeType(definition?.type)
  if (!normalizedType) {
    return null
  }

  const existing = notificationTypeDefinitions.find(item => item.type === normalizedType)
  const normalizedDefinition = {
    ...existing,
    order: 100,
    icon: 'fas fa-bell',
    navigationScope: 'notifications',
    ...definition,
    type: normalizedType,
  }

  const existingIndex = notificationTypeDefinitions.findIndex(item => item.type === normalizedType)
  if (existingIndex >= 0) {
    notificationTypeDefinitions.splice(existingIndex, 1, normalizedDefinition)
    return normalizedDefinition
  }

  notificationTypeDefinitions.push(normalizedDefinition)
  return normalizedDefinition
}

export function syncNotificationTypes(definitions = []) {
  definitions.forEach((definition, index) => {
    const normalizedType = normalizeType(definition?.code || definition?.type)
    if (!normalizedType) {
      return
    }

    const existing = getNotificationTypeDefinition(normalizedType)
    registerNotificationType({
      ...existing,
      ...definition,
      type: normalizedType,
      navigationScope: definition?.navigation_scope || definition?.navigationScope || existing?.navigationScope,
      order: Number(definition?.order ?? existing?.order ?? ((index + 1) * 10)),
    })
  })
}

export function getNotificationTypeDefinition(type) {
  const normalizedType = normalizeType(type)
  return (
    notificationTypeDefinitions.find(item => item.type === normalizedType)
    || getFallbackDefinition(normalizedType)
  )
}

export function getRegisteredNotificationTypes() {
  return [...notificationTypeDefinitions].sort((left, right) => {
    return Number(left.order || 999) - Number(right.order || 999)
  })
}

export function getNotificationIcon(type) {
  return getNotificationTypeDefinition(type).icon || 'fas fa-bell'
}

export function getNotificationText(notification, fallbackMessage = '') {
  const definition = getNotificationTypeDefinition(notification?.type)

  if (typeof definition.getText === 'function') {
    const text = definition.getText(notification)
    if (text) {
      return text
    }
  }

  return fallbackMessage || notification?.message || definition.label || '你有新通知'
}

export async function resolveNotificationPath(notification) {
  const definition = getNotificationTypeDefinition(notification?.type)

  if (typeof definition.getPath === 'function') {
    const path = await definition.getPath(notification)
    if (path) {
      return path
    }
  }

  switch (definition.navigationScope) {
    case 'post':
    case 'discussion':
      return resolveDiscussionOrPostPath(notification)
    case 'profile':
      return '/profile'
    default:
      return '/notifications'
  }
}

syncNotificationTypes([
  {
    code: 'discussionReply',
    label: '讨论新回复',
    icon: 'fas fa-reply',
    navigation_scope: 'post',
    order: 10,
    getText(notification) {
      const fromUser = describeNotificationActor(notification)
      const discussionTitle = describeDiscussionTitle(notification)
      return `${fromUser} 回复了你的讨论 "${discussionTitle}"`
    },
  },
  {
    code: 'postLiked',
    label: '回复被点赞',
    icon: 'fas fa-thumbs-up',
    navigation_scope: 'post',
    order: 20,
    getText(notification) {
      const fromUser = describeNotificationActor(notification)
      return `${fromUser} 点赞了你的回复`
    },
  },
  {
    code: 'userMentioned',
    label: '@提及通知',
    icon: 'fas fa-at',
    navigation_scope: 'post',
    order: 30,
    getText(notification) {
      const fromUser = describeNotificationActor(notification)
      return `${fromUser} 在回复中提到了你`
    },
  },
  {
    code: 'postReply',
    label: '回复被回应',
    icon: 'fas fa-comment-dots',
    navigation_scope: 'post',
    order: 40,
    getText(notification) {
      const fromUser = describeNotificationActor(notification)
      return `${fromUser} 回复了你的帖子`
    },
  },
  {
    code: 'discussionApproved',
    label: '讨论审核通过',
    icon: 'fas fa-circle-check',
    navigation_scope: 'discussion',
    order: 50,
    getText(notification) {
      const fromUser = describeNotificationActor(notification)
      const discussionTitle = describeDiscussionTitle(notification)
      return `${fromUser} 通过了你的讨论 "${discussionTitle}"`
    },
  },
  {
    code: 'discussionRejected',
    label: '讨论审核拒绝',
    icon: 'fas fa-circle-xmark',
    navigation_scope: 'discussion',
    order: 60,
    getText(notification) {
      const fromUser = describeNotificationActor(notification)
      const discussionTitle = describeDiscussionTitle(notification)
      return `${fromUser} 拒绝了你的讨论 "${discussionTitle}"${describeApprovalNote(notification)}`
    },
  },
  {
    code: 'postApproved',
    label: '回复审核通过',
    icon: 'fas fa-check',
    navigation_scope: 'post',
    order: 70,
    getText(notification) {
      const fromUser = describeNotificationActor(notification)
      const discussionTitle = describeDiscussionTitle(notification)
      return `${fromUser} 通过了你在 "${discussionTitle}" 中的回复`
    },
  },
  {
    code: 'postRejected',
    label: '回复审核拒绝',
    icon: 'fas fa-xmark',
    navigation_scope: 'post',
    order: 80,
    getText(notification) {
      const fromUser = describeNotificationActor(notification)
      const discussionTitle = describeDiscussionTitle(notification)
      return `${fromUser} 拒绝了你在 "${discussionTitle}" 中的回复${describeApprovalNote(notification)}`
    },
  },
  {
    code: 'userSuspended',
    label: '账号封禁通知',
    icon: 'fas fa-user-lock',
    navigation_scope: 'profile',
    order: 90,
    getText(notification) {
      const fromUser = describeNotificationActor(notification)
      return `${fromUser} 已封禁你的账号${describeSuspendMessage(notification)}`
    },
  },
  {
    code: 'userUnsuspended',
    label: '账号解除封禁',
    icon: 'fas fa-user-check',
    navigation_scope: 'profile',
    order: 100,
    getText(notification) {
      const fromUser = describeNotificationActor(notification)
      return `${fromUser} 已解除你的账号封禁`
    },
  },
  {
    code: 'discussionCreated',
    label: '发起讨论',
    icon: 'fas fa-pen',
    navigation_scope: 'discussion',
    order: 110,
    getText(notification) {
      const fromUser = describeNotificationActor(notification)
      const discussionTitle = describeDiscussionTitle(notification)
      return `${fromUser} 发起了新讨论 "${discussionTitle}"`
    },
  },
  {
    code: 'postCreated',
    label: '发表回复',
    icon: 'fas fa-message',
    navigation_scope: 'post',
    order: 120,
    getText(notification) {
      const fromUser = describeNotificationActor(notification)
      return `${fromUser} 发表了新回复`
    },
  },
])
