import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/api'

const DEFAULT_SETTINGS = {
  forum_title: 'PyFlarum',
  forum_description: '',
  seo_title: '',
  seo_description: '',
  seo_keywords: '',
  seo_robots_index: true,
  seo_robots_follow: true,
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

function upsertHeadTag(selector, buildTag) {
  let element = document.head.querySelector(selector)
  if (!element) {
    element = buildTag()
    document.head.appendChild(element)
  }
  return element
}

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

    const title = settings.value.seo_title || settings.value.forum_title || DEFAULT_SETTINGS.forum_title
    const description = settings.value.seo_description
      || settings.value.forum_description
      || settings.value.welcome_message
      || DEFAULT_SETTINGS.welcome_message
    const keywords = settings.value.seo_keywords || ''
    const robots = [
      settings.value.seo_robots_index === false ? 'noindex' : 'index',
      settings.value.seo_robots_follow === false ? 'nofollow' : 'follow',
    ].join(', ')

    document.title = title

    const metaDescription = upsertHeadTag('meta[name="description"]', () => {
      const element = document.createElement('meta')
      element.setAttribute('name', 'description')
      return element
    })
    metaDescription.setAttribute('content', description)

    const metaKeywords = upsertHeadTag('meta[name="keywords"]', () => {
      const element = document.createElement('meta')
      element.setAttribute('name', 'keywords')
      return element
    })
    metaKeywords.setAttribute('content', keywords)

    const metaRobots = upsertHeadTag('meta[name="robots"]', () => {
      const element = document.createElement('meta')
      element.setAttribute('name', 'robots')
      return element
    })
    metaRobots.setAttribute('content', robots)

    const ogTitle = upsertHeadTag('meta[property="og:title"]', () => {
      const element = document.createElement('meta')
      element.setAttribute('property', 'og:title')
      return element
    })
    ogTitle.setAttribute('content', title)

    const ogDescription = upsertHeadTag('meta[property="og:description"]', () => {
      const element = document.createElement('meta')
      element.setAttribute('property', 'og:description')
      return element
    })
    ogDescription.setAttribute('content', description)

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
