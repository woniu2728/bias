import { computed, markRaw, ref } from 'vue'
import { defineStore } from 'pinia'

let modalKeySeed = 0

function buildBasePayload(overrides = {}) {
  return {
    size: 'small',
    className: '',
    dismissibleViaCloseButton: true,
    dismissibleViaEscKey: true,
    dismissibleViaBackdropClick: true,
    ...overrides
  }
}

export const useModalStore = defineStore('modal', () => {
  const current = ref(null)

  function replaceCurrent(nextModal) {
    if (current.value?.resolve) {
      current.value.resolve(current.value.kind === 'confirm' ? false : null)
    }
    current.value = {
      key: `modal-${++modalKeySeed}`,
      ...nextModal
    }
  }

  function close(result = null) {
    if (!current.value) return

    const resolver = current.value.resolve
    current.value = null
    resolver?.(result)
  }

  function dismiss() {
    if (!current.value) return
    close(current.value.kind === 'confirm' ? false : null)
  }

  function alert(options = {}) {
    const payload = typeof options === 'string' ? { message: options } : options

    return new Promise(resolve => {
      replaceCurrent(buildBasePayload({
        kind: 'alert',
        title: payload.title || '提示',
        message: payload.message || '',
        confirmText: payload.confirmText || '确定',
        tone: payload.tone || 'info',
        size: payload.size || 'small',
        className: payload.className || 'Modal--simple',
        resolve
      }))
    })
  }

  function confirm(options = {}) {
    const payload = typeof options === 'string' ? { message: options } : options

    return new Promise(resolve => {
      replaceCurrent(buildBasePayload({
        kind: 'confirm',
        title: payload.title || '确认操作',
        message: payload.message || '',
        confirmText: payload.confirmText || '确定',
        cancelText: payload.cancelText || '取消',
        tone: payload.tone || 'primary',
        size: payload.size || 'small',
        className: payload.className || 'Modal--simple',
        resolve
      }))
    })
  }

  function show(component, props = {}, options = {}) {
    return new Promise(resolve => {
      replaceCurrent(buildBasePayload({
        kind: 'custom',
        component: markRaw(component),
        props,
        size: options.size || 'small',
        className: options.className || '',
        dismissibleViaCloseButton: options.dismissibleViaCloseButton ?? true,
        dismissibleViaEscKey: options.dismissibleViaEscKey ?? true,
        dismissibleViaBackdropClick: options.dismissibleViaBackdropClick ?? true,
        resolve
      }))
    })
  }

  return {
    current,
    isOpen: computed(() => Boolean(current.value)),
    alert,
    confirm,
    show,
    close,
    dismiss
  }
})
