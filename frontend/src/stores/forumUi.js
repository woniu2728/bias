import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useForumStore } from '@/stores/forum'

const ALLOWED_THEME_MODES = new Set(['light', 'dark', 'system'])
const THEME_STORAGE_KEY = 'bias.theme-mode'
const LOCALE_STORAGE_KEY = 'bias.locale'

function normalizeThemeMode(value, fallback = 'system') {
  const normalized = String(value || fallback).trim().toLowerCase()
  return ALLOWED_THEME_MODES.has(normalized) ? normalized : fallback
}

function normalizeLocale(value, fallback = 'zh-CN') {
  const normalized = String(value || fallback).trim()
  return normalized || fallback
}

export const useForumUiStore = defineStore('forum-ui', () => {
  const themeMode = ref('system')
  const locale = ref('zh-CN')
  const initialized = ref(false)
  let mediaQueryList = null
  let mediaQueryHandler = null

  const resolvedTheme = computed(() => {
    if (themeMode.value !== 'system') return themeMode.value
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return 'light'
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })

  function loadLocalFallbacks() {
    if (typeof window === 'undefined') return
    themeMode.value = normalizeThemeMode(window.localStorage.getItem(THEME_STORAGE_KEY), themeMode.value)
    locale.value = normalizeLocale(window.localStorage.getItem(LOCALE_STORAGE_KEY), locale.value)
  }

  function persistLocalState() {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(THEME_STORAGE_KEY, themeMode.value)
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale.value)
  }

  function applyRuntimeState() {
    if (typeof document === 'undefined') return
    document.documentElement.dataset.theme = resolvedTheme.value
    document.documentElement.style.colorScheme = resolvedTheme.value
    document.documentElement.lang = locale.value
  }

  function bindSystemThemeListener() {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    mediaQueryList = window.matchMedia('(prefers-color-scheme: dark)')
    mediaQueryHandler = () => {
      if (themeMode.value === 'system') {
        applyRuntimeState()
      }
    }
    mediaQueryList.addEventListener?.('change', mediaQueryHandler)
  }

  function unbindSystemThemeListener() {
    mediaQueryList?.removeEventListener?.('change', mediaQueryHandler)
    mediaQueryList = null
    mediaQueryHandler = null
  }

  async function fetchUserUiPreferences() {
    const authStore = useAuthStore()
    if (!authStore.isAuthenticated) {
      return null
    }

    try {
      const data = await api.get('/users/me/preferences')
      return data?.ui_values || null
    } catch (error) {
      console.error('加载用户界面偏好失败:', error)
      return null
    }
  }

  async function refreshFromUserPreferences() {
    const forumStore = useForumStore()
    const userUiValues = await fetchUserUiPreferences()
    if (!userUiValues) {
      syncFromForumSettings()
      return
    }

    themeMode.value = normalizeThemeMode(userUiValues.theme_mode, forumStore.settings.theme_mode || 'system')
    locale.value = normalizeLocale(userUiValues.locale, forumStore.settings.default_locale || 'zh-CN')
    persistLocalState()
    applyRuntimeState()
  }

  async function initialize() {
    if (initialized.value) return
    const forumStore = useForumStore()
    loadLocalFallbacks()
    locale.value = normalizeLocale(locale.value, forumStore.settings.default_locale || 'zh-CN')
    themeMode.value = normalizeThemeMode(themeMode.value, forumStore.settings.theme_mode || 'system')

    const userUiValues = await fetchUserUiPreferences()
    if (userUiValues) {
      themeMode.value = normalizeThemeMode(userUiValues.theme_mode, themeMode.value)
      locale.value = normalizeLocale(userUiValues.locale, locale.value)
    }

    persistLocalState()
    applyRuntimeState()
    bindSystemThemeListener()
    initialized.value = true
  }

  function syncFromForumSettings() {
    const forumStore = useForumStore()
    if (!initialized.value) {
      locale.value = normalizeLocale(locale.value, forumStore.settings.default_locale || 'zh-CN')
      themeMode.value = normalizeThemeMode(themeMode.value, forumStore.settings.theme_mode || 'system')
      return
    }

    if (!useAuthStore().isAuthenticated) {
      const localThemeMode = typeof window === 'undefined' ? '' : window.localStorage.getItem(THEME_STORAGE_KEY)
      const localLocale = typeof window === 'undefined' ? '' : window.localStorage.getItem(LOCALE_STORAGE_KEY)
      locale.value = normalizeLocale(localLocale, forumStore.settings.default_locale || 'zh-CN')
      themeMode.value = normalizeThemeMode(localThemeMode, forumStore.settings.theme_mode || 'system')
      persistLocalState()
      applyRuntimeState()
    }
  }

  async function setThemeMode(nextThemeMode) {
    const normalized = normalizeThemeMode(nextThemeMode, 'system')
    themeMode.value = normalized
    persistLocalState()
    applyRuntimeState()
    await persistUserUiPreferences()
  }

  async function setLocale(nextLocale) {
    const forumStore = useForumStore()
    locale.value = normalizeLocale(nextLocale, forumStore.settings.default_locale || 'zh-CN')
    persistLocalState()
    applyRuntimeState()
    await persistUserUiPreferences()
  }

  async function persistUserUiPreferences() {
    const authStore = useAuthStore()
    if (!authStore.isAuthenticated) return

    try {
      await api.patch('/users/me/preferences', {
        values: {},
        ui_values: {
          theme_mode: themeMode.value,
          locale: locale.value,
        },
      })
    } catch (error) {
      console.error('保存用户界面偏好失败:', error)
    }
  }

  function reset() {
    initialized.value = false
    unbindSystemThemeListener()
  }

  return {
    initialized,
    themeMode,
    locale,
    resolvedTheme,
    initialize,
    reset,
    refreshFromUserPreferences,
    setThemeMode,
    setLocale,
    syncFromForumSettings,
    applyRuntimeState,
  }
})
