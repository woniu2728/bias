export class NotificationExtender {
  constructor() {
    this.items = []
  }

  add(type, definitionOrComponent = {}) {
    const normalizedType = normalizeKey(type)
    if (normalizedType) {
      this.items.push(normalizeComponentDefinition(normalizedType, definitionOrComponent))
    }
    return this
  }

  extend(app) {
    const targetApp = resolveApplication(app)
    const registry = resolveRegistry(app)
    for (const definition of this.items) {
      if (definition.component) {
        targetApp.notificationComponents ||= Object.create(null)
        targetApp.notificationComponents[definition.type] = definition.component
      }
      if (typeof registry?.registerNotificationType === 'function') {
        registry.registerNotificationType(definition)
      } else if (typeof registry?.registerNotificationRenderer === 'function') {
        registry.registerNotificationRenderer({
          ...definition,
          key: definition.key || definition.type,
        })
      }
    }
  }
}

export class PostTypesExtender {
  constructor() {
    this.items = []
  }

  add(type, definitionOrComponent = {}) {
    const normalizedType = normalizeKey(type)
    if (normalizedType) {
      this.items.push(normalizeComponentDefinition(normalizedType, definitionOrComponent))
    }
    return this
  }

  extend(app) {
    const targetApp = resolveApplication(app)
    const registry = resolveRegistry(app)
    for (const definition of this.items) {
      if (definition.component) {
        targetApp.postComponents ||= Object.create(null)
        targetApp.postComponents[definition.type] = definition.component
      }
      if (typeof registry?.registerPostType === 'function') {
        registry.registerPostType(definition)
      }
    }
  }
}

export class SearchExtender {
  constructor() {
    this.filters = []
    this.gambits = []
  }

  filter(item) {
    if (item && typeof item === 'object') {
      this.filters.push({ ...item })
    }
    return this
  }

  gambit(modelType, gambit) {
    const target = normalizeSearchTarget(modelType)
    if (target && gambit) {
      this.gambits.push({ target, gambit })
    }
    return this
  }

  extend(app) {
    const targetApp = resolveApplication(app)
    const registry = resolveRegistry(app)
    targetApp.search ||= { gambits: { gambits: Object.create(null) } }
    targetApp.search.gambits ||= { gambits: Object.create(null) }
    targetApp.search.gambits.gambits ||= Object.create(null)

    for (const item of this.gambits) {
      targetApp.search.gambits.gambits[item.target] ||= []
      targetApp.search.gambits.gambits[item.target].push(item.gambit)
      const filter = normalizeGambitFilter(item)
      if (filter && typeof registry?.registerSearchFilter === 'function') {
        registry.registerSearchFilter(filter)
      }
    }

    if (typeof registry?.registerSearchFilter !== 'function') {
      return
    }
    for (const item of this.filters) {
      registry.registerSearchFilter(item)
    }
  }
}

export class RoutesExtender {
  constructor() {
    this.items = []
    this.helpers = []
  }

  add(name, path, component, options = {}) {
    const normalizedName = normalizeKey(name)
    if (normalizedName && path && component) {
      this.items.push({
        name: normalizedName,
        path: String(path),
        component,
        ...(options || {}),
      })
    }
    return this
  }

  helper(name, callback) {
    const normalizedName = normalizeKey(name)
    if (normalizedName && typeof callback === 'function') {
      this.helpers.push({ name: normalizedName, callback })
    }
    return this
  }

  extend(app) {
    const targetApp = resolveApplication(app)
    const router = app?.router || targetApp?.router
    targetApp.routes ||= { definitions: Object.create(null), helpers: Object.create(null) }
    targetApp.routes.definitions ||= Object.create(null)
    targetApp.routes.helpers ||= Object.create(null)
    targetApp.routeHelpers ||= Object.create(null)

    for (const route of this.items) {
      targetApp.routes.definitions[route.name] = route
      if (router && typeof router.addRoute === 'function') {
        if (typeof router.hasRoute === 'function' && router.hasRoute(route.name)) {
          continue
        }
        router.addRoute(route)
      }
    }

    for (const helper of this.helpers) {
      const bound = (...args) => helper.callback(targetApp, ...args)
      targetApp.routes.helpers[helper.name] = bound
      targetApp.routeHelpers[helper.name] = bound
      if (typeof targetApp.route === 'function') {
        targetApp.route[helper.name] = bound
      }
    }
  }
}

