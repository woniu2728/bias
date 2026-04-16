import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'

const DEFAULT_SETTINGS = {
  forum_title: 'PyFlarum',
  forum_description: '',
  welcome_title: '欢迎来到PyFlarum',
  welcome_message: '这是一个基于Django和Vue 3的现代化论坛',
  default_locale: 'zh-CN',
  show_language_selector: false,
  primary_color: '#4d698e',
  accent_color: '#e74c3c',
  logo_url: '',
  favicon_url: '',
  custom_css: '',
  custom_header: '',
  maintenance_mode: false,
  maintenance_message: '论坛正在维护中，请稍后再试...',
}

const CUSTOM_CSS_STYLE_ID = 'forum-custom-css'
const CUSTOM_HEADER_CONTAINER_ID = 'forum-custom-header'

export const useForumStore = defineStore('forum', () => {
  const settings = ref({ ...DEFAULT_SETTINGS })
  const initialized = ref(false)

  async function initialize() {
    if (initialized.value) return
    await fetchSettings()
    initialized.value = true
  }

  async function fetchSettings() {
    try {
      const data = await api.get('/forum')
      settings.value = { ...DEFAULT_SETTINGS, ...data }
    } catch (error) {
      console.error('加载论坛设置失败:', error)
      settings.value = { ...DEFAULT_SETTINGS }
    } finally {
      applyRuntimeSettings()
    }
  }

  function applyRuntimeSettings() {
    if (typeof document === 'undefined') return

    document.documentElement.style.setProperty('--forum-primary-color', settings.value.primary_color || DEFAULT_SETTINGS.primary_color)
    document.documentElement.style.setProperty('--forum-accent-color', settings.value.accent_color || DEFAULT_SETTINGS.accent_color)

    document.title = settings.value.forum_title || DEFAULT_SETTINGS.forum_title

    const metaDescription = document.querySelector('meta[name="description"]')
    if (metaDescription) {
      metaDescription.setAttribute('content', settings.value.forum_description || settings.value.welcome_message || DEFAULT_SETTINGS.welcome_message)
    }

    let favicon = document.querySelector('link[rel="icon"]')
    if (!favicon) {
      favicon = document.createElement('link')
      favicon.setAttribute('rel', 'icon')
      document.head.appendChild(favicon)
    }
    favicon.setAttribute('href', settings.value.favicon_url || '/favicon.ico')

    let customCssStyle = document.getElementById(CUSTOM_CSS_STYLE_ID)
    if (!customCssStyle) {
      customCssStyle = document.createElement('style')
      customCssStyle.id = CUSTOM_CSS_STYLE_ID
      document.head.appendChild(customCssStyle)
    }
    customCssStyle.textContent = settings.value.custom_css || ''

    let customHeaderContainer = document.getElementById(CUSTOM_HEADER_CONTAINER_ID)
    if (!customHeaderContainer) {
      customHeaderContainer = document.createElement('div')
      customHeaderContainer.id = CUSTOM_HEADER_CONTAINER_ID
      customHeaderContainer.style.display = 'none'
      document.body.appendChild(customHeaderContainer)
    }
    customHeaderContainer.innerHTML = settings.value.custom_header || ''
  }

  return {
    settings,
    initialized,
    initialize,
    fetchSettings,
  }
})
