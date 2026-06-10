import { computed } from '@bias/core'
import { getUiCopy } from '@bias/forum'
import { useVerifyEmailPage } from './useVerifyEmailPage'
import { useVerifyEmailViewBindings } from './useVerifyEmailViewBindings'

export function useVerifyEmailViewModel({
  authStore,
  pageState: injectedPageState,
  route,
}) {
  function resolveUiText(surface, fallback) {
    return getUiCopy({ surface })?.text || fallback
  }

  const pageState = injectedPageState || useVerifyEmailPage({
    authStore,
    route,
    resolveUiText,
  })

  const titleText = computed(() => getUiCopy({
    surface: 'verify-email-title',
  })?.text || '验证邮箱')
  const subtitleText = computed(() => getUiCopy({
    surface: 'verify-email-subtitle',
  })?.text || '确认你的邮箱地址后，账号安全设置会完整开放。')
  const loadingText = computed(() => getUiCopy({
    surface: 'verify-email-loading',
  })?.text || '正在验证邮箱，请稍候...')
  const idleText = computed(() => getUiCopy({
    surface: 'verify-email-idle',
  })?.text || '请从邮件中的链接打开本页面，或确认地址中的验证令牌是否完整。')
  const loginActionText = computed(() => getUiCopy({
    surface: 'verify-email-login-action',
  })?.text || '前往登录')
  const profileActionText = computed(() => getUiCopy({
    surface: 'verify-email-profile-action',
  })?.text || '返回个人资料')

  const viewBindings = useVerifyEmailViewBindings({
    error: pageState.error,
    idleText,
    loading: pageState.loading,
    loadingText,
    loginActionText,
    profileActionText,
    success: pageState.success,
    subtitleText,
    titleText,
  })

  return {
    ...pageState,
    ...viewBindings,
  }
}
