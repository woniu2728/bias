export const defaultThemeTokens = {
  id: 'default',
  name: 'Default',
  className: 'bias-theme-default',
  colorScheme: 'light',
}

export function normalizeThemeTokens(tokens = {}) {
  const payload = tokens && typeof tokens === 'object' ? tokens : {}
  return {
    ...defaultThemeTokens,
    ...payload,
    id: String(payload.id || defaultThemeTokens.id).trim() || defaultThemeTokens.id,
    className: String(payload.className || defaultThemeTokens.className).trim() || defaultThemeTokens.className,
    colorScheme: String(payload.colorScheme || defaultThemeTokens.colorScheme).trim() || defaultThemeTokens.colorScheme,
  }
}