export class ThemeModeExtender {
  constructor() {
    this.items = []
  }

  add(mode, label = '') {
    const normalizedMode = normalizeKey(mode)
    if (normalizedMode) {
      this.items.push({
        id: normalizedMode,
        mode: normalizedMode,
        label: String(label || normalizedMode),
      })
    }
    return this
  }

  extend(app) {
    const targetApp = resolveApplication(app)
    const registry = resolveRegistry(app)
    targetApp.themeModes ||= []
    const existing = new Set(targetApp.themeModes.map(item => item.id || item.mode))
    for (const item of this.items) {
      if (!existing.has(item.id)) {
        targetApp.themeModes.push(item)
        existing.add(item.id)
      }
      if (typeof registry?.registerThemeMode === 'function') {
        registry.registerThemeMode(item)
      }
    }
  }
}

export class ForumExtender {
  constructor(context = '') {
    this.context = normalizeKey(context)
    this.items = []
  }

  register(method, definition) {
    const normalizedMethod = normalizeKey(method)
    if (normalizedMethod && definition) {
      this.items.push({ method: normalizedMethod, definition })
    }
    return this
  }

  navItem(definition) { return this.register('registerForumNavItem', definition) }
  navSection(definition) { return this.register('registerForumNavSection', definition) }
  headerItem(definition) { return this.register('registerHeaderItem', definition) }
  discussionAction(definition) { return this.register('registerDiscussionAction', definition) }
  discussionActionHandler(definition) { return this.register('registerDiscussionActionHandler', definition) }
  discussionBadge(definition) { return this.register('registerDiscussionBadge', definition) }
  discussionStateBadge(definition) { return this.register('registerDiscussionStateBadge', definition) }
  discussionReplyState(definition) { return this.register('registerDiscussionReplyState', definition) }
  discussionReviewBanner(definition) { return this.register('registerDiscussionReviewBanner', definition) }
  postAction(definition) { return this.register('registerPostAction', definition) }
  postActionHandler(definition) { return this.register('registerPostActionHandler', definition) }
  postStateBadge(definition) { return this.register('registerPostStateBadge', definition) }
  postReviewBanner(definition) { return this.register('registerPostReviewBanner', definition) }
  postFlagPanel(definition) { return this.register('registerPostFlagPanel', definition) }
  composerTool(definition) { return this.register('registerComposerTool', definition) }
  composerNotice(definition) { return this.register('registerComposerNotice', definition) }
  composerMentionProvider(definition) { return this.register('registerComposerMentionProvider', definition) }
  composerPreviewTransformer(definition) { return this.register('registerComposerPreviewTransformer', definition) }
  notificationRenderer(definition) { return this.register('registerNotificationRenderer', definition) }
  emptyState(definition) { return this.register('registerEmptyState', definition) }
  stateBlock(definition) { return this.register('registerStateBlock', definition) }
  uiCopy(definition) { return this.register('registerUiCopy', definition) }
  approvalNote(definition) { return this.register('registerApprovalNote', definition) }

  extend(app, extension = {}) {
    const registry = resolveRegistry(app)
    const extensionId = normalizeKey(extension.name || app?.extension?.id || app?.application?.extension?.id || this.context)
    const scopedRegistry = typeof registry?.for === 'function'
      ? (registry.for(this.context || extensionId) || registry)
      : registry
    for (const item of this.items) {
      const register = scopedRegistry?.[item.method]
      if (typeof register !== 'function') {
        continue
      }
      register(withExtensionId(resolveExtenderDefinition(item.definition), extensionId))
    }
  }
}

