import {
  resolveDiscussionAction,
  resolvePostAction,
  runDiscussionAction,
  runPostAction,
} from '@/forum/discussionActionRuntime'
import {
  createUiTextCopy,
  getAuthModalProvider,
  getComposerNotices,
  getComposerFields,
  getComposerAutocompleteProviders,
  getComposerSecondaryActions,
  getComposerDraftMeta,
  getComposerHosts,
  getComposerUploadHandler,
  runComposerPreviewTransformers,
  getComposerStatusItems,
  getComposerTools,
  getDiscussionListHero,
  getDiscussionListContexts,
  getDiscussionListRequests,
  getForumNavItems,
  getForumNavSections,
  getForumSidebarSections,
  getForumRealtimeEvents,
  getDiscussionActions,
  getDiscussionActionHandler,
  getPostActions,
  getPostActionHandler,
  getNotificationRenderers,
  getProfilePanels,
  getSearchModalProvider,
  getSearchModalSections,
  getStartDiscussionProvider,
  getSearchSources,
  getDiscussionBadges,
  getDiscussionPresentationItems,
  getDiscussionStateBadges,
  getHeroMetaItems,
  getDiscussionReplyState,
  getDiscussionReviewBanner,
  getPostFlagPanel,
  getFeedbackNote,
  getEmptyState,
  getPageState,
  getStateBlock,
  getUiCopy,
  getPostStateBadges,
  getPostReviewBanner,
  getUserBadges,
  registerDiscussionAction,
  registerDiscussionActionHandler,
  registerDiscussionPresentation,
  registerDiscussionReplyState,
  registerDiscussionReviewBanner,
  registerHeroMeta,
  registerPostFlagPanel,
  registerFeedbackNote,
  registerEmptyState,
  registerStateBlock,
  registerUiCopy,
  registerForumRuntime,
  registerForumRealtimeEvent,
  registerPostStateBadge,
  registerPostReviewBanner,
  registerAuthModalProvider,
  registerComposerNotice,
  registerComposerField,
  registerComposerSecondaryAction,
  registerComposerPayloadContributor,
  registerComposerInitialState,
  registerComposerDraftMeta,
  registerComposerAutocompleteProvider,
  registerComposerHost,
  registerComposerUploadHandler,
  registerComposerPreviewTransformer,
  registerComposerStatusItem,
  registerComposerSubmitSuccess,
  registerComposerSubmitGuard,
  registerComposerTool,
  registerDiscussionListContext,
  registerDiscussionListRequest,
  registerHeaderItem,
  registerForumNavSection,
  registerForumSidebarSection,
  registerNotificationRenderer,
  registerProfilePanel,
  registerSearchModalProvider,
  registerSearchModalSection,
  registerStartDiscussionProvider,
  registerPostAction,
  registerPostActionHandler,
  registerSearchSource,
  registerUserBadge,
  runComposerSubmitGuards,
  runComposerPayloadContributors,
  runComposerInitialStateContributors,
  runComposerSubmitSuccess,
  runForumRuntimeHook,
} from '@/forum/frontendRegistry'
export { registerNotificationType } from './notificationTypes'
export { registerPostType } from './postTypes'
export { registerSearchFilter } from './searchFilters'

