export function buildUploadedFileMarkdown(fileName, url, options = {}) {
  const { image = false } = options
  const fallback = image ? '图片' : '附件'
  const safeLabel = sanitizeMarkdownLabel(stripFileExtension(fileName), fallback)
  return image ? `![${safeLabel}](${url})` : `[${safeLabel}](${url})`
}

export function sanitizeMarkdownLabel(value, fallback = '') {
  const sanitized = String(value || '')
    .replace(/[[\]\r\n]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  return sanitized || fallback
}

export function stripFileExtension(fileName) {
  return String(fileName || '').replace(/\.[^.]+$/, '')
}
