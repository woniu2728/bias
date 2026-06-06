import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

export function useHeaderUiState({
  authStore,
  closeMobileDrawer,
  closeHeaderOverlays = () => {},
  handleLogout,
  openLogin,
  openRegister,
  resetMobileHeaderOverride,
  route,
  updateMobileHeaderOverride
}) {
  const showUserMenu = ref(false)

  function closeUserMenu() {
    showUserMenu.value = false
  }

  function toggleUserMenu() {
    closeHeaderOverlays({ source: 'user-menu' })
    showUserMenu.value = !showUserMenu.value
  }

  function handleWindowClick(event) {
    if (!event.target.closest('.user-dropdown')) {
      closeUserMenu()
    }
  }

  function handleMobileHeaderUpdate(event) {
    updateMobileHeaderOverride(event.detail)
  }

  function handleMobileHeaderReset() {
    resetMobileHeaderOverride()
  }

  function openLoginFromDrawer() {
    closeMobileDrawer()
    openLogin()
  }

  function openRegisterFromDrawer() {
    closeMobileDrawer()
    openRegister()
  }

  async function logoutFromDrawer() {
    closeMobileDrawer()
    await handleLogout()
    closeUserMenu()
  }

  watch(
    () => authStore.isAuthenticated,
    (isAuthenticated) => {
      if (!isAuthenticated) {
        closeHeaderOverlays({ source: 'auth' })
      }
    },
    { immediate: true }
  )

  watch(
    () => route.fullPath,
    () => {
      closeHeaderOverlays({ source: 'route' })
      closeUserMenu()
      closeMobileDrawer()

      if (route.name !== 'discussion-detail') {
        resetMobileHeaderOverride()
      }
    }
  )

  onMounted(() => {
    if (typeof window === 'undefined') return

    window.addEventListener('click', handleWindowClick)
    window.addEventListener('bias:mobile-header-update', handleMobileHeaderUpdate)
    window.addEventListener('bias:mobile-header-reset', handleMobileHeaderReset)
  })

  onBeforeUnmount(() => {
    if (typeof window === 'undefined') return

    window.removeEventListener('click', handleWindowClick)
    window.removeEventListener('bias:mobile-header-update', handleMobileHeaderUpdate)
    window.removeEventListener('bias:mobile-header-reset', handleMobileHeaderReset)
  })

  return {
    showUserMenu,
    toggleUserMenu,
    openLoginFromDrawer,
    openRegisterFromDrawer,
    logoutFromDrawer
  }
}
