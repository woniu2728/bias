import {
  extendForum,
} from '@bias/forum'
import {
  registerAuthChallengeProvider,
} from '@bias/users'
import TurnstileChallenge from './TurnstileChallenge.vue'

export const extend = [
  extendForum('security', registerSecurityForum),
]

function registerSecurityForum(forum) {
  registerAuthChallengeProvider({
    key: 'turnstile',
    moduleId: 'security',
    order: 10,
    component: TurnstileChallenge,
    isVisible: ({ mode, settings }) => shouldUseTurnstile(mode, settings),
    buildPayload: ({ token }) => ({
      human_verification_token: token || undefined,
    }),
  })

  forum
    .uiCopy({
      key: 'turnstile-loading',
      order: 90,
      surfaces: ['auth-challenge-status'],
      isVisible: ({ provider, hasToken }) => provider?.key === 'turnstile' && !hasToken,
      resolve: () => ({
        text: '请完成真人验证后再继续。',
      }),
    })
    .uiCopy({
      key: 'auth-turnstile-expired-error',
      order: 1319,
      surfaces: ['auth-turnstile-expired-error'],
      resolve: () => ({ text: '真人验证已过期，请重新完成验证。' }),
    })
    .uiCopy({
      key: 'auth-turnstile-load-error',
      order: 1319,
      surfaces: ['auth-turnstile-load-error'],
      resolve: () => ({ text: '真人验证加载失败，请稍后重试。' }),
    })

  return forum
}

function shouldUseTurnstile(mode, settings = {}) {
  if (settings.auth_human_verification_provider !== 'turnstile') {
    return false
  }
  if (!settings.auth_turnstile_site_key) {
    return false
  }
  if (mode === 'login') {
    return Boolean(settings.auth_human_verification_login_enabled)
  }
  if (mode === 'register') {
    return Boolean(settings.auth_human_verification_register_enabled)
  }
  return false
}
