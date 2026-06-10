import {
  formatRelativeTime } from '@bias/core'
import {
  extendForum,
  getUiCopy
} from '@bias/forum'
import { buildDiscussionPath } from '@bias/discussions'
import { renderTwemojiHtml } from '@bias/emoji'
import { buildUserPath, getUserAvatarColor, getUserInitial } from '@bias/users'
import { highlightSearchText } from '@bias/search'
import GlobalSearchModal from './GlobalSearchModal.vue'
import HeaderSearchBox from './HeaderSearchBox.vue'

export const extend = [
  extendForum(registerSearchForum),
]

function registerSearchForum(forum) {
  registerSearchHeader(forum)
  registerSearchStates(forum)
  registerSearchCopy(forum)
  registerSearchSources(forum)
}

function registerSearchHeader(forum) {
  forum.searchModalProvider({
    key: 'search-modal',
    moduleId: 'search',
    order: 10,
    component: GlobalSearchModal,
    open({ initialQuery = '', initialType = 'all', modalStore }) {
      return modalStore?.show?.(
        GlobalSearchModal,
        {
          initialQuery,
          initialType,
        },
        {
          size: 'large',
          className: 'Modal--search',
        }
      )
    },
  })

  forum.headerItem({
    key: 'search-box',
    moduleId: 'search',
    placement: 'search',
    order: 10,
    component: HeaderSearchBox,
    componentProps: ({ currentSearchQuery = '', searchPreviewText = '', openSearchModal, clearSearch }) => ({
      currentSearchQuery,
      searchPreviewText,
      onOpenSearch: openSearchModal,
      onClearSearch: clearSearch,
    }),
  })

  forum.headerItem({
    key: 'mobile-drawer-search',
    moduleId: 'search',
    placement: 'mobile-drawer-actions',
    order: 10,
    icon: 'fas fa-search',
    label: ({ currentSearchQuery = '' }) => getUiCopy({
      surface: 'mobile-drawer-search-label',
      currentSearchQuery,
    })?.text || (currentSearchQuery ? `搜索：${currentSearchQuery}` : '搜索论坛'),
    onClick: ({ openSearchModal }) => openSearchModal?.(),
  })
}

function registerSearchSources(forum) {
  forum.searchSource({
    key: 'discussions',
    moduleId: 'search',
    type: 'discussions',
    label: '讨论',
    routeType: 'discussions',
    apiType: 'discussions',
    filterTarget: 'discussion',
    icon: 'far fa-comments',
    order: 10,
    buildResultItems(items, { query }) {
      return items.map(discussion => ({
        key: `discussion-${discussion.id}`,
        avatarAlt: discussion.user?.display_name || discussion.user?.username || '',
        avatarColor: getUserAvatarColor(discussion.user),
        avatarMode: true,
        avatarText: discussion.user?.avatar_url ? '' : getUserInitial(discussion.user),
        avatarUrl: discussion.user?.avatar_url || '',
        excerptHtml: buildSearchTextHtml(discussion.excerpt || '这个讨论没有更多摘要。', query, 180),
        iconClass: 'far fa-comments',
        metaItems: [
          discussion.user?.display_name || discussion.user?.username || '未知用户',
          `${discussion.comment_count || 0} 回复`,
          formatRelativeTime(discussion.last_posted_at || discussion.created_at),
        ],
        path: buildDiscussionPath(discussion),
        titleHtml: buildSearchTextHtml(discussion.title || '讨论', query, 90),
        titleText: discussion.title || '讨论',
        userLayout: false,
      }))
    },
  })

  forum.searchSource({
    key: 'posts',
    moduleId: 'search',
    type: 'posts',
    label: '帖子',
    routeType: 'posts',
    apiType: 'posts',
    filterTarget: 'post',
    icon: 'far fa-comment',
    order: 20,
    buildResultItems(items, { query }) {
      return items.map(post => ({
        key: `post-${post.id}`,
        avatarAlt: post.user?.display_name || post.user?.username || '',
        avatarColor: getUserAvatarColor(post.user),
        avatarMode: true,
        avatarText: post.user?.avatar_url ? '' : getUserInitial(post.user),
        avatarUrl: post.user?.avatar_url || '',
        excerptHtml: buildSearchTextHtml(post.excerpt || post.content || '', query, 200),
        iconClass: 'far fa-comment',
        metaItems: [
          `#${post.number}`,
          post.user?.display_name || post.user?.username || '未知用户',
          formatRelativeTime(post.created_at),
        ],
        path: `/d/${post.discussion_id}?near=${post.number}`,
        titleHtml: buildSearchTextHtml(post.discussion_title || '帖子结果', query, 90),
        titleText: post.discussion_title || '帖子结果',
        userLayout: false,
      }))
    },
  })

  forum.searchSource({
    key: 'users',
    moduleId: 'search',
    type: 'users',
    label: '用户',
    routeType: 'users',
    apiType: 'users',
    filterTarget: '',
    icon: 'far fa-user',
    order: 30,
    buildResultItems(items, { query }) {
      return items.map(user => ({
        key: `user-${user.id}`,
        avatarAlt: user.username || '',
        avatarColor: getUserAvatarColor(user),
        avatarMode: true,
        avatarText: user.avatar_url ? '' : getUserInitial(user),
        avatarUrl: user.avatar_url || '',
        excerptHtml: buildSearchTextHtml(user.bio || `@${user.username}`, query, 150),
        iconClass: 'far fa-user',
        metaItems: [
          `@${user.username}`,
          `${user.discussion_count || 0} 讨论`,
          `${user.comment_count || 0} 回复`,
        ],
        path: buildUserPath(user),
        titleHtml: buildSearchTextHtml(user.display_name || user.username || '用户', query, 80),
        titleText: user.display_name || user.username || '用户',
        userLayout: true,
      }))
    },
  })
}

