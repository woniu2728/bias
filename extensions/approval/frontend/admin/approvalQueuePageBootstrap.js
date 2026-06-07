import { extendAdmin } from '@bias/admin'

const PAGE_KEY = 'approval.queue'

export function buildApprovalQueuePageExtender() {
  return extendAdmin(admin => admin
    .pageCopy(PAGE_KEY, {
  key: 'core-approval-queue-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '审核队列',
    pageDescription: '审核未验证邮箱用户提交的讨论和回复',
    loadingText: '加载中...',
    emptyText: '当前没有待审核内容',
    discussionTypeLabel: '讨论',
    postTypeLabel: '回复',
    unknownAuthorLabel: '未知',
    authorPrefix: '作者',
    submittedAtPrefix: '提交于',
    floorPrefix: '楼层',
    viewContentLabel: '查看内容',
    emptyContentText: '暂无正文内容',
    approveLabel: '审核通过',
    rejectLabel: '拒绝并隐藏',
    selectAllLabel: '全选当前列表',
    selectItemLabel: '选择此项',
    bulkApproveLabel: '批量通过',
    bulkRejectLabel: '批量拒绝',
    clearSelectionLabel: '清空选择',
    bulkSelectionSummary: count => `已选择 ${count} 项`,
    modalApproveTitle: '审核通过',
    modalRejectTitle: '拒绝内容',
    modalApproveDescription: '通过后内容会对有权限的用户可见。',
    modalRejectDescription: '拒绝后作者仍可看到审核反馈。',
    noteLabel: '审核备注',
    noteTemplatesLabel: '常用模板',
    noteTemplatesHint: '点击可快速填入审核反馈，你仍可继续修改。',
    approveNotePlaceholder: '例如：内容符合社区规范，已放行',
    rejectNotePlaceholder: '例如：内容质量不足，已拒绝',
    confirmApproveText: '通过审核',
    confirmRejectText: '拒绝并隐藏',
    bulkApproveConfirmTitle: '批量通过审核',
    bulkRejectConfirmTitle: '批量拒绝内容',
    bulkApproveConfirmMessage: count => `确定批量通过这 ${count} 条待审核内容吗？`,
    bulkRejectConfirmMessage: count => `确定批量拒绝这 ${count} 条待审核内容吗？`,
    bulkApproveConfirmText: '批量通过',
    bulkRejectConfirmText: '批量拒绝',
    bulkActionCancelText: '取消',
    unknownTimeText: '未知时间',
  }),
})
    .pageConfig(PAGE_KEY, {
  key: 'core-approval-queue-page-config',
  order: 10,
  resolve: () => ({
    filters: [
      { value: 'all', label: '全部', icon: 'fas fa-layer-group' },
      { value: 'discussion', label: '讨论', icon: 'fas fa-comments' },
      { value: 'post', label: '回复', icon: 'fas fa-reply' },
    ],
  }),
})
    .pageActionMeta(PAGE_KEY, {
  key: 'core-approval-queue-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载审核队列失败，请稍后重试',
    approveSuccessTitle: '审核已通过',
    approveSuccessMessage: '内容已放行，用户现在可以正常查看。',
    rejectSuccessTitle: '内容已拒绝',
    rejectSuccessMessage: '内容已拒绝并隐藏。',
    bulkApproveSuccessTitle: '批量审核已通过',
    bulkApproveSuccessMessage: count => `已批量通过 ${count} 条内容。`,
    bulkRejectSuccessTitle: '批量拒绝已完成',
    bulkRejectSuccessMessage: count => `已批量拒绝 ${count} 条内容。`,
    submitFailedTitle: '提交失败',
    submitFailedMessage: '未知错误',
  }),
})
    .pageNoteTemplate(PAGE_KEY, {
  key: 'approval-approve-compliant',
  order: 10,
  resolve: () => ({
    label: '内容符合规范',
    value: '内容符合社区规范，已放行。',
    description: '适用于无需额外修改的通过场景。',
    actions: ['approve'],
  }),
})
    .pageNoteTemplate(PAGE_KEY, {
  key: 'approval-approve-context-complete',
  order: 20,
  resolve: () => ({
    label: '补充后通过',
    value: '已补充必要上下文，现已通过审核。',
    description: '适用于作者补充说明后的放行场景。',
    actions: ['approve'],
  }),
})
    .pageNoteTemplate(PAGE_KEY, {
  key: 'approval-reject-quality',
  order: 30,
  resolve: () => ({
    label: '内容质量不足',
    value: '内容质量不足，请补充更完整的信息后重新提交。',
    description: '适用于讨论或回复内容过短、信息不足的场景。',
    actions: ['reject'],
  }),
})
    .pageNoteTemplate(PAGE_KEY, {
  key: 'approval-reject-duplicate',
  order: 40,
  resolve: () => ({
    label: '重复内容',
    value: '内容与现有讨论重复，请优先在已有主题下继续交流。',
    description: '适用于重复发帖或重复回复场景。',
    actions: ['reject'],
    itemTypes: ['discussion', 'post'],
  }),
})
    .pageNoteTemplate(PAGE_KEY, {
  key: 'approval-reject-format',
  order: 50,
  resolve: () => ({
    label: '表达不完整',
    value: '表达不完整或缺少必要上下文，请整理后重新提交。',
    description: '适用于语义不清、缺少上下文的场景。',
    actions: ['reject'],
  }),
}))
}
