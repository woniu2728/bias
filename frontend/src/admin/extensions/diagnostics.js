export function resolveExtensionEntryTypeLabel(entryType) {
  if (entryType === 'filesystem') return '文件系统扩展'
  if (entryType === 'external') return '外部路径'
  return '未声明'
}

export function resolveExtensionNavigationSource(source) {
  if (source && typeof source === 'object' && source.query) {
    return String(source.query.from || '').trim()
  }
  return String(source || '').trim()
}

export function resolveExtensionRouteQuery(source = '', extraQuery = {}) {
  const query = {}

  if (source && typeof source === 'object' && source.query && typeof source.query === 'object') {
    for (const [key, value] of Object.entries(source.query)) {
      const normalizedKey = String(key || '').trim()
      const normalizedValue = normalizeRouteQueryValue(value)
      if (normalizedKey && normalizedValue) {
        query[normalizedKey] = normalizedValue
      }
    }
  } else {
    const from = resolveExtensionNavigationSource(source)
    if (from) {
      query.from = from
    }
  }

  if (extraQuery && typeof extraQuery === 'object') {
    for (const [key, value] of Object.entries(extraQuery)) {
      const normalizedKey = String(key || '').trim()
      const normalizedValue = normalizeRouteQueryValue(value)
      if (normalizedKey && normalizedValue) {
        query[normalizedKey] = normalizedValue
      }
    }
  }

  return query
}

export function buildExtensionRouteTarget(path, source = '') {
  const normalizedPath = String(path || '').trim()
  const query = resolveExtensionRouteQuery(source)

  if (!normalizedPath) {
    return Object.keys(query).length ? { path: '/admin', query } : '/admin'
  }

  if (!Object.keys(query).length) {
    return normalizedPath
  }

  return {
    path: normalizedPath,
    query,
  }
}

export function buildExtensionDetailRouteTarget(extensionId, source = '') {
  const normalizedId = String(extensionId || '').trim()
  if (!normalizedId) {
    return buildExtensionRouteTarget('/admin', source)
  }
  return buildExtensionRouteTarget(`/admin/extensions/${normalizedId}`, source)
}

export function resolveExtensionBackTarget(source, fallback = '/admin') {
  const from = resolveExtensionNavigationSource(source)
  if (from === 'extensions') {
    return '/admin'
  }
  return fallback
}

export function resolveExtensionForumEntryState(extension) {
  if (!extension?.frontend_forum_entry) {
    return '未声明'
  }

  const debugEntry = extension?.debug_info?.frontend_forum_entry || {}
  if (!debugEntry.exists) {
    return '缺失'
  }

  if (!Array.isArray(debugEntry.required_exports) || !debugEntry.required_exports.length) {
    return '已声明'
  }

  const requiredExports = new Set(debugEntry.required_exports)
  const availableExports = new Set(debugEntry.available_exports || [])
  return [...requiredExports].every(exportName => availableExports.has(exportName)) ? '已就绪' : '待修复'
}

export function resolveExtensionMigrationState(extension) {
  const plan = extension?.migration_plan || {}
  const pendingFiles = Array.isArray(plan.pending_files) ? plan.pending_files : []
  const appliedFiles = Array.isArray(plan.applied_files) ? plan.applied_files : []

  if (!extension?.migration_execution && pendingFiles.length) {
    return '待执行'
  }
  if (pendingFiles.length) {
    return '有更新'
  }
  if (appliedFiles.length) {
    return '已同步'
  }
  if (extension?.migration_label) {
    return extension.migration_label
  }
  return '未声明'
}

export function resolveExtensionDiagnostics(extension) {
  const diagnostics = extension?.diagnostics || {}
  const blockingReasons = Array.isArray(diagnostics.blocking_reasons) ? diagnostics.blocking_reasons : []
  const warningReasons = Array.isArray(diagnostics.warning_reasons) ? diagnostics.warning_reasons : []

  return {
    blocking: Boolean(diagnostics.blocking),
    warning: Boolean(diagnostics.warning),
    hasAttention: Boolean(diagnostics.has_attention || diagnostics.blocking || diagnostics.warning),
    blockingReasons,
    warningReasons,
  }
}

