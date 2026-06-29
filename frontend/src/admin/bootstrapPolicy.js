export function shouldPreloadAdminExtension(extension) {
  return extension?.enabled !== false && extension?.frontend_boot?.admin === true
}

export function filterPreloadAdminExtensions(extensions = []) {
  return (Array.isArray(extensions) ? extensions : []).filter(shouldPreloadAdminExtension)
}
