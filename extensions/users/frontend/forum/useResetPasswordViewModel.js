import { computed } from '@bias/core'
import { getUiCopy } from '@bias/forum'
import { useResetPasswordPage } from './useResetPasswordPage'
import { useResetPasswordViewBindings } from './useResetPasswordViewBindings'

export function useResetPasswordViewModel({
  pageState: injectedPageState,
  route,
  router,
}) {
  function resolveUiText(surface, fallback, context = {}) {
    return getUiCopy({
      surface,
      ...context,
    })?.text || fallback
  }

  const pageState = injectedPageState || useResetPasswordPage({
    route,
    router,
    resolveUiText,
  })

  const titleText = computed(() => getUiCopy({
    surface: 'reset-password-title',
  })?.text || '重置密码')
  const subtitleText = computed(() => getUiCopy({
    surface: 'reset-password-subtitle',
  })?.text || '输入新的密码以完成重置。如果你是通过邮件打开页面，令牌会自动填入。')
  const tokenLabelText = computed(() => getUiCopy({
    surface: 'reset-password-token-label',
  })?.text || '重置令牌')
  const newPasswordLabelText = computed(() => getUiCopy({
    surface: 'reset-password-new-label',
  })?.text || '新密码')
  const confirmPasswordLabelText = computed(() => getUiCopy({
    surface: 'reset-password-confirm-label',
  })?.text || '确认新密码')
  const tokenPlaceholderText = computed(() => getUiCopy({
    surface: 'reset-password-token-placeholder',
  })?.text || '请输入邮件中的重置令牌')
  const newPasswordPlaceholderText = computed(() => getUiCopy({
    surface: 'reset-password-new-placeholder',
  })?.text || '请输入新密码')
  const confirmPasswordPlaceholderText = computed(() => getUiCopy({
    surface: 'reset-password-confirm-placeholder',
  })?.text || '请再次输入新密码')
  const submitButtonText = computed(() => getUiCopy({
    surface: 'reset-password-submit',
    loading: pageState.loading.value,
  })?.text || (pageState.loading.value ? '提交中...' : '重置密码'))
  const backToLoginText = computed(() => getUiCopy({
    surface: 'reset-password-back-to-login',
  })?.text || '返回登录')

  const viewBindings = useResetPasswordViewBindings({
    backToLoginText,
    confirmPasswordLabelText,
    confirmPasswordPlaceholderText,
    error: pageState.error,
    form: pageState.form,
    loading: pageState.loading,
    newPasswordLabelText,
    newPasswordPlaceholderText,
    submit: pageState.submit,
    submitButtonText,
    success: pageState.success,
    subtitleText,
    titleText,
    tokenLabelText,
    tokenPlaceholderText,
  })

  return {
    ...pageState,
    ...viewBindings,
  }
}
