import DiscussionPostItem from '@/components/discussion/DiscussionPostItem.vue'
import DiscussionLockedPostItem from '@/components/discussion/DiscussionLockedPostItem.vue'
import DiscussionRenamedPostItem from '@/components/discussion/DiscussionRenamedPostItem.vue'
import DiscussionHiddenPostItem from '@/components/discussion/DiscussionHiddenPostItem.vue'
import DiscussionStickyPostItem from '@/components/discussion/DiscussionStickyPostItem.vue'
import DiscussionTaggedPostItem from '@/components/discussion/DiscussionTaggedPostItem.vue'
import DiscussionGenericEventPostItem from '@/components/discussion/DiscussionGenericEventPostItem.vue'
import DiscussionApprovedPostItem from '@/components/discussion/DiscussionApprovedPostItem.vue'
import DiscussionRejectedPostItem from '@/components/discussion/DiscussionRejectedPostItem.vue'
import DiscussionResubmittedPostItem from '@/components/discussion/DiscussionResubmittedPostItem.vue'
import PostApprovedPostItem from '@/components/discussion/PostApprovedPostItem.vue'
import PostRejectedPostItem from '@/components/discussion/PostRejectedPostItem.vue'
import PostResubmittedPostItem from '@/components/discussion/PostResubmittedPostItem.vue'
import PostHiddenPostItem from '@/components/discussion/PostHiddenPostItem.vue'

const postTypeDefinitions = []
const postTypeComponents = {
  comment: DiscussionPostItem,
  discussionRenamed: DiscussionRenamedPostItem,
  discussionLocked: DiscussionLockedPostItem,
  discussionSticky: DiscussionStickyPostItem,
  discussionTagged: DiscussionTaggedPostItem,
  discussionHidden: DiscussionHiddenPostItem,
  discussionApproved: DiscussionApprovedPostItem,
  discussionRejected: DiscussionRejectedPostItem,
  discussionResubmitted: DiscussionResubmittedPostItem,
  postApproved: PostApprovedPostItem,
  postRejected: PostRejectedPostItem,
  postResubmitted: PostResubmittedPostItem,
  postHidden: PostHiddenPostItem
}

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

  if (normalizedType !== 'comment') {
    return {
      type: normalizedType,
      label: normalizedType,
      component: DiscussionGenericEventPostItem,
      order: 999,
      isDefault: false,
      isFallback: true
    }
  }

  return (
    postTypeDefinitions.find(item => item.isDefault)
    || postTypeDefinitions[0]
    || null
  )
}

export function syncPostTypes(definitions = []) {
  definitions.forEach((definition, index) => {
    const type = String(definition?.code || definition?.type || '')
    if (!type) {
      return
    }

    registerPostType({
      ...definition,
      type,
      component: postTypeComponents[type] || DiscussionPostItem,
      isDefault: Boolean(definition?.is_default ?? definition?.isDefault),
      order: Number(definition?.order ?? ((index + 1) * 10))
    })
  })
}

syncPostTypes([
  {
    code: 'comment',
    label: '普通回复',
    is_default: true,
    order: 10
  },
  {
    code: 'discussionRenamed',
    label: '讨论改标题',
    order: 20
  },
  {
    code: 'discussionLocked',
    label: '讨论锁定状态变更',
    order: 30
  },
  {
    code: 'discussionSticky',
    label: '讨论置顶状态变更',
    order: 40
  },
  {
    code: 'discussionTagged',
    label: '讨论标签变更',
    order: 50
  },
  {
    code: 'discussionHidden',
    label: '讨论隐藏状态变更',
    order: 60
  },
  {
    code: 'discussionApproved',
    label: '讨论审核通过',
    order: 70
  },
  {
    code: 'discussionRejected',
    label: '讨论审核拒绝',
    order: 80
  },
  {
    code: 'discussionResubmitted',
    label: '讨论重新提交审核',
    order: 90
  },
  {
    code: 'postApproved',
    label: '回复审核通过',
    order: 100
  },
  {
    code: 'postRejected',
    label: '回复审核拒绝',
    order: 110
  },
  {
    code: 'postResubmitted',
    label: '回复重新提交审核',
    order: 120
  },
  {
    code: 'postHidden',
    label: '回复隐藏状态变更',
    order: 130
  }
])
