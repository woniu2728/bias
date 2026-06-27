export { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, toRef, watch } from 'vue'
export { useRoute, useRouter } from 'vue-router'
export { createPinia, defineStore, setActivePinia } from 'pinia'
export { default as api, default as coreApi } from '../api/index.js'
export { extend, override, resetPatches } from './extend.js'
export { ItemList, itemContentValue } from './itemList.js'
export {
  clearRegistryExtensions,
  getFirstSurfaceAwareItem,
  isRegisteredItemEnabled,
  normalizeRegisteredItem,
  orderedRegisteredItems,
  resolveRegisteredItem,
  upsertByKey,
} from './contributionRegistry.js'
export {
  getFrontendRegistrySlot,
  getFrontendRegistrySlots,
} from './frontendRegistrySlots.js'
export {
  applyTheme,
  applyThemeHeadTags,
  bootstrapThemeRuntime,
  getActiveTheme,
  loadThemeManifest,
} from '../theme/themeRuntime.js'
export {
  clearThemeSlots,
  getThemeSlot,
  getThemeSlots,
  registerThemeSlot,
} from '../theme/themeSlots.js'
export {
  defaultThemeTokens,
  normalizeThemeTokens,
} from '../theme/tokens.js'
export {
  ResourceModel,
  normalizeModelData,
} from './resourceModel.js'
export {
  formatMonth,
  formatRelativeTime,
} from './formatting.js'
export { unwrapList } from './data.js'
export { usePaginatedListState } from '../composables/usePaginatedListState.js'
export { useRequestedPaginatedListState } from '../composables/useRequestedPaginatedListState.js'
export { useRouteListState } from '../composables/useRouteListState.js'
export { useRoutePagination } from '../composables/useRoutePagination.js'
export { useModalStore } from '../stores/modal.js'
export { useResourceStore } from '../stores/resource.js'
export * from './extenders.js'
