function upsertByKey(target, value) {
  const existingIndex = target.findIndex(item => item.key === value.key)
  if (existingIndex >= 0) {
    target.splice(existingIndex, 1, value)
    return value
  }

  target.push(value)
  return value
}

function resolveAdminItem(item, context = {}) {
  const isVisible = typeof item.isVisible === 'function' ? item.isVisible(context) : true
  if (!isVisible) {
    return null
  }

  const resolvedItem = typeof item.resolve === 'function'
    ? item.resolve(context)
    : item

  if (!resolvedItem) {
    return null
  }

  return {
    ...item,
    ...resolvedItem,
  }
}

function sortByOrder(left, right) {
  return (left.order || 100) - (right.order || 100)
}

export function createSingleItemRegistry(defaults = {}) {
  const items = []

  return {
    register(item) {
      return upsertByKey(items, {
        order: 100,
        ...defaults,
        ...item,
      })
    },
    get(context = {}) {
      return [...items]
        .sort(sortByOrder)
        .map(item => resolveAdminItem(item, context))
        .find(Boolean) || null
    },
  }
}

export function createListItemRegistry(defaults = {}) {
  const items = []

  return {
    register(item) {
      return upsertByKey(items, {
        order: 100,
        ...defaults,
        ...item,
      })
    },
    get(context = {}) {
      return [...items]
        .sort(sortByOrder)
        .map(item => resolveAdminItem(item, context))
        .filter(Boolean)
    },
    getByKey(context = {}, key = '') {
      if (!key) {
        return null
      }

      return [...items]
        .filter(item => item.key === key)
        .sort(sortByOrder)
        .map(item => resolveAdminItem(item, context))
        .find(Boolean) || null
    },
  }
}
