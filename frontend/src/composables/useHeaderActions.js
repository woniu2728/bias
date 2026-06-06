import GlobalSearchModal from '@/components/modals/GlobalSearchModal.vue'
import { openLoginModal, openRegisterModal } from '@/utils/authModal'

export function useHeaderActions({
  authStore,
  composerStore,
  currentSearchQuery,
  modalStore,
  route,
  router
}) {
  function openSearchModal() {
    modalStore.show(
      GlobalSearchModal,
      {
        initialQuery: currentSearchQuery.value,
        initialType: String(route.query.type || 'all')
      },
      {
        size: 'large',
        className: 'Modal--search'
      }
    )
  }

  function openLogin() {
    openLoginModal({ redirectPath: route.fullPath })
  }

  function openRegister() {
    openRegisterModal({ redirectPath: route.fullPath })
  }

  async function handleLogout() {
    if (composerStore.hasUnsavedChanges) {
      const confirmed = await modalStore.confirm({
        title: '确认登出',
        message: composerStore.unsavedMessage || '你有未保存内容，确定要登出吗？',
        confirmText: '继续登出',
        cancelText: '返回',
        tone: 'danger'
      })
      if (!confirmed) return
    }

    authStore.logout()
    router.push('/')
  }

  function clearSearch() {
    if (route.name === 'search') {
      router.push('/')
      return
    }

    if (route.query.q || route.query.search) {
      const nextQuery = { ...route.query }
      delete nextQuery.q
      delete nextQuery.search
      delete nextQuery.type
      delete nextQuery.page

      router.push({
        path: route.path,
        query: nextQuery
      })
    }
  }

  return {
    openSearchModal,
    openLogin,
    openRegister,
    handleLogout,
    clearSearch
  }
}
