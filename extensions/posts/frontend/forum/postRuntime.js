import { renderTwemojiHtml } from '@bias/emoji'
import { normalizeUser } from '@bias/users'

export function normalizePost(post = {}) {
  return {
    ...post,
    content_html: renderTwemojiHtml(post.content_html || ''),
    user: post.user ? normalizeUser(post.user) : null,
    discussion: post.discussion || (post.discussion_id ? {
      id: post.discussion_id,
      title: post.discussion_title || '讨论',
    } : null),
  }
}
