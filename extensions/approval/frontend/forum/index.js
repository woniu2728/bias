import { extendForum } from '@bias/forum'
import DiscussionApprovedPostItem from './components/DiscussionApprovedPostItem.vue'
import DiscussionRejectedPostItem from './components/DiscussionRejectedPostItem.vue'
import DiscussionResubmittedPostItem from './components/DiscussionResubmittedPostItem.vue'
import PostApprovedPostItem from './components/PostApprovedPostItem.vue'
import PostRejectedPostItem from './components/PostRejectedPostItem.vue'
import PostResubmittedPostItem from './components/PostResubmittedPostItem.vue'
import {
  getApprovalComposerState,
  registerApprovalComposerCopy,
  registerApprovalComposerInitialState,
  registerApprovalComposerSubmitSuccess,
} from './approvalComposer.js'
import { registerApprovalModerationActions } from './approvalModerationActions.js'

export const extend = [
  extendForum(registerApprovalForum),
]

function registerApprovalForum(forum) {
  registerApprovalPostTypes(forum)
  registerApprovalNotificationRenderers(forum)
  registerApprovalBadges(forum)
  registerApprovalReviewBanners(forum)
  registerApprovalModerationActions(forum)
  registerApprovalFeedback(forum)
  registerApprovalComposerNotices(forum)
  registerApprovalRealtimeEvents(forum)
  registerApprovalComposerCopy(forum)
  registerApprovalComposerInitialState(forum)
  registerApprovalComposerSubmitSuccess(forum)
}

function registerApprovalPostTypes(forum) {
  for (const item of [
    {
      type: 'discussionApproved',
      label: '讨论审核通过',
      component: DiscussionApprovedPostItem,
      order: 70,
    },
    {
      type: 'discussionRejected',
      label: '讨论审核拒绝',
      component: DiscussionRejectedPostItem,
      order: 80,
    },
    {
      type: 'discussionResubmitted',
      label: '讨论重新提交审核',
      component: DiscussionResubmittedPostItem,
      order: 90,
    },
    {
      type: 'postApproved',
      label: '回复审核通过',
      component: PostApprovedPostItem,
      order: 100,
    },
    {
      type: 'postRejected',
      label: '回复审核拒绝',
      component: PostRejectedPostItem,
      order: 110,
    },
    {
      type: 'postResubmitted',
      label: '回复重新提交审核',
      component: PostResubmittedPostItem,
      order: 120,
    },
  ]) {
    forum.postType(item.type, {
      label: item.label,
      component: item.component,
      order: item.order,
      moduleId: 'approval',
    })
  }
}

function registerApprovalNotificationRenderers(forum) {
  forum.notificationRenderer({
    type: 'discussionApproved',
    key: 'discussionApproved',
    moduleId: 'approval',
    label: '讨论审核通过',
    icon: 'fas fa-circle-check',
    navigationScope: 'discussion',
    groupLabel: '审核结果',
    order: 50,
    getText(notification) {
      const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
      const discussionTitle = notification?.data?.discussion_title || ''
      return `${fromUser} 通过了你的讨论 "${discussionTitle}"`
    },
  })

  forum.notificationRenderer({
    type: 'discussionRejected',
    key: 'discussionRejected',
    moduleId: 'approval',
    label: '讨论审核拒绝',
    icon: 'fas fa-circle-xmark',
    navigationScope: 'discussion',
    groupLabel: '审核结果',
    order: 60,
    getText(notification) {
      const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
      const discussionTitle = notification?.data?.discussion_title || ''
      const note = notification?.data?.approval_note ? `：${notification.data.approval_note}` : ''
      return `${fromUser} 拒绝了你的讨论 "${discussionTitle}"${note}`
    },
  })

  forum.notificationRenderer({
    type: 'postApproved',
    key: 'postApproved',
    moduleId: 'approval',
    label: '回复审核通过',
    icon: 'fas fa-check',
    navigationScope: 'post',
    groupLabel: '审核结果',
    order: 70,
    getText(notification) {
      const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
      const discussionTitle = notification?.data?.discussion_title || ''
      return `${fromUser} 通过了你在 "${discussionTitle}" 中的回复`
    },
  })

  forum.notificationRenderer({
    type: 'postRejected',
    key: 'postRejected',
    moduleId: 'approval',
    label: '回复审核拒绝',
    icon: 'fas fa-xmark',
    navigationScope: 'post',
    groupLabel: '审核结果',
    order: 80,
    getText(notification) {
      const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
      const discussionTitle = notification?.data?.discussion_title || ''
      const note = notification?.data?.approval_note ? `：${notification.data.approval_note}` : ''
      return `${fromUser} 拒绝了你在 "${discussionTitle}" 中的回复${note}`
    },
  })
}

