import { renderTwemojiHtml } from '@bias/emoji'
import { normalizeUser } from '@bias/users'

function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderFallbackContent(value = '') {
  return escapeHtml(value).replace(/\r\n|\r|\n/g, '<br>')
}

export function normalizePost(post = {}) {
  const contentHtml = post.content_html || renderFallbackContent(post.content)

  return {
    ...post,
    content_html: renderTwemojiHtml(contentHtml),
    user: post.user ? normalizeUser(post.user) : null,
    discussion: post.discussion || (post.discussion_id ? {
      id: post.discussion_id,
      title: post.discussion_title || '讨论',
    } : null),
  }
}
