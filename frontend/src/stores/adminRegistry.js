import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api from '@/api/index.js'

export const useAdminRegistryStore = defineStore('adminRegistry', () => {
  const extensionScopes = ref([])
  const extensions = ref([])
  const extensionRuntime = ref({})
  const loading = ref(false)
  const loaded = ref(false)

  const enabledModuleIds = computed(() => {
    const ids = new Set()
    for (const item of extensionScopes.value) {
      if (item?.id && item.enabled !== false) {
        ids.add(String(item.id))
      }
    }
    return ids
  })

  async function fetchExtensions(force = false) {
    if (loading.value) {
      return
    }
    if (loaded.value && !force) {
      return
    }

    loading.value = true
    try {
      const extensionsData = await api.get('/admin/extensions', {
        params: { summary: 1 }
      })
      extensions.value = Array.isArray(extensionsData?.extensions)
        ? extensionsData.extensions.filter(item => item?.product_visible !== false)
        : []
      extensionScopes.value = deriveExtensionScopes(extensionsData?.extensions || [])
      extensionRuntime.value = extensionsData?.runtime || extensionsData?.runtime_rebuild || {}
      loaded.value = true
    } catch (error) {
      console.error('加载后台扩展注册表失败:', error)
    } finally {
      loading.value = false
    }
  }

  function isModuleEnabled(moduleId) {
    const normalized = String(moduleId || '').trim()
    if (!normalized) {
      return true
    }
    if (!loaded.value) {
      return true
    }
    return enabledModuleIds.value.has(normalized)
  }

  function applyExtensionScopes(nextScopes) {
    if (!Array.isArray(nextScopes)) {
      extensionScopes.value = []
      loaded.value = true
      return
    }

    const byId = new Map((extensionScopes.value || []).map(item => [String(item.id || ''), item]))
    for (const item of nextScopes) {
      const moduleId = String(item?.id || '').trim()
      if (!moduleId) {
        continue
      }
      byId.set(moduleId, {
        ...(byId.get(moduleId) || {}),
        ...item,
        id: moduleId,
      })
    }
    extensionScopes.value = Array.from(byId.values())
    loaded.value = true
  }

  function applyExtensions(nextExtensions) {
    if (!Array.isArray(nextExtensions)) {
      extensions.value = []
      extensionRuntime.value = {}
      extensionScopes.value = deriveExtensionScopes([])
      loaded.value = true
      return
    }
    extensions.value = nextExtensions.filter(item => item?.product_visible !== false)
    extensionScopes.value = deriveExtensionScopes(nextExtensions)
    loaded.value = true
  }

  function applyExtensionUpdate(extensionId, update) {
    const normalized = String(extensionId || update?.id || '').trim()
    if (!normalized || !update || typeof update !== 'object') {
      return
    }

    const currentExtensions = Array.isArray(extensions.value) ? extensions.value : []
    const index = currentExtensions.findIndex(item => String(item?.id || '').trim() === normalized)
    const nextExtension = {
      ...(index >= 0 ? currentExtensions[index] : {}),
      ...update,
      id: normalized,
    }

    if (index >= 0) {
      extensions.value = currentExtensions.map((item, itemIndex) => (
        itemIndex === index ? nextExtension : item
      ))
    } else if (nextExtension.product_visible !== false) {
      extensions.value = [...currentExtensions, nextExtension]
    }

    extensionScopes.value = deriveExtensionScopes(extensions.value)
    loaded.value = true
  }

  return {
    extensionScopes,
    extensions,
    extensionRuntime,
    loading,
    loaded,
    enabledModuleIds,
    fetchExtensions,
    isModuleEnabled,
    applyExtensionScopes,
    applyExtensions,
    applyExtensionUpdate,
  }
})

function deriveExtensionScopes(extensions) {
  const byId = new Map([
    ['core', { id: 'core', enabled: true }],
  ])

  for (const extension of extensions || []) {
    const moduleIds = Array.isArray(extension?.module_ids) ? extension.module_ids : []
    for (const moduleId of moduleIds) {
      const normalized = String(moduleId || '').trim()
      if (!normalized) {
        continue
      }
      const existing = byId.get(normalized) || {}
      byId.set(normalized, {
        ...existing,
        id: normalized,
        enabled: existing.enabled === true || extension.enabled !== false,
      })
    }
  }

  return Array.from(byId.values())
}
