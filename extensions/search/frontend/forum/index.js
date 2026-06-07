import {
  buildDiscussionPath,
  buildUserPath,
  extendForum,
  formatRelativeTime,
  getUserAvatarColor,
  getUserInitial,
  highlightSearchText,
  renderTwemojiHtml,
} from '@bias/forum'

export const extend = [
  extendForum(registerSearchForum),
]

function registerSearchForum(forum) {
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

function buildSearchTextHtml(value, query, limit) {
  return renderTwemojiHtml(highlightSearchText(value, query, limit))
}
