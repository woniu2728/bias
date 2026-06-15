import { extendAdmin } from '@bias/admin'

const SECURITY_PAGE_KEY = 'security.settings'

export const extend = [
  extendAdmin(admin => admin
    .pageCopy(SECURITY_PAGE_KEY, {
      key: 'security-human-verification-settings-copy',
      moduleId: 'security',
      order: 20,
      resolve: () => ({
        pageTitle: '安全设置',
        pageDescription: '配置登录和注册真人验证。',
      }),
    })
    .pageConfig(SECURITY_PAGE_KEY, {
      key: 'security-human-verification-settings-config',
      moduleId: 'security',
      order: 20,
      resolve: () => ({
        defaultSettings: {
          auth_human_verification_provider: 'off',
          auth_turnstile_site_key: '',
          auth_turnstile_secret_key: '',
          auth_human_verification_login_enabled: true,
          auth_human_verification_register_enabled: true,
        },
        placeholders: {
          turnstileSiteKey: '0x4AAAA...',
          turnstileSecretKey: '0x4AAAA...',
        },
        humanVerificationProviderOptions: [
          { value: 'off', label: '关闭' },
          { value: 'turnstile', label: 'Cloudflare Turnstile' },
        ],
        sensitiveLabels: {
          auth_human_verification_provider: '真人验证提供方',
          auth_turnstile_site_key: 'Turnstile Site Key',
          auth_turnstile_secret_key: 'Turnstile Secret Key',
          auth_human_verification_login_enabled: '登录时启用真人验证',
          auth_human_verification_register_enabled: '注册时启用真人验证',
        },
      }),
    }))
]

export function resolveDetailPage() {
  return null
}

export function resolveSettingsPage() {
  return null
}