function registerApprovalBadges(forum) {
  forum.discussionBadge({
    key: 'pending',
    moduleId: 'approval',
    order: 40,
    surfaces: ['hero'],
    isVisible: ({ discussion }) => discussion?.approval_status === 'pending',
    resolve: () => ({
      className: 'badge-pending',
      label: '待审核',
    }),
  })

  forum.discussionStateBadge({
    key: 'pending',
    moduleId: 'approval',
    order: 10,
    surfaces: ['discussion-list-item', 'profile-discussion'],
    isVisible: ({ discussion }) => discussion?.approval_status === 'pending',
    resolve: () => ({
      label: '待审核',
      tone: 'warning',
    }),
  })

  forum.discussionStateBadge({
    key: 'rejected',
    moduleId: 'approval',
    order: 20,
    surfaces: ['discussion-list-item', 'profile-discussion'],
    isVisible: ({ discussion }) => discussion?.approval_status === 'rejected',
    resolve: () => ({
      label: '已拒绝',
      tone: 'danger',
    }),
  })

  forum.postStateBadge({
    key: 'pending',
    moduleId: 'approval',
    order: 10,
    surfaces: ['profile-post', 'discussion-post'],
    isVisible: ({ post }) => post?.approval_status === 'pending',
    resolve: () => ({
      label: '待审核',
      tone: 'warning',
    }),
  })

  forum.postStateBadge({
    key: 'rejected',
    moduleId: 'approval',
    order: 20,
    surfaces: ['profile-post', 'discussion-post'],
    isVisible: ({ post }) => post?.approval_status === 'rejected',
    resolve: () => ({
      label: '已拒绝',
      tone: 'danger',
    }),
  })
}

function registerApprovalReviewBanners(forum) {
  forum.discussionReplyState({
    key: 'pending',
    moduleId: 'approval',
    order: 40,
    surfaces: ['discussion-reply'],
    isVisible: ({ discussion }) => discussion?.approval_status === 'pending',
    resolve: () => ({
      kind: 'notice',
      tone: 'warning',
      message: '讨论正在审核中，暂时无法继续回复',
    }),
  })

  forum.discussionReplyState({
    key: 'rejected',
    moduleId: 'approval',
    order: 50,
    surfaces: ['discussion-reply'],
    isVisible: ({ discussion }) => discussion?.approval_status === 'rejected',
    resolve: () => ({
      kind: 'notice',
      tone: 'warning',
      message: '讨论未通过审核，需调整后重新发布',
    }),
  })

  forum.discussionReviewBanner({
    key: 'pending',
    moduleId: 'approval',
    order: 10,
    surfaces: ['discussion-hero'],
    isVisible: ({ discussion }) => discussion?.approval_status === 'pending',
    resolve: context => ({
      title: '讨论正在审核中',
      tone: 'warning',
      message: '这条讨论当前仅你和管理员可见，审核通过后才会出现在论坛列表中。',
      actions: canModerateDiscussion(context)
        ? [
            { key: 'approve', label: '审核通过', tone: 'approve', action: 'approve' },
            { key: 'reject', label: '拒绝讨论', tone: 'reject', action: 'reject' },
          ]
        : [],
    }),
  })

  forum.discussionReviewBanner({
    key: 'rejected',
    moduleId: 'approval',
    order: 20,
    surfaces: ['discussion-hero'],
    isVisible: ({ discussion }) => discussion?.approval_status === 'rejected',
    resolve: context => ({
      title: '讨论审核未通过',
      tone: 'danger',
      message: context.discussion.approval_note || '管理员拒绝了这条讨论，请根据反馈调整后重新发布。',
      actions: canModerateDiscussion(context)
        ? [
            { key: 'approve', label: '审核通过', tone: 'approve', action: 'approve' },
            { key: 'reject', label: '拒绝讨论', tone: 'reject', action: 'reject' },
          ]
        : (context.canEditDiscussion
            ? [{ key: 'edit', label: '修改后重新提交', tone: 'approve', action: 'edit' }]
            : []),
    }),
  })

  forum.postReviewBanner({
    key: 'pending',
    moduleId: 'approval',
    order: 10,
    surfaces: ['discussion-post'],
    isVisible: ({ post }) => post?.approval_status === 'pending',
    resolve: context => ({
      tone: 'warning',
      message: '这条回复正在审核中，目前仅你和管理员可见。',
      actions: canModeratePost(context)
        ? [
            { key: 'approve', label: '审核通过', tone: 'approve', action: 'approve' },
            { key: 'reject', label: '拒绝回复', tone: 'reject', action: 'reject' },
          ]
        : [],
    }),
  })

  forum.postReviewBanner({
    key: 'rejected',
    moduleId: 'approval',
    order: 20,
    surfaces: ['discussion-post'],
    isVisible: ({ post }) => post?.approval_status === 'rejected',
    resolve: context => ({
      tone: 'danger',
      message: context.post.approval_note || '这条回复未通过审核，请根据管理员反馈调整内容。',
      actions: canModeratePost(context)
        ? [
            { key: 'approve', label: '审核通过', tone: 'approve', action: 'approve' },
            { key: 'reject', label: '拒绝回复', tone: 'reject', action: 'reject' },
          ]
        : (context.canEditPost(context.post)
            ? [{ key: 'edit', label: '修改后重新提交', tone: 'approve', action: 'edit' }]
            : []),
    }),
  })
}