export function resolveExtensionDiagnosticsBadges(extension) {
  const diagnostics = resolveExtensionDiagnostics(extension)
  const badges = []

  if (diagnostics.blocking) {
    badges.push({
      key: 'blocking',
      label: `阻断 ${diagnostics.blockingReasons.length || 1}`,
      tone: 'danger',
    })
  }
  if (diagnostics.warning) {
    badges.push({
      key: 'warning',
      label: `告警 ${diagnostics.warningReasons.length || 1}`,
      tone: 'warning',
    })
  }

  return badges
}

export function resolveExtensionDiagnosticsPreview(extension, limit = 2) {
  const diagnostics = resolveExtensionDiagnostics(extension)
  const preview = []

  for (const reason of diagnostics.blockingReasons.slice(0, limit)) {
    preview.push({
      key: `blocking-${reason}`,
      tone: 'danger',
      text: reason,
    })
  }
  for (const reason of diagnostics.warningReasons.slice(0, Math.max(0, limit - preview.length))) {
    preview.push({
      key: `warning-${reason}`,
      tone: 'warning',
      text: reason,
    })
  }

  return preview
}

export function resolveExtensionAdminSurfaceCards(extension) {
  const statuses = Array.isArray(extension?.debug_info?.admin_surface_statuses)
    ? extension.debug_info.admin_surface_statuses
    : []
  const statusMap = Object.fromEntries(
    statuses.map(item => [item.key, item || {}])
  )
  const settingsSchema = Array.isArray(extension?.settings_schema) ? extension.settings_schema : []
  const permissionSummary = extension?.permission_summary || {}
  const adminActions = Array.isArray(extension?.admin_actions) ? extension.admin_actions : []
  const runtimeActions = Array.isArray(extension?.runtime_actions) ? extension.runtime_actions : []

  return [
    {
      key: 'settings',
      label: '设置页',
      route: extension?.action_links?.settings_page || '',
      mode: statusMap.settings?.mode || 'missing',
      modeLabel: statusMap.settings?.mode_label || '缺失',
      summary: resolveSettingsSurfaceSummary(settingsSchema, statusMap.settings),
    },
    {
      key: 'permissions',
      label: '权限页',
      route: extension?.action_links?.permissions_page || '',
      mode: statusMap.permissions?.mode || 'missing',
      modeLabel: statusMap.permissions?.mode_label || '缺失',
      summary: resolvePermissionsSurfaceSummary(permissionSummary, statusMap.permissions),
    },
    {
      key: 'operations',
      label: '操作页',
      route: extension?.action_links?.operations_page || '',
      mode: statusMap.operations?.mode || 'missing',
      modeLabel: statusMap.operations?.mode_label || '缺失',
      summary: resolveOperationsSurfaceSummary(adminActions, runtimeActions, statusMap.operations),
    },
  ]
}

export function resolveExtensionAdminPageCards(extension, { hostKind = '' } = {}) {
  const pages = Array.isArray(extension?.admin_page_details) ? extension.admin_page_details : []
  return pages
    .filter((page) => shouldIncludeAdminPageCard(page, hostKind))
    .map((page) => ({
      key: page.path,
      label: page.label || '',
      description: page.description || '查看当前扩展关联的后台页面。',
      icon: page.icon || 'fas fa-link',
      path: page.path || '',
      target: page.path || '',
      settingsGroup: page.settings_group || '',
    }))
}

export function resolveExtensionAdminPageLabels(extension) {
  return resolveExtensionAdminPageCards(extension)
    .map(item => String(item.label || '').trim())
    .filter(Boolean)
}

export function resolveExtensionPrimaryAdminAction(extension) {
  const actions = Array.isArray(extension?.admin_actions) ? extension.admin_actions : []
  const candidates = ['settings', 'permissions', 'operations', 'details']

  for (const key of candidates) {
    const matched = actions.find(action => action?.kind === 'route' && action?.key === key)
    if (matched) {
      return matched
    }
  }

  return actions.find(action => action?.kind === 'route') || null
}

