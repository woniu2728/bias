import { extendForum } from '@bias/forum'

export const extend = [
  extendForum(registerApprovalForum),
]

function registerApprovalForum(forum) {
  registerApprovalNotificationRenderers(forum)
  registerApprovalBadges(forum)
  registerApprovalReviewBanners(forum)
  registerApprovalFeedback(forum)
  registerApprovalComposerNotices(forum)
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
    resolve: ({ canModeratePendingDiscussion }) => ({
      title: '讨论正在审核中',
      tone: 'warning',
      message: '这条讨论当前仅你和管理员可见，审核通过后才会出现在论坛列表中。',
      actions: canModeratePendingDiscussion
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
    resolve: ({ discussion, canModeratePendingDiscussion, canEditDiscussion }) => ({
      title: '讨论审核未通过',
      tone: 'danger',
      message: discussion.approval_note || '管理员拒绝了这条讨论，请根据反馈调整后重新发布。',
      actions: canModeratePendingDiscussion
        ? [
            { key: 'approve', label: '审核通过', tone: 'approve', action: 'approve' },
            { key: 'reject', label: '拒绝讨论', tone: 'reject', action: 'reject' },
          ]
        : (canEditDiscussion
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
    resolve: ({ post, canModeratePendingPost }) => ({
      tone: 'warning',
      message: '这条回复正在审核中，目前仅你和管理员可见。',
      actions: canModeratePendingPost(post)
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
    resolve: ({ post, canModeratePendingPost, canEditPost }) => ({
      tone: 'danger',
      message: post.approval_note || '这条回复未通过审核，请根据管理员反馈调整内容。',
      actions: canModeratePendingPost(post)
        ? [
            { key: 'approve', label: '审核通过', tone: 'approve', action: 'approve' },
            { key: 'reject', label: '拒绝回复', tone: 'reject', action: 'reject' },
          ]
        : (canEditPost(post)
            ? [{ key: 'edit', label: '修改后重新提交', tone: 'approve', action: 'edit' }]
            : []),
    }),
  })
}

function registerApprovalFeedback(forum) {
  forum.approvalNote({
    key: 'rejected-discussion-list',
    moduleId: 'approval',
    order: 10,
    surfaces: ['discussion-list-item', 'profile-discussion'],
    isVisible: ({ discussion }) => Boolean(discussion?.approval_status === 'rejected' && discussion?.approval_note),
    resolve: ({ discussion }) => ({
      text: `审核反馈：${discussion.approval_note}`,
    }),
  })

  forum.approvalNote({
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
      return Boolean(
        isEditing
        && composerStore?.current?.approvalStatus === 'rejected'
        && composerStore?.current?.approvalNote
      )
    },
    resolve: ({ type, composerStore }) => ({
      label: type === 'discussion' ? '讨论审核反馈' : '回复审核反馈',
      tone: 'warning',
      message: composerStore.current.approvalNote,
    }),
  })
}
