export type ExtensionId = string
export type ExtensionCallback = (...args: any[]) => any

export interface Extender {
  extend(app: any, extension?: { name?: string; id?: string }): void | Promise<void>
}

export interface ExtensionModule {
  extend?: Extender | Extender[] | Array<Extender | Extender[] | null | undefined>
}

export declare class ItemList<T = any> {
  isEmpty(): boolean
  has(key: string): boolean
  get(key: string): T | null
  getPriority(key: string): number
  add(key: string, content: T, priority?: number): this
  setContent(key: string, content: T): this
  setPriority(key: string, priority: number): this
  remove(key: string): this
  merge(otherList: ItemList<T>): this
  toArray(keepObject?: boolean): T[]
  toObject(): Record<string, T>
}

export declare function extend(target: any, methods: string | string[], callback: ExtensionCallback, options?: { extensionId?: string }): boolean
export declare function override(target: any, methods: string | string[], callback: ExtensionCallback, options?: { extensionId?: string }): boolean
export declare function resetPatches(extensionId?: string): void

export declare class Admin {
  constructor(context?: string)
  route(route: Record<string, any>): this
  page(page: Record<string, any>): this
  setting(setting: Record<string, any> | (() => any), priority?: number): this
  customSetting(setting: Record<string, any> | (() => any), priority?: number): this
  permission(permission: Record<string, any>, type?: string, priority?: number): this
  extend(app: any, extension?: { name?: string; id?: string }): void
}

export declare class AdminDashboard {
  constructor(context?: string)
  stat(definition: Record<string, any>): this
  action(definition: Record<string, any>): this
  actionMeta(definition: Record<string, any>): this
  alert(definition: Record<string, any>): this
  config(definition: Record<string, any>): this
  copy(definition: Record<string, any>): this
  queueMetric(definition: Record<string, any>): this
  statusBadge(definition: Record<string, any>): this
  statusItem(definition: Record<string, any>): this
  statusSummary(definition: Record<string, any>): this
  extend(app: any, extension?: { name?: string; id?: string }): void
}

export declare class AdminPage {
  constructor(pageKey?: string, context?: string)
  copy(definition: Record<string, any>): this
  config(definition: Record<string, any>): this
  actionMeta(definition: Record<string, any>): this
  noteTemplate(definition: Record<string, any>): this
  extend(app: any, extension?: { name?: string; id?: string }): void
}

export declare class Forum {
  constructor(context?: string)
  register(method: string, definition: Record<string, any>): this
  navItem(definition: Record<string, any>): this
  navSection(definition: Record<string, any>): this
  headerItem(definition: Record<string, any>): this
  discussionAction(definition: Record<string, any>): this
  discussionActionHandler(definition: Record<string, any>): this
  discussionBadge(definition: Record<string, any>): this
  discussionStateBadge(definition: Record<string, any>): this
  discussionReplyState(definition: Record<string, any>): this
  discussionReviewBanner(definition: Record<string, any>): this
  postAction(definition: Record<string, any>): this
  postActionHandler(definition: Record<string, any>): this
  postStateBadge(definition: Record<string, any>): this
  postReviewBanner(definition: Record<string, any>): this
  postFlagPanel(definition: Record<string, any>): this
  composerTool(definition: Record<string, any>): this
  composerNotice(definition: Record<string, any>): this
  composerMentionProvider(definition: Record<string, any>): this
  composerPreviewTransformer(definition: Record<string, any>): this
  notificationRenderer(definition: Record<string, any>): this
  emptyState(definition: Record<string, any>): this
  stateBlock(definition: Record<string, any>): this
  uiCopy(definition: Record<string, any>): this
  approvalNote(definition: Record<string, any>): this
  extend(app: any, extension?: { name?: string; id?: string }): void
}

export declare class Exports {
  constructor(namespace?: string)
  module(id: string, value: any): this
  chunk(id: string, modules?: Record<string, any>): this
  extend(app: any, extension?: { name?: string; id?: string }): void
}

export declare class Routes {
  add(name: string, path: string, component: any, options?: Record<string, any>): this
  helper(name: string, callback: (...args: any[]) => any): this
  extend(app: any): void
}

export declare class Notification {
  add(type: string, definitionOrComponent?: any): this
  extend(app: any): void
}

export declare class Search {
  filter(item: Record<string, any>): this
  gambit(modelType: string, gambit: Record<string, any>): this
  extend(app: any): void
}
