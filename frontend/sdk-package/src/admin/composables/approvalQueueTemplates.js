export function resolveApprovalTemplateOptions(config, context = {}) {
  const templates = Array.isArray(config?.noteTemplates) ? config.noteTemplates : []
  const itemTypes = Array.isArray(context.itemTypes) ? context.itemTypes.filter(Boolean) : []

  return templates
    .filter(template => {
      if (!template || !template.value) return false

      const actions = Array.isArray(template.actions) && template.actions.length
        ? template.actions
        : null
      if (actions && !actions.includes(context.action)) {
        return false
      }

      const templateItemTypes = Array.isArray(template.itemTypes) && template.itemTypes.length
        ? template.itemTypes
        : null
      if (templateItemTypes && context.itemType && !templateItemTypes.includes(context.itemType)) {
        return false
      }

      if (templateItemTypes && itemTypes.length && !itemTypes.every(itemType => templateItemTypes.includes(itemType))) {
        return false
      }

      return true
    })
    .map(template => ({
      label: template.label || template.value,
      value: template.value,
      description: template.description || '',
    }))
}

export function resolveApprovalSelectionState(items, selectedKeys) {
  const normalizedItems = Array.isArray(items) ? items : []
  const normalizedKeys = selectedKeys instanceof Set ? selectedKeys : new Set()
  const selectableKeys = normalizedItems.map(item => `${item.type}-${item.id}`)
  const selectedItems = normalizedItems.filter(item => normalizedKeys.has(`${item.type}-${item.id}`))

  return {
    selectableKeys,
    selectedItems,
    selectedCount: selectedItems.length,
    allSelected: selectableKeys.length > 0 && selectedItems.length === selectableKeys.length,
    hasSelection: selectedItems.length > 0,
  }
}
