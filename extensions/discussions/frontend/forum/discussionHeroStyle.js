export function buildDiscussionHeroColorStyle(color) {
  const normalized = String(color || '').trim() || '#f2554b'
  return {
    '--discussion-hero-color': normalized,
    '--discussion-hero-color-dark': shadeColor(normalized, -12),
    '--discussion-hero-contrast': getContrastColor(normalized)
  }
}

function getContrastColor(color) {
  const hex = String(color || '').trim().replace('#', '')
  if (!/^[\da-fA-F]{6}$/.test(hex)) return '#ffffff'

  const red = parseInt(hex.slice(0, 2), 16)
  const green = parseInt(hex.slice(2, 4), 16)
  const blue = parseInt(hex.slice(4, 6), 16)
  const brightness = (red * 299 + green * 587 + blue * 114) / 1000

  return brightness >= 150 ? '#223245' : '#ffffff'
}

function shadeColor(color, percent) {
  const hex = String(color || '').trim().replace('#', '')
  if (!/^[\da-fA-F]{6}$/.test(hex)) return color || '#f2554b'

  const amount = Number(percent) / 100
  const channel = start => {
    const value = parseInt(hex.slice(start, start + 2), 16)
    const adjusted = amount >= 0
      ? value + (255 - value) * amount
      : value * (1 + amount)
    return Math.max(0, Math.min(255, Math.round(adjusted)))
      .toString(16)
      .padStart(2, '0')
  }

  return `#${channel(0)}${channel(2)}${channel(4)}`
}
