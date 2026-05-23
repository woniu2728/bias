import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useForumUiStore = defineStore('forum-ui', () => {
  const initialized = ref(false)

  function applyRuntimeState() {
    if (typeof document === 'undefined') return
    document.documentElement.dataset.theme = 'light'
    document.documentElement.style.colorScheme = 'light'
    document.documentElement.lang = 'zh-CN'
  }

  async function initialize() {
    if (initialized.value) return
    applyRuntimeState()
    initialized.value = true
  }

  async function refreshFromUserPreferences() {
    applyRuntimeState()
  }

  function syncFromForumSettings() {
    applyRuntimeState()
  }

  function hydrateFromUiValues() {
    applyRuntimeState()
  }

  function reset() {
    initialized.value = false
  }

  return {
    initialized,
    initialize,
    reset,
    refreshFromUserPreferences,
    syncFromForumSettings,
    applyRuntimeState,
    hydrateFromUiValues,
  }
})