function canModerateDiscussion(context = {}) {
  return Boolean(context.authStore?.user?.is_staff && context.discussion?.approval_status === 'pending')
}

function canModeratePost(context = {}) {
  return Boolean(context.authStore?.user?.is_staff && context.post?.approval_status === 'pending')
}

function registerApprovalFeedback(forum) {
  forum.feedbackNote({
    key: 'rejected-discussion-list',
    moduleId: 'approval',
    order: 10,
    surfaces: ['discussion-list-item', 'profile-discussion'],
    isVisible: ({ discussion }) => Boolean(discussion?.approval_status === 'rejected' && discussion?.approval_note),
    resolve: ({ discussion }) => ({
      text: `审核反馈：${discussion.approval_note}`,
    }),
  })

  forum.feedbackNote({
    key: 'rejected-profile-post',
    moduleId: 'approval',
    order: 20,
    surfaces: ['profile-post'],
    isVisible: ({ post }) => Boolean(post?.approval_status === 'rejected' && post?.approval_note),
    resolve: ({ post }) => ({
      text: `审核反馈：${post.approval_note}`,
    }),
  })
}

function registerApprovalComposerNotices(forum) {
  forum.composerNotice({
    key: 'approval-feedback',
    moduleId: 'approval',
    order: 20,
    isVisible: ({ isEditing, composerStore }) => {
      const approvalState = getApprovalComposerState(composerStore?.current)
      return Boolean(
        isEditing
        && approvalState.status === 'rejected'
        && approvalState.note
      )
    },
    resolve: ({ type, composerStore }) => ({
      label: type === 'discussion' ? '讨论审核反馈' : '回复审核反馈',
      tone: 'warning',
      message: getApprovalComposerState(composerStore?.current).note,
    }),
  })
}

function registerApprovalRealtimeEvents(forum) {
  forum.realtimeEvent({
    key: 'approval-refresh-events',
    moduleId: 'approval',
    order: 10,
    eventTypes: [
      'discussion.rejected',
      'discussion.resubmitted',
      'post.rejected',
      'post.resubmitted',
    ],
    refresh: true,
  })

  forum.realtimeEvent({
    key: 'approval-approved-post-events',
    moduleId: 'approval',
    order: 20,
    eventTypes: ['post.approved'],
    appendPost: true,
    newReply: true,
  })

  forum.realtimeEvent({
    key: 'approval-discussion-event-posts',
    moduleId: 'approval',
    order: 30,
    eventTypes: ['discussion.approved'],
    upsertPost: true,
  })
}
