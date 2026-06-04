import {
  registerEmptyState,
  registerForumNavItem,
  registerStateBlock,
  registerUiCopy,
} from '@/forum/registry'

export async function bootForumExtension() {
  registerForumNavItem({
    key: 'tags',
    moduleId: 'tags',
    to: '/tags',
    icon: 'fas fa-tags',
    label: '全部标签',
    description: '按标签浏览论坛主题。',
    section: 'primary',
    order: 30,
    surfaces: ['primary-nav', 'discussion-sidebar', 'mobile-drawer']
  })

  registerEmptyState({
    key: 'tags-page-empty',
    moduleId: 'tags',
    order: 50,
    surfaces: ['tags-page-empty'],
    isVisible: ({ tags }) => Array.isArray(tags) && tags.length === 0,
    resolve: () => ({
      text: '暂无标签',
    }),
  })

  registerEmptyState({
    key: 'tag-last-discussion-empty',
    moduleId: 'tags',
    order: 60,
    surfaces: ['tag-last-discussion-empty'],
    isVisible: ({ tag }) => !tag?.last_posted_discussion,
    resolve: () => ({
      text: '暂无讨论',
    }),
  })

  registerStateBlock({
    key: 'tags-page-loading',
    moduleId: 'tags',
    order: 40,
    surfaces: ['tags-page-loading'],
    isVisible: ({ loading }) => Boolean(loading),
    resolve: () => ({
      text: '加载中...',
    }),
  })

  registerUiCopy({
    key: 'search-modal-popular-tags-title',
    moduleId: 'tags',
    order: 476,
    surfaces: ['search-modal-popular-tags-title'],
    resolve: () => ({
      text: '热门标签',
    }),
  })

  registerUiCopy({
    key: 'search-modal-tag-subtitle',
    moduleId: 'tags',
    order: 476,
    surfaces: ['search-modal-tag-subtitle'],
    resolve: ({ count }) => ({
      text: `${Number(count || 0)} 条讨论`,
    }),
  })

  registerUiCopy({
    key: 'tags-page-hero-title',
    moduleId: 'tags',
    order: 479,
    surfaces: ['tags-page-hero-title'],
    resolve: () => ({
      text: '全部标签',
    }),
  })

  registerUiCopy({
    key: 'tags-page-hero-description',
    moduleId: 'tags',
    order: 479,
    surfaces: ['tags-page-hero-description'],
    resolve: ({ tagCount }) => ({
      text: Number(tagCount || 0) > 0
        ? `浏览 ${tagCount} 个论坛标签，按主题发现相关讨论。`
        : '浏览论坛标签，按主题发现相关讨论。',
    }),
  })

  registerUiCopy({
    key: 'discussion-list-sidebar-tags-link',
    moduleId: 'tags',
    order: 479,
    surfaces: ['discussion-list-sidebar-tags-link'],
    resolve: () => ({
      text: '标签',
    }),
  })

  registerUiCopy({
    key: 'discussion-list-sidebar-more-tags-link',
    moduleId: 'tags',
    order: 479,
    surfaces: ['discussion-list-sidebar-more-tags-link'],
    resolve: () => ({
      text: '更多标签',
    }),
  })

  registerUiCopy({
    key: 'mobile-drawer-all-tags',
    moduleId: 'tags',
    order: 530,
    surfaces: ['mobile-drawer-all-tags'],
    resolve: () => ({
      text: '全部标签',
    }),
  })
}
