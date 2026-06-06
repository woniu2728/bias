export * from '../common/sdk'
export * from './runtimeSdk'

export declare function createForumExtensionApp(options?: Record<string, any>): any
export declare function applyExtensionDocumentPayload(payload: any): any
export declare function normalizeExtensionDocumentPayload(payload: any): any
export declare function computed(...args: any[]): any
export declare function reactive(...args: any[]): any
export declare function ref(...args: any[]): any
export declare function watch(...args: any[]): any
export declare function useRoute(...args: any[]): any
export declare function useRouter(...args: any[]): any
export declare const forumApi: any
export declare function getUiCopy(context?: Record<string, any>): any
export declare function getComposerAutocompleteProviders(context?: Record<string, any>): any[]
export declare function getDiscussionListContexts(context?: Record<string, any>): any[]
export declare function getDiscussionListHero(context?: Record<string, any>): any
export declare function getDiscussionListRequests(context?: Record<string, any>): any[]
export declare function getEmptyState(context?: Record<string, any>): any
export declare function getNotificationRenderers(context?: Record<string, any>): any[]
export declare function getSearchModalSections(context?: Record<string, any>): any[]
export declare function getStateBlock(context?: Record<string, any>): any
export declare function getComposerFields(context?: Record<string, any>): any[]
export declare function registerDiscussionListContext(definition: Record<string, any>): any
export declare function registerDiscussionListHero(definition: Record<string, any>): any
export declare function registerDiscussionListRequest(definition: Record<string, any>): any
export declare function registerEmptyState(definition: Record<string, any>): any
export declare function registerSearchModalSection(definition: Record<string, any>): any
export declare function registerForumRuntime(definition: Record<string, any>): any
export declare function registerComposerAutocompleteProvider(definition: Record<string, any>): any
export declare function registerComposerField(definition: Record<string, any>): any
export declare function registerComposerPayloadContributor(definition: Record<string, any>): any
export declare function registerComposerInitialState(definition: Record<string, any>): any
export declare function runComposerPayloadContributors(payload?: Record<string, any>, context?: Record<string, any>): Promise<any>
export declare function runComposerInitialStateContributors(initialState?: Record<string, any>, context?: Record<string, any>): Promise<any>
export declare function runForumRuntimeHook(name: string, context?: Record<string, any>): Promise<any[]>
export declare function buildDiscussionHeroColorStyle(color?: any): Record<string, string>
export declare const DiscussionListSidebarStartButton: any
export declare const DiscussionEventPostBase: any
export declare const ForumHeroPanel: any
export declare const ForumInlineMessage: any
export declare const ForumPageWithSidebar: any
export declare const ForumPagination: any
export declare const ForumPrimaryNav: any
export declare const ForumSearchFilterNav: any
export declare const ForumStateBlock: any
export declare function usePaginatedListState(options?: Record<string, any>): any
export declare function useRouteListState(options?: Record<string, any>): any
export declare function useRoutePagination(options?: Record<string, any>): any
export declare function useStartDiscussionAction(options?: Record<string, any>): any
export declare function defineStore(...args: any[]): any
export declare function formatRelativeTime(value?: any): any
export declare const FORUM_REALTIME_REFRESH_EVENT_TYPES: Set<string>
export declare function getTrackedDiscussionIdsFromDiscussionItems(items?: any[]): number[]
export declare function getTrackedDiscussionIdsFromPostItems(items?: any[]): number[]
export declare function hasTrackedDiscussionId(targetIds?: any[], discussionId?: any): boolean
export declare function mergeForumEventPayload(resourceStore?: any, event?: any): void
export declare function shouldRefreshForumEvent(eventType?: any): boolean
export declare function renderTwemojiHtml(html?: any): string
export declare function renderTwemojiText(text?: any): string
export declare function setTwemojiBaseUrl(url?: any): void
export declare function setTwemojiEnabled(value?: any): void
export declare function getTextareaCaretCoordinates(textarea?: any, position?: any): any
export declare function buildDiscussionPath(value?: any): string
export declare function buildUserPath(value?: any): string
export declare function getUserAvatarColor(user?: any): any
export declare function getUserDisplayName(user?: any): any
export declare function getUserInitial(user?: any): any
export declare function normalizeDiscussion(discussion?: any): any
export declare function normalizePost(post?: any): any
export declare function normalizeUser(user?: any): any
export declare function unwrapList(payload?: any): any[]
export declare function useAuthStore(...args: any[]): any
export declare function useComposerStore(...args: any[]): any
export declare function useForumStore(...args: any[]): any
export declare function useForumRealtimeStore(...args: any[]): any
export declare function useModalStore(...args: any[]): any
export declare function registerResourceNormalizer(type: string, normalizer: (...args: any[]) => any): any
export declare function useResourceStore(...args: any[]): any
