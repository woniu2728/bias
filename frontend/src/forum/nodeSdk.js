export {
  ForumExtender,
  extendForum,
} from '../common/sdk.js'
export {
  getComposerNotices,
  getComposerFields,
  getComposerSecondaryActions,
  getComposerDraftMeta,
  getComposerHosts,
  getComposerUploadHandler,
  createUiTextCopy,
  runComposerPreviewTransformers,
  getComposerStatusItems,
  getComposerTools,
  getComposerAutocompleteProviders,
  getEmptyState,
  getFeedbackNote,
  getForumNavItems,
  getForumNavSections,
  getForumSidebarSections,
  getHeroMetaItems,
  getPageState,
  getStateBlock,
  getUiCopy,
  registerComposerNotice,
  registerComposerField,
  registerComposerHost,
  registerComposerUploadHandler,
  registerComposerSecondaryAction,
  registerComposerInitialState,
  registerComposerPayloadContributor,
  registerComposerAutocompleteProvider,
  registerComposerPreviewTransformer,
  registerComposerStatusItem,
  registerComposerSubmitGuard,
  registerComposerSubmitSuccess,
  registerComposerTool,
  registerEmptyState,
  registerFeedbackNote,
  registerForumRuntime,
  registerForumNavSection,
  registerForumSidebarSection,
  registerHeaderItem,
  registerHeroMeta,
  registerStateBlock,
  registerUiCopy,
  runComposerInitialStateContributors,
  runComposerPayloadContributors,
  runComposerSubmitGuards,
  runComposerSubmitSuccess,
  runForumRuntimeHook,
} from './frontendRegistry.js'
export const ModerationActionModal = null
export const ForumActionMenu = null
export const ForumHeroPanel = null
export const ForumInlineMessage = null
export const ForumLoadMoreButton = null
export const ForumPageWithSidebar = null
export const ForumPagination = null
export const ForumPrimaryNav = null
export const ForumSearchFilterNav = null
export const ForumStateBadge = null
export const ForumStateBlock = null
export const ComposerActionBar = null
export const ComposerAutocompleteOutlet = null
export const ComposerHeaderBar = null
export const ComposerNoticeStack = null
export const ComposerPreviewPanel = null
export const ComposerStatusBar = null

export function useForumUiStore() {
  return {
    applyRuntimeState() {},
    hydrateFromUiValues() {},
    initialize() {},
    refreshFromUserPreferences() {},
    reset() {},
    syncFromForumSettings() {},
  }
}
export {
  getTextareaCaretCoordinates,
} from '../utils/composer.js'
export function useComposerRuntime() {
  return {}
}
