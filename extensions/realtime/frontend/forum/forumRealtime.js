import { getForumRealtimeEvents } from './realtimeFrontendRegistry.js'

export const FORUM_REALTIME_REFRESH_EVENT_TYPES = new Set([
  'discussion.hidden',
  'post.hidden',
])

const CORE_NEW_REPLY_EVENT_TYPES = new Set([
  'post.created',
])

const CORE_APPEND_POST_EVENT_TYPES = new Set([
  'post.created',
])

const CORE_UPSERT_POST_EVENT_TYPES = new Set([
  'discussion.created',
])

export function getTrackedDiscussionIdsFromDiscussionItems(items = []) {
  return items
    .map(item => Number(item?.id))
    .filter(value => Number.isInteger(value) && value > 0)
}

export function getTrackedDiscussionIdsFromPostItems(items = []) {
  return items
    .map(item => Number(item?.discussion_id || item?.discussion?.id))
    .filter(value => Number.isInteger(value) && value > 0)
}

export function hasTrackedDiscussionId(targetIds, discussionId) {
  if (!discussionId) return false
  const trackedIds = new Set((targetIds || []).map(value => String(value)))
  return trackedIds.has(String(discussionId))
}

export function getForumRealtimeEventPolicy(eventType, context = {}) {
  const normalizedEventType = String(eventType || '').trim()
  const policy = {
    appendPost: CORE_APPEND_POST_EVENT_TYPES.has(normalizedEventType),
    newReply: CORE_NEW_REPLY_EVENT_TYPES.has(normalizedEventType),
    refresh: FORUM_REALTIME_REFRESH_EVENT_TYPES.has(normalizedEventType),
    upsertPost: CORE_UPSERT_POST_EVENT_TYPES.has(normalizedEventType),
  }

  const extensionContext = {
    ...context,
    eventType: normalizedEventType,
    event_type: normalizedEventType,
  }

  for (const item of getForumRealtimeEvents(extensionContext)) {
    if (!matchesForumRealtimeEvent(item, normalizedEventType)) {
      continue
    }
    policy.appendPost ||= Boolean(item.appendPost || item.append_post)
    policy.newReply ||= Boolean(item.newReply || item.new_reply)
    policy.refresh ||= Boolean(item.refresh)
    policy.upsertPost ||= Boolean(item.upsertPost || item.upsert_post)
  }

  return policy
}

export function shouldRefreshForumEvent(eventType, context = {}) {
  return getForumRealtimeEventPolicy(eventType, context).refresh
}

export function shouldMarkForumEventAsNewReply(eventType, context = {}) {
  return getForumRealtimeEventPolicy(eventType, context).newReply
}

export function shouldAppendForumRealtimePost(eventType, context = {}) {
  return getForumRealtimeEventPolicy(eventType, context).appendPost
}

export function shouldUpsertForumRealtimePost(eventType, context = {}) {
  return getForumRealtimeEventPolicy(eventType, context).upsertPost
}

export function mergeForumEventPayload(resourceStore, event) {
  if (!resourceStore || !event || typeof event !== 'object') {
    return
  }

  resourceStore.mergePayload(event.payload || {})
}

function matchesForumRealtimeEvent(item = {}, eventType = '') {
  const eventTypes = item.eventTypes || item.event_types || item.events || item.types || item.type
  if (Array.isArray(eventTypes)) {
    return eventTypes.map(value => String(value || '').trim()).includes(eventType)
  }
  return String(eventTypes || '').trim() === eventType
}
