export function resolveTagsMetaPayload({
  descriptionText = '',
  tagCount = 0,
  titleText = '',
}) {
  return {
    title: titleText || '全部标签',
    description: descriptionText || (Number(tagCount) > 0
      ? `浏览 ${Number(tagCount)} 个论坛标签，按主题发现相关讨论。`
      : '浏览论坛标签，按主题发现相关讨论。'),
    canonicalUrl: '/tags',
  }
}
