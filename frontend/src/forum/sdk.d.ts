export { ForumExtender, extendForum } from '../common/sdk'

export declare function createForumExtensionApp(options?: Record<string, any>): any
export declare function applyExtensionDocumentPayload(payload: any): any
export declare function normalizeExtensionDocumentPayload(payload: any): any
export declare function getUiCopy(context?: Record<string, any>): any
export declare function getComposerAutocompleteProviders(context?: Record<string, any>): any[]
export declare function getComposerHosts(context?: Record<string, any>): any[]
export declare function getComposerUploadHandler(context?: Record<string, any>): any
export declare function getEmptyState(context?: Record<string, any>): any
export declare function getFeedbackNote(context?: Record<string, any>): any
export declare function getForumNavItems(context?: Record<string, any>): any[]
export declare function getForumSidebarSections(context?: Record<string, any>): any[]
export declare function getHeroMetaItems(context?: Record<string, any>): any[]
export declare function getPageState(context?: Record<string, any>): any
export declare function getStateBlock(context?: Record<string, any>): any
export declare function getComposerFields(context?: Record<string, any>): any[]
export declare function registerEmptyState(definition: Record<string, any>): any
export declare function registerForumRuntime(definition: Record<string, any>): any
export declare function registerComposerAutocompleteProvider(definition: Record<string, any>): any
export declare function registerComposerHost(definition: Record<string, any>): any
export declare function registerComposerUploadHandler(definition: Record<string, any>): any
export declare function registerComposerField(definition: Record<string, any>): any
export declare function registerComposerPayloadContributor(definition: Record<string, any>): any
export declare function registerComposerInitialState(definition: Record<string, any>): any
export declare function runComposerPayloadContributors(payload?: Record<string, any>, context?: Record<string, any>): Promise<any>
export declare function runComposerInitialStateContributors(initialState?: Record<string, any>, context?: Record<string, any>): Promise<any>
export declare function runForumRuntimeHook(name: string, context?: Record<string, any>): Promise<any[]>
export declare const ForumHeroPanel: any
export declare const ForumInlineMessage: any
export declare const ForumPageWithSidebar: any
export declare const ForumPagination: any
export declare const ForumPrimaryNav: any
export declare const ForumSearchFilterNav: any
export declare const ForumStateBadge: any
export declare const ForumStateBlock: any
export declare const ComposerActionBar: any
export declare const ComposerAutocompleteOutlet: any
export declare const ComposerHeaderBar: any
export declare const ComposerNoticeStack: any
export declare const ComposerPreviewPanel: any
export declare const ComposerStatusBar: any
export declare function useComposerRuntime(options?: Record<string, any>): any
export declare function getTextareaCaretCoordinates(textarea?: any, position?: any): any
export declare function useComposerStore(...args: any[]): any
export declare function useForumStore(...args: any[]): any
export declare function useForumUiStore(...args: any[]): any
