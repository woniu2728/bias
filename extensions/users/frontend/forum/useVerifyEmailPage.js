import {
  api,
  watch,
  ref } from '@bias/core'

export function createVerifyEmailPage({
  apiClient = api,
  authStore,
  resolveUiText = (_surface, fallback) => fallback,
}) {
  const loading = ref(false)
  const success = ref('')
  const error = ref('')

  async function verifyToken(value) {
    const token = value?.toString().trim()
    success.value = ''
    error.value = ''

    if (!token) {
      return false
    }

    loading.value = true
    try {
      await apiClient.post('/users/verify-email', { token })
      if (authStore.isAuthenticated) {
        await authStore.fetchUser()
      }
      success.value = resolveUiText(
        'verify-email-success',
        '邮箱验证成功。现在你可以继续登录，或返回个人资料查看最新状态。'
      )
      return true
    } catch (err) {
      error.value = err.response?.data?.error || resolveUiText(
        'verify-email-error',
        '邮箱验证失败，请稍后重试'
      )
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    error,
    loading,
    success,
    verifyToken,
  }
}

export function useVerifyEmailPage({
  authStore,
  route,
}) {
  const page = createVerifyEmailPage({
    authStore,
  })

  watch(
    () => route.query.token,
    value => {
      page.verifyToken(value)
    },
    { immediate: true }
  )

  return page
}
