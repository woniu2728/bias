import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import api from '@/api'

export const useAdminRegistryStore = defineStore('adminRegistry', () => {
  const modules = ref([])
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
      const data = await api.get('/admin/modules')
      modules.value = Array.isArray(data?.modules) ? data.modules : []
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
    modules.value = Array.isArray(nextModules) ? nextModules : []
    loaded.value = true
  }

  return {
    modules,
    loading,
    loaded,
    enabledModuleIds,
    fetchModules,
    isModuleEnabled,
    applyModules,
  }
})
