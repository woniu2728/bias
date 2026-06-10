import {
  api } from '@bias/core'
import {
  getUiCopy,
  ModerationActionModal
} from '@bias/forum'

export function registerApprovalModerationActions(forum) {
  registerApprovalModerationCopy(forum)
  registerApprovalDiscussionModerationActions(forum)
  registerApprovalPostModerationActions(forum)
}

function registerApprovalDiscussionModerationActions(forum) {
  for (const action of ['approve', 'reject']) {
    forum.discussionActionHandler({
      key: action,
      moduleId: 'approval',
      order: action === 'approve' ? 10 : 20,
      isVisible: ({ discussion }) => Boolean(discussion?.approval_status === 'pending' || discussion?.approval_status === 'rejected'),
      resolve: () => ({
        handle: context => runApprovalModeration({
          ...context,
          action,
          targetType: 'discussion',
          target: context.discussion,
        }),
      }),
    })
  }
}

function registerApprovalPostModerationActions(forum) {
  for (const action of ['approve', 'reject']) {
    forum.postActionHandler({
      key: action,
      moduleId: 'approval',
      order: action === 'approve' ? 10 : 20,
      isVisible: ({ post }) => Boolean(post?.approval_status === 'pending' || post?.approval_status === 'rejected'),
      resolve: () => ({
        handle: context => runApprovalModeration({
          ...context,
          action,
          targetType: 'post',
          target: context.post,
        }),
      }),
    })
  }
}

function registerApprovalModerationCopy(forum) {
  for (const item of [
    {
      key: 'moderation-action-close-label',
      order: 900,
      text: () => '关闭',
    },
    {
      key: 'moderation-action-note-label',
      order: 910,
      text: () => '处理备注',
    },
    {
      key: 'moderation-action-note-help',
      order: 920,
      text: () => '备注会同步显示给内容作者，建议简明说明处理原因。',
    },
    {
      key: 'moderation-action-submit-button',
      order: 930,
      text: ({ submitting, confirmText }) => (submitting ? '提交中...' : (confirmText || '提交')),
    },
    {
      key: 'discussion-detail-moderation-title',
      order: 90,
      text: ({ targetType, action, postNumber }) => {
        if (targetType === 'post') {
          return action === 'approve' ? `审核通过 #${postNumber}` : `拒绝 #${postNumber}`
        }
        return action === 'approve' ? '审核通过讨论' : '拒绝讨论'
      },
    },
    {
      key: 'discussion-detail-moderation-description',
      order: 91,
      text: ({ targetType, action }) => {
        if (targetType === 'post') {
          return action === 'approve'
            ? '通过后，这条回复会立刻出现在讨论流中。'
            : '拒绝后，回复作者仍可在前台看到你的审核反馈。'
        }
        return action === 'approve'
          ? '通过后，这条讨论会立即对其他用户可见。'
          : '拒绝后，讨论作者仍可在前台看到你的审核反馈。'
      },
    },
    {
      key: 'discussion-detail-moderation-confirm',
      order: 92,
      text: ({ action }) => action === 'approve' ? '通过审核' : '确认拒绝',
    },
    {
      key: 'discussion-detail-moderation-placeholder',
      order: 93,
      text: ({ targetType, action }) => {
        if (action === 'approve') {
          return '例如：内容符合社区规范，已放行'
        }
        return targetType === 'post'
          ? '例如：回复缺少上下文，请补充后重新提交'
          : '例如：标题与正文需要补充后再发布'
      },
    },
    {
      key: 'discussion-detail-moderation-success-title',
      order: 94,
      text: ({ targetType, action }) => {
        if (targetType === 'post') {
          return action === 'approve' ? '回复已通过' : '回复已拒绝'
        }
        return action === 'approve' ? '讨论已通过' : '讨论已拒绝'
      },
    },
    {
      key: 'discussion-detail-moderation-success-message',
      order: 95,
      text: ({ targetType, action }) => {
        if (targetType === 'post') {
          return action === 'approve'
            ? '这条回复现在已经加入讨论流。'
            : '作者现在可以在前台看到你的审核反馈。'
        }
        return action === 'approve'
          ? '这条讨论现在已经对其他用户可见。'
          : '作者现在可以在前台看到你的审核反馈。'
      },
    },
  ]) {
    forum.uiCopy({
      key: item.key,
      moduleId: 'approval',
      order: item.order,
      surfaces: [item.key],
      resolve: context => ({
        text: item.text(context || {}),
      }),
    })
  }
}

async function runApprovalModeration(context = {}) {
  const targetType = context.targetType
  const target = context.target
  const action = context.action || context.item?.action || context.item?.key
  if (!target?.id || !['discussion', 'post'].includes(targetType) || !['approve', 'reject'].includes(action)) {
    return false
  }

  const modalStore = context.modalStore
  if (typeof modalStore?.show !== 'function') {
    return false
  }

  const copyContext = {
    action,
    postNumber: target.number,
    targetType,
  }
  const isApprove = action === 'approve'
  const result = await modalStore.show(
    ModerationActionModal,
    {
      title: getCopy('discussion-detail-moderation-title', isApprove ? '审核通过' : '拒绝', copyContext),
      description: getCopy('discussion-detail-moderation-description', '', copyContext),
      confirmText: getCopy('discussion-detail-moderation-confirm', isApprove ? '通过审核' : '确认拒绝', copyContext),
      confirmTone: isApprove ? 'primary' : 'danger',
      placeholder: getCopy('discussion-detail-moderation-placeholder', '', copyContext),
      submitAction: ({ note }) => api.post(
        `/admin/approval-queue/${targetType}/${target.id}/${action}`,
        { note },
      ),
    },
    {
      size: 'small',
    },
  )

  if (!result) {
    return false
  }

  if (typeof context.refreshDiscussion === 'function') {
    await context.refreshDiscussion()
  }

  if (typeof modalStore.alert === 'function') {
    await modalStore.alert({
      title: getCopy('discussion-detail-moderation-success-title', isApprove ? '已通过' : '已拒绝', copyContext),
      message: getCopy('discussion-detail-moderation-success-message', '', copyContext),
    })
  }

  return true
}

function getCopy(surface, fallback, context = {}) {
  return getUiCopy({
    surface,
    ...context,
  })?.text || fallback
}
