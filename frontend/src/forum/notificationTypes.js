import api from '@/api'
import { useResourceStore } from '@/stores/resource'
import { buildDiscussionPath } from '@/utils/forum'
import { getNotificationRenderers, registerNotificationRenderer } from '@/forum/frontendRegistry'

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
    key: normalizedType,
    label: normalizedType || '通知',
    icon: 'fas fa-bell',
    navigationScope: 'notifications',
    order: 999,
    isFallback: true,
  }
}

function getResolvedNotificationDefinitions() {
  return getNotificationRenderers()
    .map(item => ({
      ...item,
      type: normalizeType(item.type || item.key),
      key: item.key || item.type,
    }))
    .filter(item => item.type)
}

export function getResolvedNotificationTypes() {
  return getResolvedNotificationDefinitions().sort((left, right) => {
    return Number(left.order || 999) - Number(right.order || 999)
  })
}

export function registerNotificationType(definition) {
  const normalizedType = normalizeType(definition?.type || definition?.code)
  if (!normalizedType) {
    return null
  }

  return registerNotificationRenderer({
    ...definition,
    key: definition?.key || normalizedType,
    type: normalizedType,
    navigationScope: definition?.navigation_scope || definition?.navigationScope,
  })
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
    getResolvedNotificationDefinitions().find(item => item.type === normalizedType)
    || getFallbackDefinition(normalizedType)
  )
}

export function getRegisteredNotificationTypes() {
  return getResolvedNotificationTypes()
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

export function getNotificationPresentation(notification, fallbackMessage = '') {
  const definition = getNotificationTypeDefinition(notification?.type)
  const messageText = getNotificationText(notification, fallbackMessage)
  const resourceStore = useResourceStore()
  const discussionId = normalizeDiscussionId(notification)
  const discussion = discussionId ? resourceStore.get('discussions', discussionId) : null
  const discussionTitle = discussion?.title || notification?.data?.discussion_title || ''
  const metaText = typeof definition.getMeta === 'function'
    ? definition.getMeta(notification)
    : (discussionTitle || definition.groupLabel || definition.label || '')
  const browserTitle = typeof definition.getBrowserTitle === 'function'
    ? definition.getBrowserTitle(notification)
    : (definition.label || '新通知')
  const browserBody = typeof definition.getBrowserBody === 'function'
    ? definition.getBrowserBody(notification)
    : messageText

  return {
    browserBody,
    browserTitle,
    definition,
    discussionTitle,
    iconClass: getNotificationIcon(notification?.type),
    label: definition.label || '通知',
    messageText,
    metaText,
    type: definition.type || normalizeType(notification?.type),
  }
}

export function resolveNotificationGroup(notification, fallbackTitle = '论坛') {
  const definition = getNotificationTypeDefinition(notification?.type)
  const resourceStore = useResourceStore()

  if (typeof definition.getGroup === 'function') {
    const resolvedGroup = definition.getGroup(notification, fallbackTitle)
    if (resolvedGroup?.key) {
      return {
        discussionId: Number(resolvedGroup.discussionId || 0),
        key: resolvedGroup.key,
        title: resolvedGroup.title || definition.label || fallbackTitle,
      }
    }
  }

  const discussionId = normalizeDiscussionId(notification)
  if (discussionId) {
    const discussion = resourceStore.get('discussions', discussionId)
    return {
      discussionId,
      key: `discussion-${discussionId}`,
      title: discussion?.title || notification?.data?.discussion_title || definition.label || fallbackTitle,
    }
  }

  if (definition.navigationScope === 'profile') {
    return {
      discussionId: 0,
      key: `profile-${definition.type}`,
      title: definition.groupLabel || '账号状态',
    }
  }

  return {
    discussionId: 0,
    key: `type-${definition.type || 'general'}`,
    title: definition.groupLabel || definition.label || fallbackTitle,
  }
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
