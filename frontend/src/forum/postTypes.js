import DiscussionPostItem from '@/components/discussion/DiscussionPostItem.vue'
import DiscussionLockedPostItem from '@/components/discussion/DiscussionLockedPostItem.vue'
import DiscussionRenamedPostItem from '@/components/discussion/DiscussionRenamedPostItem.vue'

const postTypeDefinitions = []

export function registerPostType(definition) {
  const normalizedDefinition = {
    order: 100,
    ...definition
  }

  const existingIndex = postTypeDefinitions.findIndex(item => item.type === normalizedDefinition.type)
  if (existingIndex >= 0) {
    postTypeDefinitions.splice(existingIndex, 1, normalizedDefinition)
    return normalizedDefinition
  }

  postTypeDefinitions.push(normalizedDefinition)
  return normalizedDefinition
}

export function getPostTypeDefinition(type) {
  const normalizedType = String(type || 'comment')
  const exactMatch = postTypeDefinitions.find(item => item.type === normalizedType)
  if (exactMatch) {
    return exactMatch
  }

  return (
    postTypeDefinitions.find(item => item.isDefault)
    || postTypeDefinitions[0]
    || null
  )
}

registerPostType({
  type: 'comment',
  label: '普通回复',
  component: DiscussionPostItem,
  isDefault: true,
  order: 10
})

registerPostType({
  type: 'discussionRenamed',
  label: '讨论改标题',
  component: DiscussionRenamedPostItem,
  order: 20
})

registerPostType({
  type: 'discussionLocked',
  label: '讨论锁定状态变更',
  component: DiscussionLockedPostItem,
  order: 30
})
