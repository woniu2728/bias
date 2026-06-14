export type ExtensionId = string
export type ExtensionCallback = (...args: any[]) => any
export type ExtensionPatchTarget = any

export interface Extender {
  extend(app: any, extension?: { name?: string; id?: string }): void | Promise<void>
}

export interface ExtensionModule {
  extend?: Extender | ExtensionCallback | Extender[] | Array<Extender | ExtensionCallback | Extender[] | null | undefined>
  default?: Extender | ExtensionCallback | Extender[] | ExtensionModule | Array<Extender | ExtensionCallback | Extender[] | null | undefined>
}

export interface ExtensionInitializer {
  extensionId: string
  callback: (app?: any) => any
  priority: number
  order: number
}

export interface ExtensionInitializers {
  add(extensionId: string, callback: (app?: any) => any, priority?: number): boolean
  clear(extensionId?: string): void
  remove(extensionId?: string): this
  has(extensionId?: string): boolean
  get(extensionId?: string): ((app?: any) => any) | null
  list(): ExtensionInitializer[]
  toItemList(): ItemList<(app?: any) => any>
  toArray(options?: boolean | Record<string, any>): any[]
  toObject(): Record<string, any>
  run(app?: any, options?: { onError?: (error: any, extensionId: string) => void }): Promise<Array<{ extensionId: string; error: any }>>
  runWithAppResolver(resolveApp?: (extensionId: string) => any, options?: { onError?: (error: any, extensionId: string) => void }): Promise<Array<{ extensionId: string; error: any }>>
}

export interface ExtensionPatcher {
  extend(target: ExtensionPatchTarget | string, methods: string | string[], callback: ExtensionCallback, options?: { extensionId?: string }): boolean
  override(target: ExtensionPatchTarget | string, methods: string | string[], callback: ExtensionCallback, options?: { extensionId?: string }): boolean
  reset(extensionId?: string): void
}

export declare class ExportRegistry {
  constructor()
  add(namespace: string, id: string, module: any): any
  register(namespace: string, id: string, module: any): any
  registerModule(path: string, module: any): any
  unregister(namespace: string, id: string): boolean
  unregisterModule(path: string): boolean
  registerChunk(namespace: string, chunkId: string, modules?: Record<string, any>, options?: Record<string, any>): any
  registerViteOutput(namespace: string, frontend: string, output?: Record<string, any>, options?: Record<string, any>): any[]
  get(namespace: string, id: string): any
  getModule(path: string): any
  onLoad(namespace: string, id: string, handler: (module: any) => void): boolean
  onLoadPath(path: string, handler: (module: any) => void): boolean
  asyncModuleImport(path: string): Promise<any>
  clear(): void
  clearNamespace(namespace: string): boolean
}

export interface RuntimeApplication {
  kind: string
  api?: any
  router?: any
  store?: any
  resourceStore?: any
  forumStore?: any
  initializers: ExtensionInitializers
  extensions: Record<string, any>
  extensionRegistry: any
  exportRegistry: ExportRegistry
  items: any
  cache: Record<string, any>
  session: any
  alerts: any
  translator: any
  load(payload?: Record<string, any>): this
  booting(callback: (app: this) => any): void
  booted(callback: (app: this) => any): void
  beforeMount(callback: (app: this) => any): void
  runBeforeMount(): Promise<this>
  bootExtensions(extensions?: Record<string, ExtensionModule> | ExtensionModule[], options?: Record<string, any>): Promise<this>
  boot(callback?: (app: this) => any): Promise<this>
  route(name: string | Record<string, any>, params?: Record<string, any>): string
  request(options?: string | Record<string, any>): Promise<any>
  handleError(error: any, operation?: string): any
}

export declare class ItemList<T = any> {
  constructor(items?: Record<string, { content: T; priority?: number }>)
  isEmpty(): boolean
  has(key: string): boolean
  get(key: string): T | undefined
  getPriority(key: string): number
  add(key: string, content: T, priority?: number): this
  setContent(key: string, content: T): this
  setPriority(key: string, priority: number): this
  remove(key: string): this
  merge(otherList: ItemList<T>): this
  toArray(options?: boolean | { keepPrimitives?: boolean; context?: any; resolve?: (content: T, context: any, key: string) => any }): T[]
  toObject(): Record<string, { content: T; itemName: string; priority: number }>
}

