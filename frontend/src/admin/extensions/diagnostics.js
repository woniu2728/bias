export function resolveExtensionEntryTypeLabel(entryType) {
  if (entryType === 'builtin') return '内置入口'
  if (entryType === 'filesystem') return '文件系统扩展'
  if (entryType === 'external') return '外部路径'
  return '未声明'
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
