let currentExtensionId = ''

export function getCurrentExtensionId() {
  return currentExtensionId
}

export function runWithExtensionScope(extensionId, callback) {
  const previous = currentExtensionId
  currentExtensionId = String(extensionId || '').trim()
  try {
    return callback()
  } finally {
    currentExtensionId = previous
  }
}
