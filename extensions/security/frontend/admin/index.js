import { extendAdmin } from '@bias/admin'

const ADVANCED_PAGE_KEY = 'core.advanced'

export const extend = [
  extendAdmin(admin => admin
    .pageCopy(ADVANCED_PAGE_KEY, {
      key: 'security-human-verification-advanced-copy',
      moduleId: 'security',
      order: 20,
      resolve: () => ({
        humanVerificationSectionTitle: '安全与真人验证',
        humanVerificationProviderLabel: '验证提供方',
        humanVerificationProviderHelpText: '建议正式环境开启，优先拦截登录和注册机器人。',
        turnstileSiteKeyLabel: 'Site Key',
        turnstileSecretKeyLabel: 'Secret Key',
        turnstileLoginEnabledLabel: '登录时启用真人验证',
        turnstileRegisterEnabledLabel: '注册时启用真人验证',
        turnstileMisconfiguredText: '已选择 Turnstile，但 Site Key 或 Secret Key 仍为空，当前不会真正启用验证。',
      }),
    })
    .pageConfig(ADVANCED_PAGE_KEY, {
      key: 'security-human-verification-advanced-config',
      moduleId: 'security',
      order: 20,
      resolve: () => ({
        enableHumanVerificationSection: true,
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
      }),
    }))
]

export function resolveDetailPage() {
  return null
}