export declare function createRuntimeApplication(options?: Record<string, any>): RuntimeApplication
export declare function computed(...args: any[]): any
export declare function nextTick(...args: any[]): any
export declare function onBeforeUnmount(...args: any[]): any
export declare function onMounted(...args: any[]): any
export declare function reactive(...args: any[]): any
export declare function ref(...args: any[]): any
export declare function toRef(...args: any[]): any
export declare function watch(...args: any[]): any
export declare function useRoute(...args: any[]): any
export declare function useRouter(...args: any[]): any
export declare function createPinia(...args: any[]): any
export declare function defineStore(...args: any[]): any
export declare function setActivePinia(...args: any[]): any
export declare const api: any
export declare const coreApi: any
export declare function normalizeExtensionExtenders(module?: ExtensionModule | Extender | ExtensionCallback | Array<any>): Extender[]
export declare function hasExtensionExtenders(module?: ExtensionModule | Extender | ExtensionCallback | Array<any>): boolean
export declare function createExtensionAppApi(options?: Record<string, any>): any
export declare function createExtensionInitializers(): ExtensionInitializers
export declare function createExtensionPatcher(): ExtensionPatcher
export declare function getCurrentExtensionId(): string
export declare function runWithExtensionScope<T = any>(extensionId: string, callback: () => T): T
export declare function extend(target: ExtensionPatchTarget | string, methods: string | string[], callback: ExtensionCallback, options?: { extensionId?: string }): boolean
export declare function override(target: ExtensionPatchTarget | string, methods: string | string[], callback: ExtensionCallback, options?: { extensionId?: string }): boolean
export declare function resetPatches(extensionId?: string): void
export declare function resetExtensionPatches(extensionId?: string): void
export declare function onLazyModuleLoad(key: string, callback: (module: any) => void): boolean
export declare function registerLazyExtensionModule(key: string, module: any, options?: { extensionId?: string }): boolean
export declare function unregisterLazyExtensionModules(extensionId?: string): void
export declare function registerLoadedExtensionModule(extensionId: string, module: any, options?: Record<string, any>): any
export declare function unregisterLoadedExtensionModule(extensionId?: string, options?: Record<string, any>): void
export declare function getExtensionRuntimeErrors(): any[]
export declare function clearExtensionRuntimeErrors(extensionId?: string): void
export declare function handleExtensionRuntimeError(error: any, extensionId?: string, operation?: string): void
export declare function normalizeExtensionFrontendEntry(entry?: string): string
export declare function withRuntimeApplication<T = any>(extension: T, application: any): T
export declare function registerExtensionFrontendOutput(application: any, extensionId: string, frontend: string, output?: Record<string, any>, options?: { baseUrl?: string }): any[]
export declare function resolveExtensionRouteComponent(componentKey: string, extension: Record<string, any>, options?: Record<string, any>): any
export declare function resolveExtensionRouteComponentKeys(componentKey: string, extension?: Record<string, any>, options?: Record<string, any>): string[]
export declare function importRouteComponentFromExportRegistry(registry: ExportRegistry, candidates?: string[]): Promise<any>
export declare function resolveDefaultComponent(module: any): any
export declare function ensureExportRegistry(target?: any): ExportRegistry
export declare function createExtensionRegistry(): any
export declare function createListItemRegistry(defaults?: Record<string, any>): any
export declare function createSingleItemRegistry(defaults?: Record<string, any>): any
export declare function upsertByKey(target: any[], key: string, value: any): any
export declare function orderedRegisteredItems(target: any[]): any[]
export declare function normalizeRegisteredItem(item: Record<string, any>, defaults?: Record<string, any>): any
export declare function clearRegistryExtensions(targets: any[][], extensionId?: string): void
export declare function getFrontendRegistrySlot(name: string): any[]
export declare function getFrontendRegistrySlots(names?: string[]): any[][]
export declare function isRegisteredItemEnabled(item: Record<string, any>, context?: Record<string, any>): boolean
export declare function resolveRegisteredItem(item: Record<string, any>, context?: Record<string, any>): any
export declare function getFirstSurfaceAwareItem(target: any[], context?: Record<string, any>): any
export declare function itemContentValue(content: any): any
export declare function formatRelativeTime(value?: any): any
export declare function formatMonth(value?: any): any
export declare function unwrapList(payload?: any): any[]
export declare function usePaginatedListState(options?: Record<string, any>): any
export declare function useRequestedPaginatedListState(options?: Record<string, any>): any
export declare function useRouteListState(options?: Record<string, any>): any
export declare function useRoutePagination(options?: Record<string, any>): any
export declare function useModalStore(...args: any[]): any
export declare function useResourceStore(...args: any[]): any

