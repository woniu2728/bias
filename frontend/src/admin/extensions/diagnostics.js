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

export function resolveExtensionCapabilitySummaryItems(extension) {
  const summary = extension?.capability_summary || {}
  return [
    { key: 'notification_type_count', label: '通知类型', count: Number(summary.notification_type_count || 0) },
    { key: 'user_preference_count', label: '用户偏好', count: Number(summary.user_preference_count || 0) },
    { key: 'event_listener_count', label: '事件监听', count: Number(summary.event_listener_count || 0) },
    { key: 'search_filter_count', label: '搜索过滤', count: Number(summary.search_filter_count || 0) },
    { key: 'discussion_sort_count', label: '讨论排序', count: Number(summary.discussion_sort_count || 0) },
    { key: 'discussion_list_filter_count', label: '列表过滤', count: Number(summary.discussion_list_filter_count || 0) },
    { key: 'resource_field_count', label: '资源字段', count: Number(summary.resource_field_count || 0) },
    { key: 'resource_relationship_count', label: '资源关系', count: Number(summary.resource_relationship_count || 0) },
    { key: 'resource_definition_count', label: '资源定义', count: Number(summary.resource_definition_count || 0) },
    { key: 'post_type_count', label: '帖子类型', count: Number(summary.post_type_count || 0) },
    { key: 'language_pack_count', label: '语言包', count: Number(summary.language_pack_count || 0) },
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
