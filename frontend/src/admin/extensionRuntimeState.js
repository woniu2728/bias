export function resetLoadedExtensions(loadedIds, { onReset } = {}) {
  loadedIds?.clear?.()
  if (loadedIds) {
    loadedIds.__biasRuntimeStamp = ''
  }
  if (typeof onReset === 'function') {
    onReset()
  }
}

export function resetLoadedExtensionsWhenRuntimeChanges(loadedIds, runtime, { onReset } = {}) {
  if (!loadedIds || typeof loadedIds.clear !== 'function') {
    return false
  }
  const stamp = String(runtime?.stamp || '')
  const previousStamp = loadedIds.__biasRuntimeStamp || ''
  if (!stamp) {
    return false
  }
  if (previousStamp && previousStamp !== stamp) {
    loadedIds.clear()
    if (typeof onReset === 'function') {
      onReset()
    }
  }
  loadedIds.__biasRuntimeStamp = stamp
  return previousStamp !== stamp
}
