import {
  getDiscussionActionHandler,
  getDiscussionActions,
  getPostActionHandler,
  getPostActions,
  getUiCopy,
} from './frontendRegistry.js'

function getConfirmationText(surface, fallback) {
  return getUiCopy({ surface })?.text || fallback
}

async function runRegisteredAction(item, context = {}, handlerKey = '') {
  if (!item || item.disabled) {
    return false
  }

  const modalStore = context.modalStore
  if (item.confirm && modalStore?.confirm) {
    const confirmed = await modalStore.confirm({
      title: item.confirm.title || item.label || getConfirmationText('discussion-action-confirm-title', '确认操作'),
      message: item.confirm.message || getConfirmationText('discussion-action-confirm-message', '确定继续执行这个操作吗？'),
      confirmText: item.confirm.confirmText || getConfirmationText('discussion-action-confirm-default', '继续'),
      cancelText: item.confirm.cancelText || getConfirmationText('discussion-action-confirm-cancel', '取消'),
      tone: item.confirm.tone || item.tone || 'primary',
    })
    if (!confirmed) {
      return false
    }
  }

  if (typeof item.onClick === 'function') {
    await item.onClick({
      ...context,
      item,
    })
    return true
  }

  const handlers = context[handlerKey] || {}
  const actionKey = item.action || item.key
  if (actionKey && typeof handlers[actionKey] === 'function') {
    await handlers[actionKey](item, context)
    return true
  }

  if (handlerKey === 'discussionActionHandlers') {
    const registeredHandler = getDiscussionActionHandler(actionKey, context)
    if (typeof registeredHandler?.handle === 'function') {
      await registeredHandler.handle({
        ...context,
        item,
      })
      return true
    }
  }

  if (handlerKey === 'postActionHandlers') {
    const registeredHandler = getPostActionHandler(actionKey, context)
    if (typeof registeredHandler?.handle === 'function') {
      await registeredHandler.handle({
        ...context,
        item,
      })
      return true
    }
  }

  return false
}

export function resolveDiscussionAction(actionKey, context = {}) {
  return getDiscussionActions(context).find(item => item.key === actionKey) || null
}

export function resolvePostAction(actionKey, context = {}) {
  return getPostActions(context).find(item => item.key === actionKey) || null
}

export async function runDiscussionAction(item, context = {}) {
  return runRegisteredAction(item, context, 'discussionActionHandlers')
}

export async function runPostAction(item, context = {}) {
  return runRegisteredAction(item, context, 'postActionHandlers')
}
