import {
  api,
  watch,
  reactive,
  ref } from '@bias/core'

export function createResetPasswordPage({
  apiClient = api,
  initialToken = '',
  navigateToLogin = () => {},
  resolveUiText = (_surface, fallback) => fallback,
  scheduleRedirect = (callback, delay) => setTimeout(callback, delay),
}) {
  const form = reactive({
    token: initialToken,
    password: '',
    passwordConfirm: '',
  })
  const loading = ref(false)
  const error = ref('')
  const success = ref('')

  function syncToken(value) {
    form.token = value?.toString() || ''
  }

  async function submit() {
    error.value = ''
    success.value = ''

    if (form.password !== form.passwordConfirm) {
      error.value = resolveUiText(
        'reset-password-mismatch-error',
        '两次输入的新密码不一致'
      )
      return false
    }

    loading.value = true
    try {
      await apiClient.post('/users/reset-password', {
        token: form.token,
        password: form.password,
      })

      success.value = resolveUiText(
        'reset-password-success',
        '密码已重置，正在返回登录页...'
      )
      scheduleRedirect(() => {
        navigateToLogin('/login')
      }, 1500)
      return true
    } catch (err) {
      error.value = err.response?.data?.error || resolveUiText(
        'reset-password-error',
        '重置失败，请检查令牌或稍后重试'
      )
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    error,
    form,
    loading,
    submit,
    success,
    syncToken,
  }
}

export function useResetPasswordPage({
  route,
  router,
}) {
  const page = createResetPasswordPage({
    initialToken: route.query.token?.toString() || '',
    navigateToLogin(path) {
      router.push(path)
    },
  })

  watch(
    () => route.query.token,
    value => {
      page.syncToken(value)
    }
  )

  return page
}