export {
  getAuthModalProvider,
  createUiTextCopy,
  getForumNavItems,
  getForumNavSections,
  getForumSidebarSections,
  getForumRealtimeEvents,
  getComposerNotices,
  getComposerFields,
  getComposerAutocompleteProviders,
  getComposerSecondaryActions,
  getComposerDraftMeta,
  getComposerHosts,
  getComposerUploadHandler,
  runComposerPreviewTransformers,
  getComposerStatusItems,
  getComposerTools,
  getDiscussionListHero,
  getDiscussionListContexts,
  getDiscussionListRequests,
  resolveDiscussionAction,
  resolvePostAction,
  getDiscussionActions,
  getDiscussionActionHandler,
  getPostActions,
  getPostActionHandler,
  getNotificationRenderers,
  getSearchModalProvider,
  getStartDiscussionProvider,
  getDiscussionBadges,
  getDiscussionPresentationItems,
  getDiscussionStateBadges,
  getHeroMetaItems,
  getDiscussionReplyState,
  getDiscussionReviewBanner,
  getPostFlagPanel,
  getFeedbackNote,
  getEmptyState,
  getPageState,
  getStateBlock,
  getUiCopy,
  getPostStateBadges,
  getPostReviewBanner,
  registerDiscussionAction,
  registerDiscussionActionHandler,
  registerDiscussionPresentation,
  registerDiscussionReplyState,
  registerDiscussionReviewBanner,
  registerHeroMeta,
  registerPostFlagPanel,
  registerFeedbackNote,
  registerEmptyState,
  registerStateBlock,
  registerUiCopy,
  registerForumRuntime,
  registerForumRealtimeEvent,
  registerPostStateBadge,
  registerPostReviewBanner,
  registerAuthModalProvider,
  registerComposerNotice,
  registerComposerField,
  registerComposerSecondaryAction,
  registerComposerPayloadContributor,
  registerComposerInitialState,
  registerComposerDraftMeta,
  registerComposerAutocompleteProvider,
  registerComposerHost,
  registerComposerUploadHandler,
  registerComposerPreviewTransformer,
  registerComposerStatusItem,
  registerComposerSubmitSuccess,
  registerComposerSubmitGuard,
  registerComposerTool,
  registerDiscussionListContext,
  registerDiscussionListRequest,
  registerHeaderItem,
  registerForumNavSection,
  registerForumSidebarSection,
  registerNotificationRenderer,
  registerProfilePanel,
  registerSearchModalProvider,
  registerSearchModalSection,
  registerStartDiscussionProvider,
  registerPostAction,
  registerPostActionHandler,
  registerSearchSource,
  registerUserBadge,
  runDiscussionAction,
  runPostAction,
  runComposerSubmitGuards,
  runComposerPayloadContributors,
  runComposerInitialStateContributors,
  runComposerSubmitSuccess,
  runForumRuntimeHook,
  getProfilePanels,
  getSearchModalSections,
  getSearchSources,
  getUserBadges,
}

registerUiCopy({
  key: 'composer-preview-loading',
  order: 50,
  surfaces: ['discussion-composer-preview-status', 'post-composer-preview-status'],
  isVisible: ({ previewLoading }) => Boolean(previewLoading),
  resolve: () => ({
    text: '同步中',
  }),
})

registerUiCopy({
  key: 'composer-preview-empty',
  order: 60,
  surfaces: ['discussion-composer-preview-status', 'post-composer-preview-status'],
  isVisible: ({ hasContent }) => !hasContent,
  resolve: () => ({
    text: '暂无内容',
  }),
})

registerUiCopy({
  key: 'composer-preview-ready',
  order: 70,
  surfaces: ['discussion-composer-preview-status', 'post-composer-preview-status'],
  isVisible: ({ previewLoading, hasContent }) => !previewLoading && Boolean(hasContent),
  resolve: () => ({
    text: '按论坛最终渲染效果预览',
  }),
})

registerUiCopy({
  key: 'composer-preview-panel-loading',
  order: 110,
  surfaces: ['composer-preview-panel-loading'],
  resolve: () => ({
    text: '正在生成预览...',
  }),
})

registerUiCopy({
  key: 'composer-preview-panel-empty',
  order: 120,
  surfaces: ['composer-preview-panel-empty'],
  resolve: () => ({
    text: '输入内容后即可查看预览',
  }),
})

registerUiCopy({
  key: 'mobile-drawer-close-label',
  order: 480,
  surfaces: ['mobile-drawer-close-label'],
  resolve: () => ({
    text: '关闭导航菜单',
  }),
})

registerUiCopy({
  key: 'composer-preview-button-title',
  order: 600,
  surfaces: ['composer-preview-button-title'],
  resolve: () => ({
    text: '预览',
  }),
})

