import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api from '@/api'

export const useAdminRegistryStore = defineStore('adminRegistry', () => {
  const modules = ref([])
  const extensions = ref([])
  const loading = ref(false)
  const loaded = ref(false)

  const enabledModuleIds = computed(() => {
    const ids = new Set()
    for (const item of modules.value) {
      if (item?.id && item.enabled !== false) {
        ids.add(String(item.id))
      }
    }
    return ids
  })

  async function fetchModules(force = false) {
    if (loading.value) {
      return
    }
    if (loaded.value && !force) {
      return
    }

    loading.value = true
    try {
      const [modulesData, extensionsData] = await Promise.all([
        api.get('/admin/modules'),
        api.get('/admin/extensions'),
      ])
      modules.value = Array.isArray(modulesData?.modules) ? modulesData.modules : []
      extensions.value = Array.isArray(extensionsData?.extensions)
        ? extensionsData.extensions.filter(item => item?.product_visible !== false)
        : []
      loaded.value = true
    } catch (error) {
      console.error('加载后台模块注册表失败:', error)
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

  function applyModules(nextModules) {
    if (!Array.isArray(nextModules)) {
      modules.value = []
      loaded.value = true
      return
    }

    const byId = new Map((modules.value || []).map(item => [String(item.id || ''), item]))
    for (const item of nextModules) {
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
    modules.value = Array.from(byId.values())
    loaded.value = true
  }

  function applyExtensions(nextExtensions) {
    if (!Array.isArray(nextExtensions)) {
      extensions.value = []
      return
    }
    extensions.value = nextExtensions.filter(item => item?.product_visible !== false)
  }

  return {
    modules,
    extensions,
    loading,
    loaded,
    enabledModuleIds,
    fetchModules,
    isModuleEnabled,
    applyModules,
    applyExtensions,
  }
})