const operationFocusCopy = {
  notification_types: {
    title: '通知类型',
    description: '查看扩展声明的通知类型、偏好键和触达场景。',
  },
  user_preferences: {
    title: '用户偏好',
    description: '查看扩展暴露给用户的偏好项和默认开关。',
  },
  event_listeners: {
    title: '事件监听',
    description: '查看扩展挂接到运行时事件总线的监听链路。',
  },
  search_filters: {
    title: '搜索过滤',
    description: '查看扩展注册的搜索语法、目标资源和过滤说明。',
  },
  discussion_sorts: {
    title: '讨论排序',
    description: '查看扩展注册到讨论列表的排序能力。',
  },
  discussion_list_filters: {
    title: '列表过滤',
    description: '查看扩展注册到讨论列表的入口和筛选能力。',
  },
  resource_fields: {
    title: '资源字段',
    description: '查看扩展追加到 API 资源上的字段。',
  },
  resource_relationships: {
    title: '资源关系',
    description: '查看扩展追加到 API 资源上的关系。',
  },
  resource_definitions: {
    title: '资源定义',
    description: '查看扩展声明的独立 API 资源。',
  },
  post_types: {
    title: '帖子类型',
    description: '查看扩展注册的帖子类型和渲染入口。',
  },
  language_packs: {
    title: '语言包',
    description: '查看扩展声明的语言包能力。',
  },
}

export function resolveExtensionOperationsProfile(extension) {
  const explicitProfile = normalizeOperationsProfile(extension?.operations_profile || extension?.admin_operations_profile)
  const capabilitySummary = resolveExtensionCapabilitySummaryItems(extension)
  const focusPanels = resolveDefaultOperationsFocusPanels(extension)
  const name = extension?.name || extension?.title || extension?.id || '当前扩展'
  const highlights = capabilitySummary.slice(0, 4).map(item => item.label)
  const capabilityText = highlights.length ? highlights.join('、') : '后台动作、运行操作和能力摘要'
  const defaults = {
    kicker: 'Extension Operations',
    title: `${name} 操作宿主`,
    description: `${name} 当前通过扩展协议暴露${capabilityText}，可在统一操作宿主页集中查看运行状态。`,
    highlights,
    focusPanels,
    recommendedActionKeys: ['operations', 'details'],
    nextSteps: [],
  }

  if (explicitProfile) {
    return {
      ...defaults,
      kicker: explicitProfile.kicker || defaults.kicker,
      title: explicitProfile.title || defaults.title,
      description: explicitProfile.description || defaults.description,
      highlights: explicitProfile.highlights.length ? explicitProfile.highlights : defaults.highlights,
      focusPanels: explicitProfile.focusPanels.length ? explicitProfile.focusPanels : defaults.focusPanels,
      recommendedActionKeys: explicitProfile.recommendedActionKeys.length
        ? explicitProfile.recommendedActionKeys
        : defaults.recommendedActionKeys,
      nextSteps: explicitProfile.nextSteps,
    }
  }

  return defaults
}

function normalizeOperationsProfile(profile) {
  if (!profile || typeof profile !== 'object') {
    return null
  }
  return {
    kicker: String(profile.kicker || '').trim(),
    title: String(profile.title || '').trim(),
    description: String(profile.description || '').trim(),
    highlights: normalizeStringList(profile.highlights),
    focusPanels: normalizeFocusPanels(profile.focus_panels || profile.focusPanels),
    recommendedActionKeys: normalizeStringList(profile.recommended_action_keys || profile.recommendedActionKeys),
    nextSteps: normalizeStringList(profile.next_steps || profile.nextSteps),
  }
}

