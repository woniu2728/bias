export { EMOJI_GROUPS, searchEmojiItems } from './emojiData.js'

export function renderTwemojiHtml(html = '') {
  return String(html || '')
}

export function renderTwemojiText(text = '') {
  return escapeHtml(text)
}

export function setTwemojiBaseUrl() {}

export function setTwemojiEnabled() {}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
