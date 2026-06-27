import api from '../api/index.js'

export const BASE_COMPOSER_TOOLS = [
  { key: 'heading', title: '标题', label: 'H', before: '## ', after: '', order: 20 },
  { key: 'bold', title: '加粗', label: 'B', before: '**', after: '**', order: 30 },
  { key: 'italic', title: '斜体', label: 'I', before: '*', after: '*', order: 40 },
  { key: 'strike', title: '删除线', label: 'S', before: '~~', after: '~~', order: 50 },
  { key: 'quote', title: '引用', icon: 'fas fa-quote-left', order: 60 },
  { key: 'spoiler', title: '提示/警告', icon: 'fas fa-exclamation-triangle', before: '> **提示：** ', after: '', order: 70 },
  { key: 'code', title: '代码', icon: 'fas fa-code', before: '`', after: '`', order: 80 },
  { key: 'link', title: '链接', icon: 'fas fa-link', order: 90 },
  { key: 'bullets', title: '无序列表', icon: 'fas fa-list-ul', order: 110 },
  { key: 'ordered', title: '有序列表', icon: 'fas fa-list-ol', order: 120 }
]

export async function fetchComposerPreview(content) {
  return api.post('/preview', {
    content
  })
}

export function buildComposerToolReplacement(tool, selected) {
  if (typeof tool?.replacement === 'function') {
    return tool.replacement(selected, tool)
  }
  if (typeof tool?.replacement === 'string') {
    return tool.replacement
  }
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
  if (typeof tool?.cursorOffset === 'number') {
    return tool.cursorOffset
  }
  const replacement = buildComposerToolReplacement(tool, '')
  if (tool.key === 'link') return replacement.indexOf('https://')
  return replacement.length
}

export function replaceSelection(content, start, end, replacement) {
  return `${content.slice(0, start)}${replacement}${content.slice(end)}`
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
  if (tool.placeholder) return tool.placeholder
  if (tool.key === 'code') return 'code'
  if (tool.key === 'heading') return '标题'
  return '文本'
}
