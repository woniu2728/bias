import api from '@/api'

export const EMOJI_GROUPS = [
  {
    key: 'common',
    label: '常用',
    emojis: ['😀', '😁', '😂', '😊', '😉', '😍', '😘', '🤔', '😎', '😭', '😡', '👍', '👎', '👏', '🙏', '🎉']
  },
  {
    key: 'people',
    label: '人物',
    emojis: ['🙂', '😇', '🥳', '😴', '🤗', '🤯', '😅', '🤩', '😬', '🤓', '😷', '🤝', '💪', '🙌', '👀', '🫡']
  },
  {
    key: 'nature',
    label: '自然',
    emojis: ['🌞', '🌙', '⭐', '🔥', '🌈', '☁️', '🌧️', '❄️', '🌸', '🌻', '🍀', '🌲', '🐶', '🐱', '🦊', '🐼']
  },
  {
    key: 'objects',
    label: '物件',
    emojis: ['📌', '📎', '📷', '💻', '⌚', '📱', '🎧', '🎁', '📚', '✏️', '🧩', '⚙️', '🔒', '🔔', '❤️', '✅']
  }
]

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

export function buildMentionReplacement(username) {
  return `@${String(username || '').trim()} `
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
