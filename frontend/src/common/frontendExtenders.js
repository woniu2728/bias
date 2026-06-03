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
        const setting = resolveAdminDefinition(item.setting)
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
        const permission = resolveAdminDefinition(item.permission)
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
        const values = resolveAdminDefinition(item.items) || []
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

function resolveAdminDefinition(value) {
  return typeof value === 'function' ? value() : value
}

function resolveApplication(app) {
  return app?.application || app
}

function resolveRegistry(app) {
  return app?.registry || app?.application?.registry || null
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