registerUiCopy({
  key: 'composer-notice-draft-label',
  order: 646,
  surfaces: ['composer-notice-draft-label'],
  resolve: () => ({
    text: '草稿',
  }),
})

registerUiCopy({
  key: 'composer-notice-preview-label',
  order: 646,
  surfaces: ['composer-notice-preview-label'],
  resolve: () => ({
    text: '预览',
  }),
})

registerUiCopy({
  key: 'composer-notice-submit-label',
  order: 646,
  surfaces: ['composer-notice-submit-label'],
  resolve: ({ isEditing, isEditingDiscussion, type }) => {
    if (type === 'discussion') {
      return {
        text: isEditingDiscussion ? '保存' : '发布',
      }
    }

    return {
      text: isEditing ? '保存' : '发布',
    }
  },
})

registerUiCopy({
  key: 'composer-preview-load-failed',
  order: 646,
  surfaces: ['composer-preview-load-failed'],
  resolve: () => ({
    text: '预览加载失败',
  }),
})

registerUiCopy({
  key: 'composer-submit-blocked',
  order: 646,
  surfaces: ['composer-submit-blocked'],
  resolve: () => ({
    text: '当前内容未通过校验。',
  }),
})

registerUiCopy({
  key: 'composer-submit-failed',
  order: 646,
  surfaces: ['composer-submit-failed'],
  resolve: () => ({
    text: '提交失败，请稍后重试',
  }),
})

registerUiCopy({
  key: 'composer-draft-time-fallback',
  order: 646,
  surfaces: ['composer-draft-time-fallback'],
  resolve: () => ({
    text: '刚刚',
  }),
})

registerUiCopy({
  key: 'composer-date-fallback',
  order: 646,
  surfaces: ['composer-date-fallback'],
  resolve: () => ({
    text: '未知时间',
  }),
})

registerUiCopy({
  key: 'modal-close-label',
  order: 810,
  surfaces: ['modal-close-label'],
  resolve: () => ({
    text: '关闭',
  }),
})

registerUiCopy({
  key: 'modal-cancel-button',
  order: 820,
  surfaces: ['modal-cancel-button'],
  resolve: () => ({
    text: '取消',
  }),
})

registerUiCopy({
  key: 'modal-submit-error',
  order: 830,
  surfaces: ['modal-submit-error'],
  resolve: () => ({
    text: '提交失败，请稍后重试',
  }),
})

registerUiCopy({
  key: 'composer-formatting-toolbar-label',
  order: 1100,
  surfaces: ['composer-formatting-toolbar-label'],
  resolve: () => ({
    text: '格式化工具栏',
  }),
})

registerUiCopy({
  key: 'composer-status-bar-label',
  order: 1110,
  surfaces: ['composer-status-bar-label'],
  resolve: () => ({
    text: '编辑器状态',
  }),
})

registerUiCopy({
  key: 'composer-preview-panel-title',
  order: 1120,
  surfaces: ['composer-preview-panel-title'],
  resolve: () => ({
    text: '预览',
  }),
})

registerUiCopy({
  key: 'composer-header-save-draft',
  order: 1270,
  surfaces: ['composer-header-save-draft'],
  resolve: ({ submitting }) => ({
    text: submitting ? '提交中，暂不可保存草稿' : '保存草稿',
  }),
})

registerUiCopy({
  key: 'composer-header-toggle-minimized',
  order: 1280,
  surfaces: ['composer-header-toggle-minimized'],
  resolve: ({ minimized }) => ({
    text: minimized ? '展开' : '最小化',
  }),
})

registerUiCopy({
  key: 'composer-header-toggle-expanded',
  order: 1290,
  surfaces: ['composer-header-toggle-expanded'],
  resolve: ({ expanded }) => ({
    text: expanded ? '退出全屏' : '全屏',
  }),
})

registerUiCopy({
  key: 'composer-header-close',
  order: 1300,
  surfaces: ['composer-header-close'],
  resolve: () => ({
    text: '关闭',
  }),
})
