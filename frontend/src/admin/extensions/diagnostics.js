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