export class AdminExtender {
  constructor(context = '') {
    this.context = normalizeKey(context)
    this.routes = []
    this.settings = []
    this.settingReplacements = []
    this.settingPriorityChanges = []
    this.settingRemovals = []
    this.permissions = []
    this.permissionReplacements = []
    this.permissionPriorityChanges = []
    this.permissionRemovals = []
    this.generalIndexes = []
  }

  route(route) {
    if (route && typeof route === 'object' && route.path) {
      this.routes.push({ ...route })
    }
    return this
  }

  page(page) {
    return this.route(page)
  }

  setting(setting, priority = 0) {
    if (setting) {
      this.settings.push({ setting, priority, custom: false })
    }
    return this
  }

  customSetting(setting, priority = 0) {
    if (setting) {
      this.settings.push({ setting, priority, custom: true })
    }
    return this
  }

  replaceSetting(setting, replacement) {
    const key = normalizeKey(setting)
    if (key && typeof replacement === 'function') {
      this.settingReplacements.push({ setting: key, replacement })
    }
    return this
  }

  setSettingPriority(setting, priority = 0) {
    const key = normalizeKey(setting)
    if (key) {
      this.settingPriorityChanges.push({ setting: key, priority: Number(priority) || 0 })
    }
    return this
  }

  removeSetting(setting) {
    const key = normalizeKey(setting)
    if (key) {
      this.settingRemovals.push(key)
    }
    return this
  }

  permission(permission, type = 'moderate', priority = 0) {
    if (permission) {
      this.permissions.push({ permission, type: normalizeKey(type) || 'moderate', priority })
    }
    return this
  }

  replacePermission(permission, replacement, type = 'moderate') {
    const key = normalizeKey(permission)
    if (key && typeof replacement === 'function') {
      this.permissionReplacements.push({ permission: key, replacement, type: normalizeKey(type) || 'moderate' })
    }
    return this
  }

  setPermissionPriority(permission, type = 'moderate', priority = 0) {
    const key = normalizeKey(permission)
    if (key) {
      this.permissionPriorityChanges.push({ permission: key, type: normalizeKey(type) || 'moderate', priority: Number(priority) || 0 })
    }
    return this
  }

  removePermission(permission, type = 'moderate') {
    const key = normalizeKey(permission)
    if (key) {
      this.permissionRemovals.push({ permission: key, type: normalizeKey(type) || 'moderate' })
    }
    return this
  }

  generalIndexItems(type, items) {
    const normalizedType = normalizeKey(type)
    if (normalizedType && items) {
      this.generalIndexes.push({ type: normalizedType, items })
    }
    return this
  }