export declare class ResourceModel {
  constructor(data?: Record<string, any>, store?: any)
  data: Record<string, any>
  store: any
  exists: boolean
  id(): any
  type(): any
  attribute(name: string): any
  pushData(data?: Record<string, any>): this
  pushAttributes(attributes?: Record<string, any>): this
  copyData(): Record<string, any>
  rawRelationship(name: string): any
  apiEndpoint(): string
  save(attributes?: Record<string, any>, options?: Record<string, any>): Promise<any>
  delete(data?: Record<string, any>, options?: Record<string, any>): Promise<void>
  static attribute(name: string, transform?: ((value: any) => any) | null): (...args: any[]) => any
  static hasOne(name: string): (...args: any[]) => any
  static hasMany(name: string): (...args: any[]) => any
  static transformDate(value: any): any
  static getIdentifier(model: any): any
}

export declare class Store {
  add(type: string, model: any): this
  extend(app: any): void
}

export declare class ResourceNormalizer {
  add(type: string, normalizer: (...args: any[]) => any): this
  extend(app: any, extension?: { name?: string; id?: string }): void
}

export declare class Model {
  constructor(model: any)
  attribute(name: string, transform?: ((value: any) => any) | null): this
  hasOne(name: string): this
  hasMany(name: string): this
  extend(app?: any): void
}

export declare class AdminExtender {
  constructor(context?: string)
  route(route: Record<string, any>): this
  page(page: Record<string, any>): this
  setting(setting: Record<string, any> | (() => any), priority?: number): this
  customSetting(setting: Record<string, any> | (() => any), priority?: number): this
  replaceSetting(setting: string, replacement: (setting: Record<string, any>) => Record<string, any>): this
  setSettingPriority(setting: string, priority?: number): this
  removeSetting(setting: string): this
  permission(permission: Record<string, any>, type?: string, priority?: number): this
  permissionScope(definition: Record<string, any>): this
  replacePermission(permission: string, replacement: (permission: Record<string, any>) => Record<string, any>, type?: string): this
  setPermissionPriority(permission: string, type?: string, priority?: number): this
  removePermission(permission: string, type?: string): this
  generalIndexItems(type: string, items: Record<string, any>[] | (() => Record<string, any>[])): this
  dashboardStat(definition: Record<string, any>): this
  dashboardAction(definition: Record<string, any>): this
  dashboardActionMeta(definition: Record<string, any>): this
  dashboardAlert(definition: Record<string, any>): this
  dashboardConfig(definition: Record<string, any>): this
  dashboardCopy(definition: Record<string, any>): this
  dashboardQueueMetric(definition: Record<string, any>): this
  dashboardStatusBadge(definition: Record<string, any>): this
  dashboardStatusItem(definition: Record<string, any>): this
  dashboardStatusSummary(definition: Record<string, any>): this
  pageCopy(pageKey: string, definition: Record<string, any>): this
  pageConfig(pageKey: string, definition: Record<string, any>): this
  pageAction(pageKey: string, definition: Record<string, any>): this
  pageActionMeta(pageKey: string, definition: Record<string, any>): this
  pageNoteTemplate(pageKey: string, definition: Record<string, any>): this
  extend(app: any, extension?: { name?: string; id?: string }): void
}

