import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api from '../api/index.js'
import { syncNotificationTypes } from '../forum/notificationTypes.js'
import { syncPostTypes } from '../forum/postTypes.js'
import {
  applyExtensionDocumentState,
  resolveExtensionPageMeta,
} from '../forum/documentRuntime.js'

const DEFAULT_SETTINGS = {
  forum_title: 'Bias',
  forum_description: '',
  seo_title: '',
  seo_description: '',
  seo_keywords: '',
  seo_robots_index: true,
  seo_robots_follow: true,
  announcement_enabled: false,
  announcement_message: '',
  announcement_tone: 'info',
  primary_color: '#4d698e',
  accent_color: '#e74c3c',
  logo_url: '',
  favicon_url: '',
  custom_head_html: '',
  custom_footer_html: '',
  maintenance_mode: false,
  maintenance_mode_key: 'none',
  maintenance_mode_label: '未启用',
  maintenance_message: '论坛正在维护中，请稍后再试...',
  realtime_typing_enabled: true,
  auth_human_verification_provider: 'off',
  auth_turnstile_site_key: '',
  auth_human_verification_login_enabled: false,
  auth_human_verification_register_enabled: false,
  notification_types: [],
  user_preferences: [],
  post_types: [],
  enabled_modules: [],
  enabled_extensions: [],
}

