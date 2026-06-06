import { AdminPage } from '@bias/admin'

const PAGE_KEY = 'flags.index'

export function buildFlagsPageExtender() {
  return new AdminPage(PAGE_KEY)
    .copy({
  key: 'flags-page-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '举报管理',
    pageDescription: '处理用户提交的帖子举报',
    loadingText: '加载中...',
    emptyText: '暂无举报记录',
    reporterPrefix: '举报人',
    discussionPrefix: '讨论',
    postPrefix: '帖子',
    viewPostLabel: '查看帖子',
    reasonBlockTitle: '举报说明',
    postBlockTitle: '帖子内容',
    emptyReasonText: '用户未填写补充说明',
    resolveLabel: '标记已处理',
    ignoreLabel: '忽略举报',
    resolverPrefix: '处理人',
    resolutionNotePrefix: '备注',
    unknownResolverLabel: '未知',
    statusOpenLabel: '待处理',
    statusResolvedLabel: '已处理',
    statusIgnoredLabel: '已忽略',
    modalResolveTitle: '标记举报已处理',
    modalIgnoreTitle: '忽略举报',
    modalResolveDescription: '标记后这条举报会从待处理列表移出。',
    modalIgnoreDescription: '忽略后举报会进入已忽略列表，便于后续追溯。',
    noteLabel: '处理备注',
    resolveNotePlaceholder: '例如：已隐藏帖子并警告用户',
    ignoreNotePlaceholder: '例如：举报理由不足，暂不处理',
  }),
})
    .config({
  key: 'flags-page-config',
  order: 10,
  resolve: () => ({
    filters: [
      { value: 'open', label: '待处理', icon: 'fas fa-inbox' },
      { value: 'resolved', label: '已处理', icon: 'fas fa-check-circle' },
      { value: 'ignored', label: '已忽略', icon: 'fas fa-ban' },
    ],
  }),
})
    .actionMeta({
  key: 'flags-page-actions-meta',
  order: 10,
  resolve: () => ({
    loadErrorText: '加载举报失败，请稍后重试',
    resolveSuccessTitle: '举报已处理',
    resolveSuccessMessage: '举报状态已更新为已处理。',
    ignoreSuccessTitle: '举报已忽略',
    ignoreSuccessMessage: '举报状态已更新为已忽略。',
    resolveFailedTitle: '处理失败',
    resolveFailedMessage: '未知错误',
  }),
})
}