function registerSearchStates(forum) {
  forum.emptyState({
    key: 'search-page-idle',
    moduleId: 'search',
    order: 70,
    surfaces: ['search-page-idle'],
    isVisible: ({ hasQuery }) => !hasQuery,
    resolve: () => ({
      text: '请输入关键词后再搜索。',
    }),
  })

  forum.emptyState({
    key: 'search-page-empty',
    moduleId: 'search',
    order: 80,
    surfaces: ['search-page-empty'],
    isVisible: ({ hasQuery }) => Boolean(hasQuery),
    resolve: () => ({
      text: '没有找到相关讨论、帖子或用户。',
    }),
  })

  forum.emptyState({
    key: 'search-modal-idle',
    moduleId: 'search',
    order: 90,
    surfaces: ['search-modal-idle'],
    isVisible: ({ hasQuery }) => !hasQuery,
    resolve: () => ({
      text: '输入关键词后即可开始搜索。你可以直接回车进入完整搜索结果页。',
    }),
  })

  forum.emptyState({
    key: 'search-modal-empty',
    moduleId: 'search',
    order: 100,
    surfaces: ['search-modal-empty'],
    isVisible: ({ hasQuery }) => Boolean(hasQuery),
    resolve: () => ({
      text: '没有找到相关结果，试试更短的关键词或切换分类。',
    }),
  })

  forum.stateBlock({
    key: 'search-page-loading',
    moduleId: 'search',
    order: 50,
    surfaces: ['search-page-loading'],
    isVisible: ({ loading, hasQuery }) => Boolean(loading) && Boolean(hasQuery),
    resolve: () => ({
      text: '搜索中...',
    }),
  })

  forum.stateBlock({
    key: 'search-modal-loading',
    moduleId: 'search',
    order: 60,
    surfaces: ['search-modal-loading'],
    isVisible: ({ loading, hasQuery }) => Boolean(loading) && Boolean(hasQuery),
    resolve: () => ({
      text: '搜索中...',
    }),
  })
}

function registerSearchCopy(forum) {
  for (const definition of searchCopyDefinitions()) {
    forum.uiCopy({
      moduleId: 'search',
      ...definition,
    })
  }
}