function resolveDefaultOperationsFocusPanels(extension) {
  return resolveExtensionCapabilityPanels(extension).map((panel) => {
    const copy = operationFocusCopy[panel.key] || {}
    return {
      key: panel.key,
      title: copy.title || panel.label,
      description: copy.description || '查看该能力组下由扩展协议注册的项目。',
    }
  })
}

function normalizeFocusPanels(panels) {
  if (!Array.isArray(panels)) {
    return []
  }
  return panels
    .map((panel) => ({
      key: String(panel?.key || '').trim(),
      title: String(panel?.title || '').trim(),
      description: String(panel?.description || '').trim(),
    }))
    .filter(panel => panel.key)
}

function normalizeStringList(items) {
  if (!Array.isArray(items)) {
    return []
  }
  return items.map(item => String(item || '').trim()).filter(Boolean)
}

export function resolveExtensionOperationsFocusSections(extension) {
  const profile = resolveExtensionOperationsProfile(extension)
  const panelMap = Object.fromEntries(
    resolveExtensionCapabilityPanels(extension).map(panel => [panel.key, panel])
  )

  return (Array.isArray(profile.focusPanels) ? profile.focusPanels : [])
    .map((item) => {
      const panel = panelMap[item.key]
      if (!panel || !panel.items.length) {
        return null
      }
      return {
        key: item.key,
        title: item.title || panel.label,
        description: item.description || '',
        items: panel.items,
      }
    })
    .filter(Boolean)
}

export function resolveExtensionOperationsActionGroups(extension) {
  const adminActions = Array.isArray(extension?.admin_actions) ? extension.admin_actions : []
  const runtimeActions = Array.isArray(extension?.runtime_actions) ? extension.runtime_actions : []
  const profile = resolveExtensionOperationsProfile(extension)
  const primaryAction = resolveExtensionPrimaryAdminAction(extension)
  const recommendedKeys = new Set([
    ...(Array.isArray(profile.recommendedActionKeys) ? profile.recommendedActionKeys : []),
    primaryAction?.key,
  ].filter(Boolean))

  const actionMap = new Map(adminActions.map(action => [action?.key, action]))
  const recommendedActions = []
  const secondaryActions = []

  for (const key of recommendedKeys) {
    const action = actionMap.get(key)
    if (action) {
      recommendedActions.push(action)
      actionMap.delete(key)
    }
  }

  for (const action of adminActions) {
    if (!actionMap.has(action?.key)) {
      continue
    }
    secondaryActions.push(action)
  }

  return [
    {
      key: 'recommended',
      title: '推荐动作',
      description: '优先进入当前扩展最常用的后台入口。',
      actions: recommendedActions,
      actionType: 'admin',
    },
    {
      key: 'admin',
      title: '更多后台动作',
      description: '保留当前扩展声明的其他后台入口与文档动作。',
      actions: secondaryActions,
      actionType: 'admin',
    },
    {
      key: 'runtime',
      title: '运行操作',
      description: '直接执行安装、启用、禁用、卸载或其他运行时钩子。',
      actions: runtimeActions,
      actionType: 'runtime',
    },
  ].filter(group => group.actions.length > 0)
}

export function resolveExtensionOperationsNextSteps(extension) {
  const profile = resolveExtensionOperationsProfile(extension)
  const nextSteps = Array.isArray(profile.nextSteps) ? [...profile.nextSteps] : []
  const adminSurfaceStatuses = Array.isArray(extension?.debug_info?.admin_surface_statuses)
    ? extension.debug_info.admin_surface_statuses
    : []
  const operationsSurface = adminSurfaceStatuses.find(item => item.key === 'operations')

  if (operationsSurface?.mode !== 'custom') {
    nextSteps.push('当前仍复用统一操作宿主页，后续可通过 resolveOperationsPage 替换为扩展自定义操作页。')
  }

  return [...new Set(nextSteps)].filter(Boolean)
}

export function resolveExtensionOperationsSections(extension) {
  return {
    profile: resolveExtensionOperationsProfile(extension),
    capabilitySummaryItems: resolveExtensionCapabilitySummaryItems(extension),
    capabilityPanels: resolveExtensionCapabilityPanels(extension),
    focusSections: resolveExtensionOperationsFocusSections(extension),
    actionGroups: resolveExtensionOperationsActionGroups(extension),
    nextSteps: resolveExtensionOperationsNextSteps(extension),
  }
}

