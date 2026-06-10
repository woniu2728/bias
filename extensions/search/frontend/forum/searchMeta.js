export function resolveSearchMetaPayload({
  query,
  searchType,
  titleText,
  descriptionText,
}) {
  const normalizedQuery = String(query || '').trim()

  return {
    title: titleText || (normalizedQuery ? `搜索：${normalizedQuery}` : '搜索'),
    description: descriptionText || (normalizedQuery
      ? `查看“${normalizedQuery}”相关的讨论、回复和用户结果。`
      : '搜索论坛中的讨论、回复和用户。'),
    canonicalUrl: `/search${normalizedQuery
      ? `?q=${encodeURIComponent(normalizedQuery)}&type=${encodeURIComponent(searchType || 'all')}`
      : ''}`,
  }
}