function searchCopyDefinitions() {
  return [
    textCopy('header-search-placeholder', 130, '搜索论坛'),
    textCopy('search-modal-close-label', 430, '关闭搜索'),
    textCopy('search-modal-title', 440, '搜索'),
    textCopy('search-modal-description', 450, '按讨论、帖子、用户快速定位内容。'),
    textCopy('search-modal-input-placeholder', 460, '输入关键词搜索讨论、帖子和用户'),
    {
      key: 'search-modal-full-results',
      order: 470,
      surfaces: ['search-modal-full-results'],
      resolve: ({ activeTabLabel }) => ({
        text: `查看${activeTabLabel || '全部'}完整结果`,
      }),
    },
    textCopy('search-modal-section-link', 475, '只看{label}'),
    textCopy('search-modal-recent-title', 476, '最近搜索'),
    {
      key: 'search-modal-recent-subtitle',
      order: 476,
      surfaces: ['search-modal-recent-subtitle'],
      resolve: ({ activeTabLabel }) => ({
        text: `只看${activeTabLabel || '当前分类'}`,
      }),
    },
    textCopy('search-modal-recent-all-subtitle', 476, '搜索全部内容'),
    textCopy('search-modal-syntax-title', 476, '搜索语法'),
    textCopy('search-page-hero-pill', 478, '全局搜索'),
    {
      key: 'mobile-drawer-search-label',
      order: 490,
      surfaces: ['mobile-drawer-search-label'],
      resolve: ({ currentSearchQuery }) => ({
        text: currentSearchQuery ? `搜索：${currentSearchQuery}` : '搜索论坛',
      }),
    },
    {
      key: 'search-page-hero-title',
      order: 479,
      surfaces: ['search-page-hero-title'],
      resolve: ({ query }) => ({
        text: `“${query || '未输入关键词'}”`,
      }),
    },
    {
      key: 'search-page-hero-description',
      order: 479,
      surfaces: ['search-page-hero-description'],
      resolve: ({ hasQuery, searchType, total, discussionTotal, postTotal, userTotal, activeLabel }) => {
        if (!hasQuery) {
          return {
            text: '支持在讨论、帖子和用户之间进行全局搜索。',
          }
        }

        if (searchType === 'all') {
          return {
            text: `共找到 ${discussionTotal + postTotal + userTotal} 条结果，已按讨论、帖子和用户分组展示。`,
          }
        }

        return {
          text: `当前显示 ${activeLabel || '结果'}结果，共 ${total || 0} 条。`,
        }
      },
    },
    {
      key: 'search-page-meta-title',
      order: 479,
      surfaces: ['search-page-meta-title'],
      resolve: ({ query }) => ({
        text: query ? `搜索：${query}` : '搜索',
      }),
    },
    {
      key: 'search-page-meta-description',
      order: 479,
      surfaces: ['search-page-meta-description'],
      resolve: ({ query, hasQuery }) => ({
        text: hasQuery ? `查看“${query}”相关的讨论、回复和用户结果。` : '搜索论坛中的讨论、回复和用户。',
      }),
    },
    textCopy('search-result-section-show-more', 479, '查看全部'),
    {
      key: 'search-page-stats-label',
      order: 479,
      surfaces: ['search-page-stats-label'],
      resolve: ({ itemKey }) => ({
        text: itemKey === 'posts' ? '帖子' : itemKey === 'users' ? '用户' : '讨论',
      }),
    },
    textCopy('search-section-discussions-title', 479, '讨论'),
    {
      key: 'search-discussion-result-replies',
      order: 479,
      surfaces: ['search-discussion-result-replies'],
      resolve: ({ count }) => ({
        text: `${count || 0} 回复`,
      }),
    },
    textCopy('search-section-posts-title', 479, '帖子'),
    textCopy('search-result-unknown-user', 479, '未知用户'),
    textCopy('search-section-users-title', 479, '用户'),
    {
      key: 'search-user-result-discussions',
      order: 479,
      surfaces: ['search-user-result-discussions'],
      resolve: ({ count }) => ({
        text: `${count || 0} 讨论`,
      }),
    },
    {
      key: 'search-user-result-replies',
      order: 479,
      surfaces: ['search-user-result-replies'],
      resolve: ({ count }) => ({
        text: `${count || 0} 回复`,
      }),
    },
    textCopy('search-filter-all-label', 479, '全部'),
    {
      key: 'search-filter-item-label',
      order: 479,
      surfaces: ['search-filter-item-label'],
      resolve: ({ label }) => ({
        text: label || '',
      }),
    },
    {
      key: 'search-stat-label',
      order: 479,
      surfaces: ['search-stat-label'],
      resolve: ({ label }) => ({
        text: label || '',
      }),
    },
    textCopy('search-filter-catalog-load-error', 479, '加载搜索过滤目录失败'),
    textCopy('search-results-load-error', 479, '加载搜索结果失败，请稍后重试'),
    {
      key: 'search-results-total-count',
      order: 479,
      surfaces: ['search-results-total-count'],
      resolve: ({ count }) => ({
        text: String(Number(count || 0)),
      }),
    },
    {
      key: 'search-results-source-count',
      order: 479,
      surfaces: ['search-results-source-count'],
      resolve: ({ count }) => ({
        text: String(Number(count || 0)),
      }),
    },
    textCopy('header-search-open-label', 1060, '打开全局搜索'),
    textCopy('header-search-clear-label', 1070, '清除搜索'),
  ]
}

function textCopy(key, order, text) {
  return {
    key,
    order,
    surfaces: [key],
    resolve: () => ({ text }),
  }
}

function buildSearchTextHtml(value, query, limit) {
  return renderTwemojiHtml(highlightSearchText(value, query, limit))
}
