export const DiscussionEventPostBase = null
export const DiscussionHero = null
export const DiscussionListContent = null
export const DiscussionListSidebar = null
export const DiscussionListSidebarStartButton = null
export const DiscussionMobileActions = null
export const DiscussionReplyState = null
export const DiscussionSidebar = null
export {
  getDiscussionBadges,
  getDiscussionListContexts,
  getDiscussionListHero,
  getDiscussionListRequests,
  getDiscussionMenuItems,
  getDiscussionPresentationItems,
  getDiscussionReplyState,
  getDiscussionReviewBanner,
  getDiscussionStateBadges,
  registerDiscussionAction,
  registerDiscussionActionHandler,
  registerDiscussionListContext,
  registerDiscussionListHero,
  registerDiscussionListRequest,
  registerDiscussionPresentation,
  registerDiscussionReplyState,
  registerDiscussionReviewBanner,
  registerStartDiscussionProvider,
  getStartDiscussionProvider,
  runDiscussionAction,
} from './discussionFrontendRegistry.js'
export {
  getDiscussionListFilterHeroDescriptionText,
  getDiscussionListFilterHeroTitleText,
  getDiscussionListFilterLabelText,
  resolveDiscussionListActiveFilterCode,
  resolveDiscussionListPageMetaDescription,
  resolveDiscussionListPageMetaTitle,
} from './discussionList.js'
export {
  buildDiscussionFilterLocation,
  getDiscussionListStartButtonStyle,
  isDiscussionFilterActive,
} from './discussionListNavigation.js'
export {
  getDiscussionListTrackingDiff,
  resolveDiscussionMarkAllReadPatch,
  resolveDiscussionReadStatePatch,
} from './discussionListRealtime.js'
export { resolveDiscussionNewReplyPatch } from './discussionListRealtimeUi.js'
export { shouldAppendRealtimePostImmediately } from './discussionPostStream.js'
export { buildDiscussionHeroColorStyle } from './discussionHeroStyle.js'
export { resolveDiscussionDetailMetaPayload } from './discussionDetailMeta.js'
export {
  buildDiscussionPath,
  normalizeDiscussion,
} from './discussionRuntime.js'
export { useStartDiscussionAction } from './startDiscussionRuntime.js'