export declare function extendAdmin(callback: (admin: AdminExtender) => AdminExtender | void): AdminExtender
export declare function extendAdmin(context: string, callback?: (admin: AdminExtender) => AdminExtender | void): AdminExtender

export declare class ForumExtender {
  constructor(context?: string)
  register(method: string, definition: Record<string, any>): this
  navItem(definition: Record<string, any>): this
  navSection(definition: Record<string, any>): this
  sidebarSection(definition: Record<string, any>): this
  profilePanel(definition: Record<string, any>): this
  authChallengeProvider(definition: Record<string, any>): this
  searchSource(definition: Record<string, any>): this
  heroMeta(definition: Record<string, any>): this
  discussionListContext(definition: Record<string, any>): this
  discussionListHero(definition: Record<string, any>): this
  discussionListRequest(definition: Record<string, any>): this
  headerItem(definition: Record<string, any>): this
  discussionAction(definition: Record<string, any>): this
  discussionActionHandler(definition: Record<string, any>): this
  discussionBadge(definition: Record<string, any>): this
  discussionStateBadge(definition: Record<string, any>): this
  discussionPresentation(definition: Record<string, any>): this
  discussionReplyState(definition: Record<string, any>): this
  discussionReviewBanner(definition: Record<string, any>): this
  postType(type: string, definitionOrComponent?: any): this
  postAction(definition: Record<string, any>): this
  postActionHandler(definition: Record<string, any>): this
  postStateBadge(definition: Record<string, any>): this
  postReviewBanner(definition: Record<string, any>): this
  postFlagPanel(definition: Record<string, any>): this
  composerTool(definition: Record<string, any>): this
  composerField(definition: Record<string, any>): this
  composerNotice(definition: Record<string, any>): this
  composerSubmitGuard(definition: Record<string, any>): this
  composerPayloadContributor(definition: Record<string, any>): this
  composerInitialState(definition: Record<string, any>): this
  composerSecondaryAction(definition: Record<string, any>): this
  composerStatusItem(definition: Record<string, any>): this
  composerDraftMeta(definition: Record<string, any>): this
  composerSubmitSuccess(definition: Record<string, any>): this
  composerAutocompleteProvider(definition: Record<string, any>): this
  composerPreviewTransformer(definition: Record<string, any>): this
  composerHost(definition: Record<string, any>): this
  composerUploadHandler(definition: Record<string, any>): this
  notificationRenderer(definition: Record<string, any>): this
  searchModalProvider(definition: Record<string, any>): this
  searchModalSection(definition: Record<string, any>): this
  userBadge(definition: Record<string, any>): this
  emptyState(definition: Record<string, any>): this
  pageState(definition: Record<string, any>): this
  stateBlock(definition: Record<string, any>): this
  uiCopy(definition: Record<string, any>): this
  feedbackNote(definition: Record<string, any>): this
  realtimeEvent(definition: Record<string, any>): this
  runtime(definition: Record<string, any>): this
  extend(app: any, extension?: { name?: string; id?: string }): void
}

export declare function extendForum(callback: (forum: ForumExtender) => ForumExtender | void): ForumExtender
export declare function extendForum(context: string, callback?: (forum: ForumExtender) => ForumExtender | void): ForumExtender

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

export declare class PostTypes {
  add(type: string, definitionOrComponent?: any): this
  extend(app: any, extension?: { name?: string; id?: string }): void
}

export declare class Search {
  filter(item: Record<string, any>): this
  gambit(modelType: string, gambit: Record<string, any>): this
  extend(app: any): void
}

export declare class ThemeMode {
  add(mode: string, label?: string): this
  extend(app: any): void
}

export declare const ModelExtender: typeof Model
export declare const ResourceModelExtender: typeof Model
export declare const ResourceNormalizerExtender: typeof ResourceNormalizer
export declare const StoreExtender: typeof Store
export declare const NotificationExtender: typeof Notification
export declare const PostTypesExtender: typeof PostTypes
export declare const RoutesExtender: typeof Routes
export declare const SearchExtender: typeof Search
export declare const ThemeModeExtender: typeof ThemeMode
export declare const ExportsExtender: typeof Exports
export declare const ModerationActionModal: any
