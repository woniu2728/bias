export async function runComposerSecondaryAction(item, context = {}) {
  if (!item || item.disabled) {
    return false
  }

  const modalStore = context.modalStore
  if (item.confirm && modalStore?.confirm) {
    const confirmed = await modalStore.confirm({
      title: item.confirm.title || item.label || '确认操作',
      message: item.confirm.message || '确定继续执行这个操作吗？',
      confirmText: item.confirm.confirmText || '确定',
      cancelText: item.confirm.cancelText || '取消',
      tone: item.confirm.tone || item.tone || 'primary',
    })
    if (!confirmed) {
      return false
    }
  }

  if (typeof item.onClick === 'function') {
    await item.onClick(context)
    return true
  }

  const handlers = context.secondaryActionHandlers || {}
  if (item.action && typeof handlers[item.action] === 'function') {
    await handlers[item.action](item, context)
    return true
  }

  return false
}
