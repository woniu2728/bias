export function resolveExtensionEntryTypeLabel(entryType) {
  if (entryType === 'builtin') return '内置入口'
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
    return Object.keys(query).length ? { path: '/admin/extensions', query } : '/admin/extensions'
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
    return buildExtensionRouteTarget('/admin/extensions', source)
  }
  return buildExtensionRouteTarget(`/admin/extensions/${normalizedId}`, source)
}

export function resolveExtensionBackTarget(source, fallback = '/admin/extensions') {
  if (source && typeof source === 'object' && source.query) {
    const from = String(source.query.from || '').trim()
    const moduleId = String(source.query.module || '').trim()
    if (from === 'modules' && moduleId) {
      return {
        path: '/admin/modules',
        query: {
          from: 'modules',
          module: moduleId,
        },
      }
    }
  }
  const from = resolveExtensionNavigationSource(source)
  if (from === 'extensions') {
    return '/admin/extensions'
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
  const internalPageTargets = {
    '/admin/basics': '/admin/internal/core/basics',
    '/admin/appearance': '/admin/internal/core/appearance',
    '/admin/mail': '/admin/internal/core/mail',
    '/admin/advanced': '/admin/internal/core/advanced',
    '/admin/audit-logs': '/admin/internal/core/audit-logs',
    '/admin/docs': '/admin/internal/core/docs',
  }

  const pages = Array.isArray(extension?.admin_page_details) ? extension.admin_page_details : []
  return pages
    .filter((page) => shouldIncludeAdminPageCard(page, hostKind))
    .map((page) => ({
      key: page.path,
      label: page.label || '',
      description: page.description || '查看当前扩展关联的后台页面。',
      icon: page.icon || 'fas fa-link',
      path: page.path || '',
      target: internalPageTargets[page.path] || page.path || '',
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

export function resolveExtensionOperationsProfile(extension) {
  const extensionId = String(extension?.id || '').trim()
  const profiles = {
    discussions: {
      kicker: 'Discussion Runtime',
      title: '讨论流与内容治理',
      description: '集中查看讨论列表、搜索语法、排序规则和内容治理能力，作为核心讨论模块的统一操作宿主页。',
      highlights: ['讨论列表', '搜索过滤', '排序规则', '治理权限'],
      focusPanels: [
        { key: 'discussion_sorts', title: '讨论排序', description: '用于确认讨论流当前暴露了哪些排序方式，以及默认排序是否已经进入扩展协议。' },
        { key: 'discussion_list_filters', title: '讨论列表入口', description: '用于检查讨论流、我的讨论、未读等列表入口是否都已通过统一列表过滤协议暴露。' },
        { key: 'search_filters', title: '讨论搜索语法', description: '用于查看作者、状态、创建时间等搜索过滤是否已经完成注册。' },
      ],
      recommendedActionKeys: ['permissions', 'operations', 'details'],
      nextSteps: ['后续将讨论治理和列表策略拆成更细的自定义操作页。'],
    },
    posts: {
      kicker: 'Post Stream',
      title: '帖子流与内容输出',
      description: '集中查看帖子类型、帖子搜索和楼层内容输出能力，作为核心帖子模块的统一操作宿主页。',
      highlights: ['帖子类型', '帖子搜索', '内容输出'],
      focusPanels: [
        { key: 'post_types', title: '帖子类型', description: '用于确认评论、系统事件帖等帖子类型是否已经全部进入统一帖子类型协议。' },
        { key: 'search_filters', title: '帖子搜索语法', description: '用于检查按作者、创建时间、提及等帖子搜索扩展是否已经按协议注册。' },
      ],
      recommendedActionKeys: ['operations', 'details'],
      nextSteps: ['后续将帖子流诊断、渲染策略和系统事件帖说明拆到独立操作页。'],
    },
    notifications: {
      kicker: 'Notification Hub',
      title: '通知分发与偏好',
      description: '集中查看站内通知类型、通知偏好和通知相关动作，便于继续拆分独立通知设置页。',
      highlights: ['通知类型', '通知偏好', '站内提醒动作'],
      focusPanels: [
        { key: 'notification_types', title: '通知触达面', description: '优先关注当前扩展声明了哪些通知类型，以及这些通知最终会触达哪些用户场景。' },
        { key: 'user_preferences', title: '用户通知偏好', description: '这里收口通知开关和默认偏好，后续可继续演进为独立通知策略设置页。' },
      ],
    },
    mentions: {
      kicker: 'Mention Signals',
      title: '提及规则与提醒',
      description: '集中查看 @提及 相关的搜索过滤、通知能力和后续可扩展的处理动作。',
      highlights: ['@提及通知', '提及搜索过滤', '提及触发链路'],
      focusPanels: [
        { key: 'notification_types', title: '提及提醒', description: '用于确认 @提及 的提醒类型和最终通知入口。' },
        { key: 'search_filters', title: '提及过滤语法', description: '用于检查与提及相关的搜索过滤是否已经进入统一搜索扩展协议。' },
      ],
    },
    subscriptions: {
      kicker: 'Subscription Flow',
      title: '关注流与关注通知',
      description: '集中查看关注讨论、关注流和关注后通知能力，为后续独立关注设置页做准备。',
      highlights: ['关注偏好', '关注列表过滤', '关注后通知'],
      focusPanels: [
        { key: 'user_preferences', title: '关注偏好', description: '用于检查自动关注和关注后通知等核心偏好是否都已经走统一配置协议。' },
        { key: 'discussion_list_filters', title: '关注列表入口', description: '用于检查关注列表过滤能力是否已经稳定挂接到讨论列表协议。' },
        { key: 'event_listeners', title: '关注触发链路', description: '用于确认回复后关注通知的事件监听是否仍然沿统一总线分发。' },
      ],
    },
    realtime: {
      kicker: 'Realtime Runtime',
      title: '实时连接与广播',
      description: '集中查看实时广播、连接能力和相关运行操作，便于后续收口为独立实时运维页。',
      highlights: ['实时广播', '事件监听', '连接运行状态'],
      focusPanels: [
        { key: 'event_listeners', title: '广播事件链路', description: '用于确认实时广播依赖的事件监听和消息分发入口是否已经注册到统一协议。' },
      ],
      recommendedActionKeys: ['operations', 'details'],
      nextSteps: ['继续补齐实时连接诊断与广播状态摘要。', '后续将实时运行操作收口到独立运维页。'],
    },
    likes: {
      kicker: 'Reaction Flow',
      title: '点赞互动与提醒',
      description: '集中查看点赞通知、互动偏好和后续可扩展的互动后台动作。',
      highlights: ['点赞通知', '互动偏好'],
      focusPanels: [
        { key: 'notification_types', title: '点赞通知', description: '用于确认点赞触发后的提醒类型和对应偏好是否已经标准化。' },
        { key: 'user_preferences', title: '互动偏好', description: '用于检查点赞相关通知偏好是否已进入统一用户偏好协议。' },
      ],
      recommendedActionKeys: ['operations', 'details'],
      nextSteps: ['继续补齐点赞统计和互动诊断入口。'],
    },
    'tag-stats': {
      kicker: 'Tag Runtime',
      title: '标签统计刷新链路',
      description: '集中查看标签统计依赖的事件刷新链路，为后续拆分标签运维页做准备。',
      highlights: ['统计刷新', '事件监听'],
      focusPanels: [
        { key: 'event_listeners', title: '刷新事件链路', description: '用于确认标签统计刷新依赖的事件监听是否已经全部走统一总线。' },
      ],
      recommendedActionKeys: ['operations', 'details'],
      nextSteps: ['继续补齐标签统计刷新任务与延迟队列的运行摘要。'],
    },
  }

  const profile = profiles[extensionId]
  if (profile) {
    return profile
  }

  const name = extension?.name || '当前扩展'
  return {
    kicker: 'Extension Operations',
    title: `${name} 操作宿主`,
    description: `${name} 当前复用统一操作宿主页承接后台动作、运行操作和能力摘要，后续可逐步替换为扩展自定义操作页。`,
    highlights: [],
    focusPanels: [],
    recommendedActionKeys: ['operations', 'details'],
    nextSteps: [],
  }
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
  if (!path || path === '/admin' || path === '/admin/modules' || path === '/admin/permissions') {
    return false
  }

  if (hostKind === 'operations') {
    return ['/admin/advanced', '/admin/audit-logs', '/admin/docs'].includes(path)
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
