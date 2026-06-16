export function shouldUseTurnstile(mode, settings = {}) {
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

export function buildHumanVerificationPayload({ token } = {}) {
  return {
    human_verification_token: token || undefined,
  }
}