  extend(app, extension = {}) {
    const targetApp = resolveApplication(app)
    const registry = resolveRegistry(app)
    const router = app?.router || targetApp?.router
    const extensionId = normalizeKey(extension.name || app?.extension?.id || targetApp?.extension?.id || this.context)

    for (const route of this.routes) {
      const normalizedRoute = {
        navSection: 'feature',
        navOrder: 100,
        showInNavigation: true,
        ...route,
        ...(extensionId ? { extensionId, extension_id: extensionId } : {}),
      }
      if (typeof registry?.registerAdminRoute === 'function') {
        registry.registerAdminRoute(normalizedRoute)
      }
      if (router && typeof router.addRoute === 'function') {
        if (typeof router.hasRoute === 'function' && router.hasRoute(normalizedRoute.name)) {
          continue
        }
        router.addRoute(normalizedRoute)
      }
    }

    const applyAdminRegistry = () => {
      const context = this.context || extensionId
      registry?.for?.(context)

      for (const route of this.routes) {
        const normalizedRoute = {
          navSection: 'feature',
          navOrder: 100,
          showInNavigation: true,
          ...route,
          ...(extensionId ? { extensionId, extension_id: extensionId } : {}),
        }
        if (typeof registry?.registerPage === 'function') {
          registry.registerPage(normalizedRoute)
        }
      }

      for (const item of this.settings) {
        const setting = resolveExtenderDefinition(item.setting)
        if (!setting) continue
        if (item.custom && typeof registry?.registerCustomSetting === 'function') {
          registry.registerCustomSetting(setting, item.priority)
        } else if (typeof registry?.registerSetting === 'function') {
          registry.registerSetting(setting, item.priority)
        }
      }

      for (const item of this.settingReplacements) {
        registry?.setSetting?.(item.setting, item.replacement)
      }
      for (const item of this.settingPriorityChanges) {
        registry?.setSettingPriority?.(item.setting, item.priority)
      }
      for (const setting of this.settingRemovals) {
        registry?.removeSetting?.(setting)
      }

      for (const item of this.permissions) {
        const permission = resolveExtenderDefinition(item.permission)
        if (permission && typeof registry?.registerPermission === 'function') {
          registry.registerPermission(permission, item.type, item.priority)
        }
      }
      for (const item of this.permissionReplacements) {
        registry?.setPermission?.(item.permission, item.replacement, item.type)
      }
      for (const item of this.permissionPriorityChanges) {
        registry?.setPermissionPriority?.(item.permission, item.type, item.priority)
      }
      for (const item of this.permissionRemovals) {
        registry?.removePermission?.(item.permission, item.type)
      }

      const generalIndex = targetApp?.generalIndex || app?.generalIndex || registry?.generalIndex
      if (context && typeof generalIndex?.for === 'function') {
        generalIndex.for(context)
      }
      for (const item of this.generalIndexes) {
        const values = resolveExtenderDefinition(item.items) || []
        if (typeof generalIndex?.add === 'function') {
          generalIndex.add(item.type, values)
        } else if (typeof registry?.registerGeneralIndexItems === 'function') {
          registry.registerGeneralIndexItems(item.type, values)
        }
      }
    }

    if (typeof targetApp?.beforeMount === 'function') {
      targetApp.beforeMount(applyAdminRegistry)
    } else {
      applyAdminRegistry()
    }
  }
}

export class AdminDashboardExtender {
  constructor(context = '') {
    this.context = normalizeKey(context)
    this.items = []
  }

  register(method, definition) {
    const normalizedMethod = normalizeKey(method)
    if (normalizedMethod && definition) {
      this.items.push({ method: normalizedMethod, definition })
    }
    return this
  }

  stat(definition) { return this.register('registerAdminDashboardStat', definition) }
  action(definition) { return this.register('registerAdminDashboardAction', definition) }
  actionMeta(definition) { return this.register('registerAdminDashboardActionMeta', definition) }
  alert(definition) { return this.register('registerAdminDashboardAlert', definition) }
  config(definition) { return this.register('registerAdminDashboardConfig', definition) }
  copy(definition) { return this.register('registerAdminDashboardCopy', definition) }
  queueMetric(definition) { return this.register('registerAdminDashboardQueueMetric', definition) }
  statusBadge(definition) { return this.register('registerAdminDashboardStatusBadge', definition) }
  statusItem(definition) { return this.register('registerAdminDashboardStatusItem', definition) }
  statusSummary(definition) { return this.register('registerAdminDashboardStatusSummary', definition) }

  extend(app, extension = {}) {
    const registry = resolveRegistry(app)
    const extensionId = normalizeKey(extension.name || app?.extension?.id || app?.application?.extension?.id || this.context)
    const scopedRegistry = typeof registry?.for === 'function'
      ? (registry.for(this.context || extensionId) || registry)
      : registry
    for (const item of this.items) {
      const register = scopedRegistry?.[item.method]
      if (typeof register === 'function') {
        register(withExtensionId(resolveExtenderDefinition(item.definition), extensionId))
      }
    }
  }
}

export class AdminPageExtender {
  constructor(pageKey = '', context = '') {
    this.pageKey = normalizeKey(pageKey)
    this.context = normalizeKey(context)
    this.items = []
  }

  register(method, definition) {
    const normalizedMethod = normalizeKey(method)
    if (normalizedMethod && definition) {
      this.items.push({ method: normalizedMethod, definition })
    }
    return this
  }