export function resolveExtensionCapabilitySummaryItems(extension) {
  const summary = extension?.capability_summary || {}
  return [
    { key: 'notification_type_count', label: '通知类型', count: resolveCapabilityCount(summary.notification_type_count, extension?.notification_types) },
    { key: 'user_preference_count', label: '用户偏好', count: resolveCapabilityCount(summary.user_preference_count, extension?.user_preferences) },
    { key: 'event_listener_count', label: '事件监听', count: resolveCapabilityCount(summary.event_listener_count, extension?.event_listeners) },
    { key: 'search_filter_count', label: '搜索过滤', count: resolveCapabilityCount(summary.search_filter_count, extension?.search_filters) },
    { key: 'discussion_sort_count', label: '讨论排序', count: resolveCapabilityCount(summary.discussion_sort_count, extension?.discussion_sorts) },
    { key: 'discussion_list_filter_count', label: '列表过滤', count: resolveCapabilityCount(summary.discussion_list_filter_count, extension?.discussion_list_filters) },
    { key: 'resource_field_count', label: '资源字段', count: resolveCapabilityCount(summary.resource_field_count, extension?.resource_fields) },
    { key: 'resource_relationship_count', label: '资源关系', count: resolveCapabilityCount(summary.resource_relationship_count, extension?.resource_relationships) },
    { key: 'resource_definition_count', label: '资源定义', count: resolveCapabilityCount(summary.resource_definition_count, extension?.resource_definitions) },
    { key: 'post_type_count', label: '帖子类型', count: resolveCapabilityCount(summary.post_type_count, extension?.post_types) },
    { key: 'language_pack_count', label: '语言包', count: resolveCapabilityCount(summary.language_pack_count, extension?.language_packs) },
  ].filter(item => item.count > 0)
}

export function resolveExtensionCapabilityPanels(extension) {
  if (!extension) {
    return []
  }

  return [
    buildCapabilityPanel('notification_types', '通知类型', extension?.notification_types, (item) => ({
      key: `${item.module_id}-${item.code}`,
      label: item.label || item.code,
      meta: item.preference_key || item.code,
      description: item.description,
      moduleId: item.module_id,
    })),
    buildCapabilityPanel('user_preferences', '用户偏好', extension?.user_preferences, (item) => ({
      key: `${item.module_id}-${item.key}`,
      label: item.label || item.key,
      meta: item.key,
      description: item.description,
      moduleId: item.module_id,
    })),
    buildCapabilityPanel('event_listeners', '事件监听', extension?.event_listeners, (item) => ({
      key: `${item.module_id}-${item.event}-${item.listener}`,
      label: item.event,
      meta: item.listener,
      description: item.description,
      moduleId: item.module_id,
    })),
    buildCapabilityPanel('search_filters', '搜索过滤', extension?.search_filters, (item) => ({
      key: `${item.module_id}-${item.target}-${item.code}`,
      label: item.label || item.code,
      meta: item.syntax || `${item.target}:${item.code}`,
      description: item.description,
      moduleId: item.module_id,
    })),
    buildCapabilityPanel('discussion_sorts', '讨论排序', extension?.discussion_sorts, (item) => ({
      key: `${item.module_id}-${item.code}`,
      label: item.label || item.code,
      meta: item.code,
      description: item.description,
      moduleId: item.module_id,
    })),
    buildCapabilityPanel('discussion_list_filters', '列表过滤', extension?.discussion_list_filters, (item) => ({
      key: `${item.module_id}-${item.code}`,
      label: item.label || item.code,
      meta: item.route_path || item.code,
      description: item.description,
      moduleId: item.module_id,
    })),
    buildCapabilityPanel('resource_fields', '资源字段', extension?.resource_fields, (item) => ({
      key: `${item.module_id}-${item.resource}-${item.field}`,
      label: `${item.resource}.${item.field}`,
      meta: item.module_id,
      description: item.description,
      moduleId: item.module_id,
    })),
    buildCapabilityPanel('resource_relationships', '资源关系', extension?.resource_relationships, (item) => ({
      key: `${item.module_id}-${item.resource}-${item.relationship}`,
      label: `${item.resource}.${item.relationship}`,
      meta: item.module_id,
      description: item.description,
      moduleId: item.module_id,
    })),
    buildCapabilityPanel('resource_definitions', '资源定义', extension?.resource_definitions, (item) => ({
      key: `${item.module_id}-${item.resource}`,
      label: item.resource,
      meta: item.module_id,
      description: item.description,
      moduleId: item.module_id,
    })),
    buildCapabilityPanel('post_types', '帖子类型', extension?.post_types, (item) => ({
      key: `${item.module_id}-${item.code}`,
      label: item.label || item.code,
      meta: item.code,
      description: item.description,
      moduleId: item.module_id,
    })),
    buildCapabilityPanel('language_packs', '语言包', extension?.language_packs, (item) => ({
      key: `${item.module_id}-${item.code}`,
      label: item.label || item.code,
      meta: item.code,
      description: item.description,
      moduleId: item.module_id,
    })),
  ].filter(panel => panel.items.length > 0)
}

