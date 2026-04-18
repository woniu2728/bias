import api from '@/api'
export { EMOJI_GROUPS, searchEmojiItems } from '@/utils/emojiData'

export const COMPOSER_EMOJI_PICKER_WIDTH = 420

const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']

export async function uploadComposerFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  return api.post('/uploads', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

export async function fetchComposerPreview(content) {
  return api.post('/preview', {
    content
  })
}

export function buildComposerToolReplacement(tool, selected) {
  if (tool.key === 'link') {
    return selected ? `[${selected}](https://)` : '[链接文字](https://)'
  }
  if (tool.key === 'quote') {
    return prefixLines(selected || '引用内容', '> ')
  }
  if (tool.key === 'bullets') {
    return prefixLines(selected || '列表项', '- ')
  }
  if (tool.key === 'ordered') {
    return prefixOrderedLines(selected || '列表项')
  }

  const before = tool.before || ''
  const after = tool.after || ''
  return `${before}${selected || defaultToolText(tool)}${after}`
}

export function defaultToolCursorOffset(tool) {
  const replacement = buildComposerToolReplacement(tool, '')
  if (tool.key === 'link') return replacement.indexOf('https://')
  return replacement.length
}

export function replaceSelection(content, start, end, replacement) {
  return `${content.slice(0, start)}${replacement}${content.slice(end)}`
}

export function buildUploadedFileMarkdown(fileName, url, options = {}) {
  const { image = false } = options
  const fallback = image ? '图片' : '附件'
  const safeLabel = sanitizeMarkdownLabel(stripFileExtension(fileName), fallback)
  return image ? `![${safeLabel}](${url})` : `[${safeLabel}](${url})`
}

export function detectMentionQuery(content, cursorPosition) {
  const safeContent = String(content || '')
  const safeCursor = Math.max(0, Math.min(cursorPosition ?? safeContent.length, safeContent.length))
  const beforeCursor = safeContent.slice(0, safeCursor)
  const match = beforeCursor.match(/(^|[\s(])@([A-Za-z0-9_.-]{0,30})$/)
  if (!match) return null

  const query = match[2] || ''
  const start = safeCursor - query.length - 1
  return {
    query,
    start,
    end: safeCursor
  }
}

export function detectEmojiQuery(content, cursorPosition) {
  const safeContent = String(content || '')
  const safeCursor = Math.max(0, Math.min(cursorPosition ?? safeContent.length, safeContent.length))
  const beforeCursor = safeContent.slice(0, safeCursor)
  const match = beforeCursor.match(/(^|[\s(\[{"'“‘]):([A-Za-z0-9_+\-\u4e00-\u9fa5]{0,32})$/u)
  if (!match) return null

  const query = match[2] || ''
  const start = safeCursor - query.length - 1
  return {
    query,
    start,
    end: safeCursor
  }
}

export function getTextareaCaretCoordinates(textarea, position) {
  if (!textarea || typeof window === 'undefined' || typeof document === 'undefined') {
    return null
  }

  const value = String(textarea.value || '')
  const safePosition = Math.max(0, Math.min(position ?? value.length, value.length))
  const style = window.getComputedStyle(textarea)
  const mirror = document.createElement('div')
  const marker = document.createElement('span')
  const mirroredProperties = [
    'boxSizing',
    'width',
    'paddingTop',
    'paddingRight',
    'paddingBottom',
    'paddingLeft',
    'borderTopWidth',
    'borderRightWidth',
    'borderBottomWidth',
    'borderLeftWidth',
    'borderTopStyle',
    'borderRightStyle',
    'borderBottomStyle',
    'borderLeftStyle',
    'fontFamily',
    'fontSize',
    'fontStyle',
    'fontVariant',
    'fontWeight',
    'letterSpacing',
    'lineHeight',
    'textAlign',
    'textIndent',
    'textTransform',
    'whiteSpace',
    'wordBreak',
    'overflowWrap',
    'tabSize'
  ]

  mirror.setAttribute('aria-hidden', 'true')
  mirror.style.position = 'fixed'
  mirror.style.top = '0'
  mirror.style.left = '-9999px'
  mirror.style.visibility = 'hidden'
  mirror.style.pointerEvents = 'none'
  mirror.style.whiteSpace = 'pre-wrap'
  mirror.style.wordBreak = 'break-word'
  mirror.style.overflowWrap = 'break-word'
  mirror.style.overflow = 'hidden'

  mirroredProperties.forEach(property => {
    mirror.style[property] = style[property]
  })

  mirror.textContent = value.slice(0, safePosition)
  marker.textContent = value.slice(safePosition) || '.'
  mirror.appendChild(marker)
  document.body.appendChild(mirror)

  const rect = textarea.getBoundingClientRect()
  const lineHeight = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.4 || 20
  const coordinates = {
    left: rect.left + marker.offsetLeft - textarea.scrollLeft,
    top: rect.top + marker.offsetTop - textarea.scrollTop,
    lineHeight
  }

  mirror.remove()
  return coordinates
}

export function buildMentionReplacement(username) {
  return `@${String(username || '').trim()} `
}

export function buildEmojiReplacement(emoji) {
  return `${String(emoji || '').trim()} `
}

export function buildMentionTrigger(content, start) {
  const safeContent = String(content || '')
  const safeStart = Math.max(0, Math.min(start ?? safeContent.length, safeContent.length))
  const previousCharacter = safeContent.slice(Math.max(0, safeStart - 1), safeStart)
  return /[\s(]/.test(previousCharacter) || !previousCharacter ? '@' : ' @'
}

export function isImageFile(file) {
  if (!file) return false
  if (file.type?.startsWith('image/')) return true

  const name = String(file.name || '').toLowerCase()
  return IMAGE_EXTENSIONS.some(extension => name.endsWith(extension))
}

export function getComposerErrorMessage(error, fallback) {
  return (
    error?.response?.data?.error ||
    error?.response?.data?.detail ||
    error?.message ||
    fallback
  )
}

function prefixLines(content, prefix) {
  return content
    .split('\n')
    .map(line => `${prefix}${line || '内容'}`)
    .join('\n')
}

function prefixOrderedLines(content) {
  return content
    .split('\n')
    .map((line, index) => `${index + 1}. ${line || '内容'}`)
    .join('\n')
}

function defaultToolText(tool) {
  if (tool.key === 'code') return 'code'
  if (tool.key === 'heading') return '标题'
  return '文本'
}

function sanitizeMarkdownLabel(value, fallback) {
  const sanitized = String(value || '')
    .replace(/[\[\]\r\n]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  return sanitized || fallback
}

function stripFileExtension(fileName) {
  return String(fileName || '').replace(/\.[^.]+$/, '')
}