  copy(definition) { return this.register('registerAdminPageCopy', definition) }
  config(definition) { return this.register('registerAdminPageConfig', definition) }
  actionMeta(definition) { return this.register('registerAdminPageActionMeta', definition) }
  noteTemplate(definition) { return this.register('registerAdminPageNoteTemplate', definition) }

  extend(app, extension = {}) {
    const registry = resolveRegistry(app)
    const pageKey = this.pageKey
    if (!pageKey || !registry) {
      return
    }
    const extensionId = normalizeKey(extension.name || app?.extension?.id || app?.application?.extension?.id || this.context)
    for (const item of this.items) {
      const register = registry?.[item.method]
      if (typeof register === 'function') {
        register(pageKey, withExtensionId(resolveExtenderDefinition(item.definition), extensionId))
      }
    }
  }
}

export class ExportsExtender {
  constructor(namespace = '') {
    this.namespace = normalizeKey(namespace)
    this.modules = []
    this.chunks = []
  }

  module(id, value) {
    const normalizedId = normalizeKey(id)
    if (normalizedId && value != null) {
      this.modules.push({ id: normalizedId, value })
    }
    return this
  }

  chunk(id, modules = {}) {
    const normalizedId = normalizeKey(id)
    if (normalizedId && modules && typeof modules === 'object') {
      this.chunks.push({ id: normalizedId, modules })
    }
    return this
  }

  extend(app, extension = {}) {
    const targetApp = resolveApplication(app)
    const registry = targetApp?.exportRegistry || app?.exportRegistry
    const namespace = this.namespace || normalizeKey(extension.name || app?.extension?.id || targetApp?.extension?.id)
    if (!namespace || !registry) {
      return
    }
    for (const item of this.modules) {
      registry.register(namespace, item.id, item.value)
    }
    for (const item of this.chunks) {
      registry.registerChunk(namespace, item.id, item.modules)
    }
  }
}

function resolveExtenderDefinition(value) {
  return typeof value === 'function' ? value() : value
}

function resolveApplication(app) {
  return app?.application || app
}

function resolveRegistry(app) {
  return app?.registry || app?.application?.registry || null
}

function withExtensionId(value, extensionId) {
  if (!extensionId || !value || typeof value !== 'object') {
    return value
  }
  return {
    ...value,
    extensionId: value.extensionId || value.extension_id || extensionId,
    extension_id: value.extension_id || value.extensionId || extensionId,
    moduleId: value.moduleId || value.module_id || extensionId,
    module_id: value.module_id || value.moduleId || extensionId,
  }
}

function normalizeComponentDefinition(type, definitionOrComponent) {
  if (definitionOrComponent && typeof definitionOrComponent === 'object' && !isComponent(definitionOrComponent)) {
    return {
      ...definitionOrComponent,
      type: definitionOrComponent.type || type,
      key: definitionOrComponent.key || definitionOrComponent.type || type,
    }
  }
  return {
    type,
    key: type,
    component: definitionOrComponent,
  }
}

function normalizeGambitFilter({ target, gambit }) {
  if (!gambit || typeof gambit !== 'object') {
    return null
  }
  const syntax = String(gambit.syntax || gambit.pattern || '').trim()
  const code = String(gambit.code || gambit.key || syntax || '').trim()
  if (!code && !syntax) {
    return null
  }
  return {
    key: gambit.key || `${target}:${code || syntax}`,
    code,
    target,
    syntax,
    label: gambit.label || code || syntax,
    description: gambit.description || '',
    category: gambit.category || 'extension',
    order: Number(gambit.order || 100),
  }
}

function normalizeSearchTarget(target) {
  const normalized = normalizeKey(target).toLowerCase()
  if (['discussion', 'discussions'].includes(normalized)) return 'discussions'
  if (['post', 'posts'].includes(normalized)) return 'posts'
  if (['user', 'users'].includes(normalized)) return 'users'
  return normalized || 'all'
}

function normalizeKey(value) {
  return String(value || '').trim()
}

function isComponent(value) {
  return typeof value === 'function' || Boolean(value?.setup || value?.render || value?.template)
}