function shouldIncludeAdminPageCard(page, hostKind) {
  const path = String(page?.path || '').trim()
  if (!path || path === '/admin' || path === '/admin/permissions' || path === '/admin/docs') {
    return false
  }

  if (hostKind === 'operations') {
    return ['/admin/advanced', '/admin/audit-logs'].includes(path)
  }

  if (hostKind === 'settings') {
    return Boolean(page?.settings_group) && path !== '/admin/advanced'
  }

  return true
}

function buildCapabilityPanel(key, label, items, mapper) {
  return {
    key,
    label,
    items: mapCapabilityItems(items, mapper),
  }
}

function mapCapabilityItems(items, mapper) {
  if (!Array.isArray(items)) {
    return []
  }
  return items.map(mapper)
}

function normalizeRouteQueryValue(value) {
  if (value === null || value === undefined) {
    return ''
  }
  return String(value).trim()
}

function resolveCapabilityCount(summaryValue, items) {
  const count = Number(summaryValue || 0)
  if (count > 0) {
    return count
  }
  return Array.isArray(items) ? items.length : 0
}

function resolveSettingsSurfaceSummary(settingsSchema, status) {
  if (status?.mode === 'custom') {
    return settingsSchema.length ? `${settingsSchema.length} 个设置项` : '自定义设置组件'
  }
  if (status?.mode === 'generated') {
    return settingsSchema.length ? `自动生成 ${settingsSchema.length} 个设置项` : '自动生成设置表单'
  }
  if (status?.mode === 'default') {
    return '复用平台默认设置页'
  }
  return '未提供设置承载'
}

function resolvePermissionsSurfaceSummary(permissionSummary, status) {
  const permissionCount = Number(permissionSummary?.permission_count || 0)
  const sectionCount = Number(permissionSummary?.section_count || 0)
  if (permissionCount > 0) {
    return `${permissionCount} 项权限，${sectionCount} 个分组`
  }
  if (status?.mode === 'custom') {
    return '自定义权限组件'
  }
  if (status?.mode === 'generated' || status?.mode === 'default') {
    return '复用统一权限矩阵'
  }
  return '未注册扩展权限'
}

function resolveOperationsSurfaceSummary(adminActions, runtimeActions, status) {
  const count = adminActions.length + runtimeActions.length
  if (count > 0) {
    return `${adminActions.length} 个后台动作，${runtimeActions.length} 个运行操作`
  }
  if (status?.mode === 'custom') {
    return '自定义操作组件'
  }
  if (status?.mode === 'generated' || status?.mode === 'default') {
    return '复用统一操作宿主'
  }
  return '未声明可执行操作'
}
