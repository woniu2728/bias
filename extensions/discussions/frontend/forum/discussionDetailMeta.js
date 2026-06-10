export function resolveDiscussionDetailMetaPayload(discussion) {
  if (!discussion) return null

  const firstPostText = String(discussion.first_post?.content || discussion.excerpt || '')
    .replace(/\s+/g, ' ')
    .trim()

  return {
    title: discussion.title,
    description: firstPostText.slice(0, 160),
    ogType: 'article',
    canonicalUrl: `/d/${discussion.id}`,
  }
}