const CUSTOM_HEAD_MARKER_ATTRIBUTE = 'data-forum-custom-head'

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
  let customHeadNodes = []

  const enabledModuleIds = computed(() => {
    const ids = new Set()
    for (const item of settings.value.enabled_modules || []) {
      const normalized = String(item || '').trim()
      if (normalized) {
        ids.add(normalized)
      }
    }
    return ids
  })

  async function initialize() {
    if (initialized.value) return
    await fetchSettings()
    initialized.value = true
  }

  async function fetchSettings() {
    try {
      const data = await api.get('/forum')
      applyPublicSettings(data)
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

    applyPageMeta()
    applyRuntimeAssets()
  }

  function applyPublicSettings(data = {}) {
    settings.value = { ...DEFAULT_SETTINGS, ...data }
    syncNotificationTypes(settings.value.notification_types)
    syncPostTypes(settings.value.post_types)
  }

  function isModuleEnabled(moduleId) {
    const normalized = String(moduleId || '').trim()
    if (!normalized) {
      return true
    }
    if (!initialized.value) {
      return true
    }
    return enabledModuleIds.value.has(normalized)
  }

  function buildDefaultMeta() {
    const title = settings.value.seo_title || settings.value.forum_title || DEFAULT_SETTINGS.forum_title
    const description = settings.value.seo_description
      || settings.value.forum_description
      || DEFAULT_SETTINGS.forum_description
    const keywords = settings.value.seo_keywords || ''
    const robots = [
      settings.value.seo_robots_index === false ? 'noindex' : 'index',
      settings.value.seo_robots_follow === false ? 'nofollow' : 'follow',
    ].join(', ')

    return {
      title,
      description,
      keywords,
      robots,
      ogTitle: title,
      ogDescription: description,
    }
  }

  function applyPageMeta(meta = {}) {
    if (typeof document === 'undefined') return

    const defaults = buildDefaultMeta()
    const pageTitle = normalizeMetaText(meta.title)
    const siteTitle = settings.value.forum_title || DEFAULT_SETTINGS.forum_title
    const title = pageTitle && pageTitle !== siteTitle ? `${pageTitle} - ${siteTitle}` : (pageTitle || defaults.title)
    const description = normalizeMetaText(meta.description) || defaults.description
    const keywords = normalizeMetaText(meta.keywords) || defaults.keywords
    const robots = normalizeMetaText(meta.robots) || defaults.robots

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

    const canonical = upsertHeadTag('link[rel="canonical"]', () => {
      const element = document.createElement('link')
      element.setAttribute('rel', 'canonical')
      return element
    })
    canonical.setAttribute('href', normalizeCanonicalUrl(meta.canonicalUrl))

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

    const twitterCard = upsertHeadTag('meta[name="twitter:card"]', () => {
      const element = document.createElement('meta')
      element.setAttribute('name', 'twitter:card')
      return element
    })
    twitterCard.setAttribute('content', normalizeMetaText(meta.image || settings.value.logo_url) ? 'summary_large_image' : 'summary')

    const twitterTitle = upsertHeadTag('meta[name="twitter:title"]', () => {
      const element = document.createElement('meta')
      element.setAttribute('name', 'twitter:title')
      return element
    })
    twitterTitle.setAttribute('content', title)

    const twitterDescription = upsertHeadTag('meta[name="twitter:description"]', () => {
      const element = document.createElement('meta')
      element.setAttribute('name', 'twitter:description')
      return element
    })
    twitterDescription.setAttribute('content', description)

    const ogType = upsertHeadTag('meta[property="og:type"]', () => {
      const element = document.createElement('meta')
      element.setAttribute('property', 'og:type')
      return element
    })
    ogType.setAttribute('content', normalizeMetaText(meta.ogType) || 'website')

    const ogUrl = upsertHeadTag('meta[property="og:url"]', () => {
      const element = document.createElement('meta')
      element.setAttribute('property', 'og:url')
      return element
    })
    ogUrl.setAttribute('content', normalizeCanonicalUrl(meta.canonicalUrl))

    const ogSiteName = upsertHeadTag('meta[property="og:site_name"]', () => {
      const element = document.createElement('meta')
      element.setAttribute('property', 'og:site_name')
      return element
    })
    ogSiteName.setAttribute('content', siteTitle)

    const ogImage = normalizeMetaText(meta.image || settings.value.logo_url)
    const existingOgImage = document.head.querySelector('meta[property="og:image"]')
    if (ogImage) {
      const tag = existingOgImage || upsertHeadTag('meta[property="og:image"]', () => {
        const element = document.createElement('meta')
        element.setAttribute('property', 'og:image')
        return element
      })
      tag.setAttribute('content', absoluteUrl(ogImage))

      const twitterImage = upsertHeadTag('meta[name="twitter:image"]', () => {
        const element = document.createElement('meta')
        element.setAttribute('name', 'twitter:image')
        return element
      })
      twitterImage.setAttribute('content', absoluteUrl(ogImage))
    } else if (existingOgImage) {
      existingOgImage.remove()
      document.head.querySelector('meta[name="twitter:image"]')?.remove()
    }
  }

  function setPageMeta(meta = {}) {
    const state = resolveExtensionPageMeta(meta, {
      settings: settings.value,
      route: typeof window === 'undefined' ? null : window.location,
    })
    applyPageMeta(state.meta)
    applyExtensionDocumentState(state)
  }

  function resetPageMeta() {
    setPageMeta()
  }

  function normalizeMetaText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim()
  }

  function normalizeCanonicalUrl(value) {
    if (typeof window === 'undefined') return normalizeMetaText(value)
    return absoluteUrl(value || `${window.location.pathname}${window.location.search}`)
  }

  function absoluteUrl(value) {
    const normalized = normalizeMetaText(value)
    if (!normalized || typeof window === 'undefined') return normalized
    return new URL(normalized, window.location.origin).href
  }

  function applyRuntimeAssets() {
    if (typeof document === 'undefined') return

    let favicon = document.querySelector('link[rel="icon"]')
    if (!favicon) {
      favicon = document.createElement('link')
      favicon.setAttribute('rel', 'icon')
      document.head.appendChild(favicon)
    }
    favicon.setAttribute('href', settings.value.favicon_url || '/favicon.ico')
    applyCustomHeadHtml(settings.value.custom_head_html || '')
  }

  function applyCustomHeadHtml(html) {
    customHeadNodes.forEach((node) => node.remove())
    customHeadNodes = []

    const normalizedHtml = String(html || '').trim()
    if (!normalizedHtml) return

    const template = document.createElement('template')
    template.innerHTML = normalizedHtml

    const nextNodes = []
    Array.from(template.content.childNodes).forEach((node) => {
      const injectedNode = cloneCustomHeadNode(node)
      if (!injectedNode) return
      if (injectedNode.nodeType === Node.ELEMENT_NODE) {
        injectedNode.setAttribute(CUSTOM_HEAD_MARKER_ATTRIBUTE, 'true')
      }
      document.head.appendChild(injectedNode)
      nextNodes.push(injectedNode)
    })

    customHeadNodes = nextNodes
  }

  function cloneCustomHeadNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = String(node.textContent || '').trim()
      return text ? document.createTextNode(text) : null
    }

    if (node.nodeType !== Node.ELEMENT_NODE) {
      return null
    }

    if (node.tagName.toLowerCase() !== 'script') {
      return node.cloneNode(true)
    }

    const script = document.createElement('script')
    Array.from(node.attributes).forEach((attribute) => {
      script.setAttribute(attribute.name, attribute.value)
    })
    script.textContent = node.textContent || ''
    return script
  }

  return {
    settings,
    initialized,
    enabledModuleIds,
    initialize,
    fetchSettings,
    applyPublicSettings,
    isModuleEnabled,
    resetPageMeta,
    setPageMeta,
  }
})
