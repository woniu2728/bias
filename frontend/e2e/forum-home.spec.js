import { expect, test } from '@playwright/test'

const forumSettings = {
  forum_title: 'Bias E2E Forum',
  forum_description: 'Browser flow fixture',
  enabled_modules: ['users', 'discussions', 'posts', 'realtime', 'search', 'tags', 'notifications'],
  enabled_extensions: [
    {
      id: 'users',
      frontend_forum_entry: 'extensions/users/frontend/forum/index.js',
      frontend_routes: [
        {
          path: '/login',
          name: 'login',
          component: './AuthRouteView.vue',
          frontend: 'forum',
          module_id: 'users',
        },
        {
          path: '/register',
          name: 'register',
          component: './AuthRouteView.vue',
          frontend: 'forum',
          module_id: 'users',
        },
        {
          path: '/forgot-password',
          name: 'forgot-password',
          component: './AuthRouteView.vue',
          frontend: 'forum',
          module_id: 'users',
        },
        {
          path: '/verify-email',
          name: 'verify-email',
          component: './VerifyEmailView.vue',
          frontend: 'forum',
          module_id: 'users',
        },
        {
          path: '/reset-password',
          name: 'reset-password',
          component: './ResetPasswordView.vue',
          frontend: 'forum',
          module_id: 'users',
        },
        {
          path: '/profile',
          name: 'profile',
          component: './ProfileView.vue',
          frontend: 'forum',
          module_id: 'users',
          requires_auth: true,
        },
        {
          path: '/u/:id',
          name: 'user-profile',
          component: './ProfileView.vue',
          frontend: 'forum',
          module_id: 'users',
        },
      ],
    },
    {
      id: 'discussions',
      frontend_forum_entry: 'extensions/discussions/frontend/forum/index.js',
      frontend_routes: [
        {
          path: '/',
          name: 'home',
          component: './DiscussionListView.vue',
          frontend: 'forum',
          module_id: 'discussions',
        },
        {
          path: '/d/:id',
          name: 'discussion-detail',
          component: './DiscussionDetailView.vue',
          frontend: 'forum',
          module_id: 'discussions',
        },
        {
          path: '/discussions/create',
          name: 'discussion-create',
          component: './DiscussionCreateView.vue',
          frontend: 'forum',
          module_id: 'discussions',
          requires_auth: true,
        },
      ],
    },
    {
      id: 'posts',
      frontend_forum_entry: 'extensions/posts/frontend/forum/index.js',
      frontend_routes: [],
    },
    {
      id: 'search',
      frontend_forum_entry: 'extensions/search/frontend/forum/index.js',
      frontend_routes: [
        {
          path: '/search',
          name: 'search',
          component: './SearchResultsView.vue',
          frontend: 'forum',
          module_id: 'search',
        },
      ],
    },
    {
      id: 'tags',
      frontend_forum_entry: 'extensions/tags/frontend/forum/index.js',
      frontend_routes: [
        {
          path: '/tags',
          name: 'tags',
          component: './TagsView.vue',
          frontend: 'forum',
          module_id: 'tags',
          preloads: [
            {
              href: '/api/tags?include=children,lastPostedDiscussion,parent&include_children=true',
            },
          ],
        },
        {
          path: '/t/:slug',
          name: 'tag-detail',
          component: 'extensions/discussions/frontend/forum/DiscussionListView.vue',
          frontend: 'forum',
          module_id: 'tags',
          preloads: [
            {
              href: '/api/tags/slug/:slug',
            },
            {
              href: '/api/tags?include=children,lastPostedDiscussion,parent&include_children=true',
            },
          ],
        },
      ],
    },
    {
      id: 'notifications',
      frontend_forum_entry: 'extensions/notifications/frontend/forum/index.js',
      frontend_routes: [
        {
          path: '/notifications',
          name: 'notifications',
          component: './NotificationView.vue',
          frontend: 'forum',
          module_id: 'notifications',
          requires_auth: true,
        },
      ],
    },
    {
      id: 'realtime',
      frontend_routes: [],
    },
  ],
  extensions: {
    tags: {
      min_primary_tags: 1,
      max_primary_tags: 1,
      min_secondary_tags: 0,
      max_secondary_tags: 2,
    },
  },
}

const alice = {
  id: 7,
  username: 'alice',
  display_name: 'Alice',
  avatar_url: '',
  is_staff: false,
}

const bob = {
  id: 8,
  username: 'bob',
  display_name: 'Bob',
  avatar_url: '',
  is_staff: false,
}

const charlie = {
  id: 9,
  username: 'charlie',
  display_name: 'Charlie',
  avatar_url: '',
  is_staff: false,
  bio: 'Charlie profile biography',
  email: 'charlie@example.test',
  color: '#4d698e',
  joined_at: '2026-06-01T08:00:00Z',
  last_seen_at: '2026-06-30T10:15:00Z',
  discussion_count: 2,
  comment_count: 4,
  is_email_confirmed: true,
  is_suspended: false,
  forum_permissions: ['startDiscussion', 'discussion.reply', 'discussion.typing'],
}

const discussionListPayload = {
  data: [
    {
      id: 101,
      title: 'Browser E2E discussion list renders',
      slug: 'browser-e2e-discussion-list-renders',
      created_at: '2026-06-30T08:00:00Z',
      last_posted_at: '2026-06-30T09:00:00Z',
      comment_count: 3,
      participant_count: 2,
      unread_count: 0,
      is_sticky: false,
      is_locked: false,
      is_hidden: false,
      can_reply: true,
      can_edit: false,
      can_delete: false,
      can_hide: false,
      user: alice,
      tags: [
        {
          id: 1,
          name: 'General',
          slug: 'general',
          color: '#2d8fdd',
          is_primary: true,
          parent_id: null,
          children: [],
        },
        {
          id: 3,
          name: 'Browser',
          slug: 'browser',
          color: '#8e44ad',
          is_primary: false,
          parent_id: 1,
          children: [],
        },
      ],
      last_post: {
        id: 501,
        number: 3,
        created_at: '2026-06-30T09:00:00Z',
        user: bob,
      },
    },
  ],
  total: 1,
  available_sorts: [
    { value: 'latest', label: '最新回复' },
    { value: 'newest', label: '最新发布' },
  ],
  available_filters: [
    { value: 'all', label: '全部讨论' },
  ],
}

const tagTreePayload = {
  data: [
    {
      id: 1,
      name: 'General',
      slug: 'general',
      description: 'General forum discussions',
      color: '#2d8fdd',
      icon: 'fas fa-comments',
      position: 1,
      is_primary: true,
      is_child: false,
      parent_id: null,
      discussion_count: 2,
      children: [
        {
          id: 3,
          name: 'Browser',
          slug: 'browser',
          description: 'Browser automation cases',
          color: '#8e44ad',
          icon: 'fas fa-window-maximize',
          position: 1,
          is_primary: false,
          is_child: true,
          parent_id: 1,
          discussion_count: 1,
          children: [],
          last_posted_discussion: discussionListPayload.data[0],
        },
      ],
      last_posted_discussion: discussionListPayload.data[0],
    },
    {
      id: 2,
      name: 'Support',
      slug: 'support',
      description: 'Support questions',
      color: '#16a085',
      icon: 'fas fa-life-ring',
      position: null,
      is_primary: false,
      is_child: false,
      parent_id: null,
      discussion_count: 4,
      children: [],
      last_posted_discussion: null,
    },
  ],
}

const tagDetailPayload = tagTreePayload.data[0]

const taggedDiscussionListPayload = {
  ...discussionListPayload,
  data: [
    {
      ...discussionListPayload.data[0],
      title: 'Browser tag filtered discussion',
      slug: 'browser-tag-filtered-discussion',
    },
  ],
}

const discussionDetailPayload = {
  id: 101,
  title: 'Browser E2E discussion list renders',
  slug: 'browser-e2e-discussion-list-renders',
  created_at: '2026-06-30T08:00:00Z',
  last_posted_at: '2026-06-30T09:00:00Z',
  last_post_number: 2,
  comment_count: 2,
  participant_count: 2,
  unread_count: 0,
  last_read_post_number: 0,
  is_sticky: false,
  is_locked: false,
  is_hidden: false,
  can_reply: true,
  can_edit: false,
  can_delete: false,
  can_hide: false,
  user: alice,
  last_post: {
    id: 502,
    number: 2,
    created_at: '2026-06-30T09:00:00Z',
    user: bob,
  },
}

const postStreamPayload = {
  data: [
    {
      id: 501,
      discussion_id: 101,
      number: 1,
      type: 'comment',
      content: 'First browser detail post',
      content_html: '<p>First browser detail post</p>',
      created_at: '2026-06-30T08:00:00Z',
      is_hidden: false,
      can_edit: false,
      can_delete: false,
      can_hide: false,
      user: alice,
    },
    {
      id: 502,
      discussion_id: 101,
      number: 2,
      type: 'comment',
      content: 'Reply rendered from post stream',
      content_html: '<p>Reply rendered from post stream</p>',
      created_at: '2026-06-30T09:00:00Z',
      is_hidden: false,
      can_edit: false,
      can_delete: false,
      can_hide: false,
      user: bob,
    },
  ],
  total: 2,
  current_start: 1,
  current_end: 2,
}

const createdDiscussion = {
  id: 202,
  title: 'Discussion created through Playwright',
  slug: 'discussion-created-through-playwright',
  created_at: '2026-06-30T10:30:00Z',
  last_posted_at: '2026-06-30T10:30:00Z',
  last_post_number: 1,
  comment_count: 1,
  participant_count: 1,
  unread_count: 0,
  last_read_post_number: 0,
  is_sticky: false,
  is_locked: false,
  is_hidden: false,
  can_reply: true,
  can_edit: true,
  can_delete: true,
  can_hide: false,
  user: charlie,
  tags: [
    tagTreePayload.data[0],
    tagTreePayload.data[0].children[0],
  ],
  last_post: {
    id: 601,
    number: 1,
    created_at: '2026-06-30T10:30:00Z',
    user: charlie,
  },
}

const createdDiscussionPostsPayload = {
  data: [
    {
      id: 601,
      discussion_id: 202,
      number: 1,
      type: 'comment',
      content: 'Opening post created through Playwright',
      content_html: '<p>Opening post created through Playwright</p>',
      created_at: '2026-06-30T10:30:00Z',
      is_hidden: false,
      can_edit: true,
      can_delete: true,
      can_hide: false,
      user: charlie,
    },
  ],
  total: 1,
  current_start: 1,
  current_end: 1,
}

const searchPayload = {
  total: 3,
  discussions: [
    {
      id: 101,
      title: 'Browser E2E discussion list renders',
      slug: 'browser-e2e-discussion-list-renders',
      excerpt: 'Browser search discussion excerpt',
      created_at: '2026-06-30T08:00:00Z',
      last_posted_at: '2026-06-30T09:00:00Z',
      comment_count: 3,
      user: alice,
    },
  ],
  posts: [
    {
      id: 502,
      discussion_id: 101,
      discussion_title: 'Browser E2E discussion list renders',
      number: 2,
      excerpt: 'Browser search post excerpt',
      content: 'Browser search post excerpt',
      created_at: '2026-06-30T09:00:00Z',
      user: bob,
    },
  ],
  users: [
    {
      id: 7,
      username: 'alice',
      display_name: 'Alice Searcher',
      avatar_url: '',
      bio: 'Browser search user profile',
      discussion_count: 1,
      comment_count: 2,
    },
  ],
  discussion_total: 1,
  post_total: 1,
  user_total: 1,
}

const profilePreferencesPayload = {
  values: {
    notify_post_reply: true,
    notify_user_mentioned: false,
  },
  ui_values: {},
  definitions: [
    {
      key: 'notify_post_reply',
      label: '回复通知',
      description: '有人回复你的帖子时通知你。',
      category: 'notifications',
    },
    {
      key: 'notify_user_mentioned',
      label: '提及通知',
      description: '有人提及你时通知你。',
      category: 'notifications',
    },
  ],
}

const profileDiscussionPayload = {
  data: [
    {
      ...discussionListPayload.data[0],
      title: 'Charlie profile discussion',
      slug: 'charlie-profile-discussion',
      user: charlie,
      comment_count: 5,
    },
  ],
  total: 1,
}

const profilePostsPayload = {
  data: [
    {
      id: 701,
      discussion_id: 101,
      number: 4,
      type: 'comment',
      content: 'Profile reply rendered from author feed',
      content_html: '<p>Profile reply rendered from author feed</p>',
      created_at: '2026-06-30T10:45:00Z',
      is_hidden: false,
      can_edit: true,
      can_delete: true,
      can_hide: false,
      user: charlie,
      discussion: {
        id: 101,
        title: 'Browser E2E discussion list renders',
      },
    },
  ],
  total: 1,
}

const browserAvatarDataUrl = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII='

const baseNotifications = [
  {
    id: 301,
    type: 'postReply',
    subject_type: 'post',
    subject_id: 502,
    data: {
      discussion_id: 101,
      discussion_title: 'Browser E2E discussion list renders',
      post_id: 502,
      post_number: 2,
    },
    created_at: '2026-06-30T09:10:00Z',
    is_read: false,
    from_user: bob,
  },
  {
    id: 302,
    type: 'userSuspended',
    subject_type: 'user',
    subject_id: 9,
    data: {
      suspend_message: 'Browser account moderation notice',
    },
    created_at: '2026-06-30T07:30:00Z',
    is_read: true,
    from_user: alice,
  },
]

function cloneNotification(notification) {
  return {
    ...notification,
    data: { ...(notification.data || {}) },
    from_user: notification.from_user ? { ...notification.from_user } : null,
  }
}

function buildPostStreamPayload(extraPosts = []) {
  const posts = [
    ...postStreamPayload.data,
    ...extraPosts,
  ]

  return {
    ...postStreamPayload,
    data: posts,
    total: posts.length,
    current_start: posts[0]?.number || 0,
    current_end: posts[posts.length - 1]?.number || 0,
  }
}

test.beforeEach(async ({ page }) => {
  const browserErrors = []
  const createdReplies = []
  let notificationItems = baseNotifications.map(cloneNotification)
  let currentUser = { ...charlie }

  await page.exposeFunction('__biasE2ESetEmailUnconfirmed', () => {
    currentUser = {
      ...currentUser,
      is_email_confirmed: false,
    }
  })
  await page.exposeFunction('__biasE2ESetEmailConfirmed', () => {
    currentUser = {
      ...currentUser,
      is_email_confirmed: true,
    }
  })

  function buildNotificationListPayload(params = {}) {
    let items = notificationItems.map(cloneNotification)
    if (params.type) {
      items = items.filter(item => item.type === params.type)
    }
    if (params.isRead !== null && params.isRead !== undefined) {
      items = items.filter(item => item.is_read === params.isRead)
    }

    const allUnreadCount = notificationItems.filter(item => !item.is_read).length
    return {
      data: items,
      total: items.length,
      limit: Number(params.limit || 20),
      unread_count: allUnreadCount,
      type_counts: {
        postReply: notificationItems.filter(item => item.type === 'postReply').length,
        userSuspended: notificationItems.filter(item => item.type === 'userSuspended').length,
      },
      unread_type_counts: {
        postReply: notificationItems.filter(item => item.type === 'postReply' && !item.is_read).length,
        userSuspended: notificationItems.filter(item => item.type === 'userSuspended' && !item.is_read).length,
      },
    }
  }

  function buildNotificationStatsPayload() {
    const total = notificationItems.length
    const unread = notificationItems.filter(item => !item.is_read).length
    return {
      total,
      unread_count: unread,
      read_count: Math.max(0, total - unread),
    }
  }

  page.on('pageerror', error => {
    browserErrors.push(error.message)
  })
  page.on('console', message => {
    if (message.type() !== 'error') return
    const text = message.text()
    if (text.includes('WebSocket connection')) return
    if (text.includes('Failed to load resource') && text.includes('/ws/online/')) return
    if (text.includes('Failed to load resource') && text.includes('/ws/notifications/')) return
    if (
      text.includes('Failed to load resource')
      && (
        text.includes('/api/users/login')
        || text.includes('/api/users/register')
        || text.includes('/api/users/verify-email')
        || text.includes('/api/users/reset-password')
        || text.includes('/api/users/me/resend-email-verification')
        || text.includes('/api/users/9/password')
      )
    ) return
    if (text.includes('WebSocket错误: Event')) return
    browserErrors.push(text)
  })

  page.e2eAuthenticated = false
  await page.route('**/*', route => {
    const url = new URL(route.request().url())
    if (!url.pathname.startsWith('/api/')) {
      return route.continue()
    }
    const json = (body, options = {}) => route.fulfill({
      status: options.status || 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
      headers: options.headers || {},
    })

    if (url.pathname === '/api/csrf') {
      return json({ ok: true }, {
        headers: {
          'Set-Cookie': 'csrftoken=e2e-token; Path=/',
        },
      })
    }
    if (url.pathname === '/api/forum') {
      return json(forumSettings)
    }
    if (url.pathname === '/api/forum/theme') {
      return json({ theme: { id: 'default', className: 'theme-default', colorScheme: 'light' } })
    }
    if (url.pathname === '/api/users/session') {
      if (page.e2eAuthenticated) {
        return json({ authenticated: true, user: currentUser })
      }
      return json({ authenticated: false, user: null })
    }
    if (url.pathname === '/api/users/login' && route.request().method() === 'POST') {
      const requestBody = route.request().postDataJSON()
      if (requestBody.identification === 'wrong@example.test') {
        return json({ error: '用户名或密码错误' }, { status: 401 })
      }
      expect(requestBody).toMatchObject({
        identification: 'charlie@example.test',
        password: 'correct-password',
      })
      page.e2eAuthenticated = true
      currentUser = { ...charlie }
      return json({ ok: true })
    }
    if (url.pathname === '/api/users/register' && route.request().method() === 'POST') {
      const requestBody = route.request().postDataJSON()
      if (requestBody.email === 'taken@example.test') {
        return json({ error: '邮箱已被使用' }, { status: 400 })
      }
      expect(requestBody).toMatchObject({
        username: 'browseruser',
        email: 'browseruser@example.test',
        password: 'browser-password',
      })
      return json({
        id: 10,
        username: 'browseruser',
        display_name: 'browseruser',
        email: 'browseruser@example.test',
      }, { status: 201 })
    }
    if (url.pathname === '/api/users/forgot-password' && route.request().method() === 'POST') {
      const requestBody = route.request().postDataJSON()
      expect(requestBody).toMatchObject({
        email: 'charlie@example.test',
      })
      return json({
        message: 'Reset link sent to charlie@example.test',
        debug_reset_url: 'http://127.0.0.1:3100/reset-password?token=reset-token-1',
      })
    }
    if (url.pathname === '/api/users/verify-email' && route.request().method() === 'POST') {
      const requestBody = route.request().postDataJSON()
      if (requestBody.token === 'bad-verify-token') {
        return json({ error: '邮箱验证令牌无效或已过期' }, { status: 400 })
      }
      expect(requestBody).toMatchObject({
        token: 'verify-token-1',
      })
      currentUser = {
        ...currentUser,
        is_email_confirmed: true,
      }
      return json(currentUser)
    }
    if (url.pathname === '/api/users/reset-password' && route.request().method() === 'POST') {
      const requestBody = route.request().postDataJSON()
      if (requestBody.token === 'bad-reset-token') {
        return json({ error: '重置密码令牌无效或已过期' }, { status: 400 })
      }
      expect(requestBody).toMatchObject({
        token: 'reset-token-1',
        password: 'new-password',
      })
      return json({
        ...charlie,
        password_reset_at: '2026-06-30T11:00:00Z',
      })
    }
    if (url.pathname === '/api/users/me/resend-email-verification' && route.request().method() === 'POST') {
      if (currentUser.is_email_confirmed) {
        return json({ error: '当前邮箱已经验证' }, { status: 400 })
      }
      return json({
        message: '验证邮件已发送',
        debug_verify_url: 'http://127.0.0.1:3100/verify-email?token=verify-token-2',
      })
    }
    if (url.pathname === '/api/users/me') {
      return json(currentUser)
    }
    if (url.pathname === '/api/users/me/preferences' && route.request().method() === 'GET') {
      return json(profilePreferencesPayload)
    }
    if (url.pathname === '/api/users/me/preferences' && route.request().method() === 'PATCH') {
      const requestBody = route.request().postDataJSON()
      expect(requestBody).toMatchObject({
        values: {
          notify_post_reply: true,
          notify_user_mentioned: false,
        },
        ui_values: {},
      })
      return json(profilePreferencesPayload)
    }
    if (url.pathname === '/api/users/9/avatar' && route.request().method() === 'POST') {
      const contentType = route.request().headers()['content-type'] || ''
      expect(contentType).toContain('multipart/form-data')

      currentUser = {
        ...currentUser,
        avatar_url: browserAvatarDataUrl,
      }
      return json(currentUser)
    }
    if (url.pathname === '/api/users/9/password' && route.request().method() === 'POST') {
      const requestBody = route.request().postDataJSON()
      expect(requestBody).toMatchObject({
        old_password: 'wrong-current-password',
        new_password: 'new-secure-password',
      })
      return json({ error: '当前密码不正确' }, { status: 400 })
    }
    if (url.pathname === '/api/users/9' && route.request().method() === 'PATCH') {
      const requestBody = route.request().postDataJSON()
      expect(requestBody).toMatchObject({
        display_name: 'Charlie Browser',
        email: 'charlie@example.test',
        bio: 'Profile updated through Playwright',
      })
      return json({
        ...charlie,
        display_name: 'Charlie Browser',
        bio: 'Profile updated through Playwright',
      })
    }
    if (url.pathname === '/api/users/7') {
      return json({
        ...alice,
        bio: 'Alice public profile biography',
        color: '#2d8fdd',
        joined_at: '2026-05-20T08:00:00Z',
        last_seen_at: '2026-06-30T09:30:00Z',
        discussion_count: 1,
        comment_count: 2,
      })
    }
    if (url.pathname === '/api/search') {
      expect(url.searchParams.get('q')).toBe('browser')
      expect(url.searchParams.get('type')).toBe('all')
      expect(url.searchParams.get('page')).toBe('1')
      expect(url.searchParams.get('limit')).toBe('20')
      return json(searchPayload)
    }
    if (url.pathname === '/api/search/filters') {
      return json({ filters: [] })
    }
    if (url.pathname === '/api/tags') {
      expect(url.searchParams.get('include_children')).toBe('true')
      return json(tagTreePayload)
    }
    if (url.pathname === '/api/tags/slug/general') {
      return json(tagDetailPayload)
    }
    if (url.pathname === '/api/tags/popular') {
      return json({ data: tagTreePayload.data })
    }
    if (url.pathname === '/api/notifications/stats') {
      return json(buildNotificationStatsPayload())
    }
    if (url.pathname === '/api/notifications' && route.request().method() === 'GET') {
      return json(buildNotificationListPayload({
        page: Number(url.searchParams.get('page') || 1),
        limit: Number(url.searchParams.get('limit') || 20),
        type: url.searchParams.get('type') || '',
        isRead: url.searchParams.has('is_read') ? url.searchParams.get('is_read') === 'true' : null,
      }))
    }
    if (url.pathname === '/api/notifications/read-all' && route.request().method() === 'POST') {
      notificationItems = notificationItems.map(item => ({ ...item, is_read: true }))
      return json({ count: notificationItems.length })
    }
    if (url.pathname === '/api/notifications/read/clear' && route.request().method() === 'DELETE') {
      const beforeCount = notificationItems.length
      notificationItems = notificationItems.filter(item => !item.is_read)
      return json({ count: beforeCount - notificationItems.length })
    }
    if (url.pathname === '/api/notifications/read-filtered' && route.request().method() === 'POST') {
      const type = url.searchParams.get('type') || ''
      const discussionId = Number(url.searchParams.get('discussion_id') || 0)
      let count = 0
      notificationItems = notificationItems.map(item => {
        const matchesType = !type || item.type === type
        const matchesDiscussion = !discussionId || Number(item.data?.discussion_id || 0) === discussionId
        if (!item.is_read && matchesType && matchesDiscussion) {
          count += 1
          return { ...item, is_read: true }
        }
        return item
      })
      return json({ count })
    }
    if (url.pathname === '/api/notifications/read/clear-filtered' && route.request().method() === 'DELETE') {
      const type = url.searchParams.get('type') || ''
      const discussionId = Number(url.searchParams.get('discussion_id') || 0)
      const beforeCount = notificationItems.length
      notificationItems = notificationItems.filter(item => {
        const matchesType = !type || item.type === type
        const matchesDiscussion = !discussionId || Number(item.data?.discussion_id || 0) === discussionId
        return !(item.is_read && matchesType && matchesDiscussion)
      })
      return json({ count: beforeCount - notificationItems.length })
    }
    if (url.pathname.match(/^\/api\/notifications\/\d+\/read$/) && route.request().method() === 'POST') {
      const notificationId = Number(url.pathname.split('/')[3])
      notificationItems = notificationItems.map(item => (
        item.id === notificationId ? { ...item, is_read: true } : item
      ))
      return json({ ok: true })
    }
    if (url.pathname.match(/^\/api\/notifications\/\d+$/) && route.request().method() === 'DELETE') {
      const notificationId = Number(url.pathname.split('/')[3])
      notificationItems = notificationItems.filter(item => item.id !== notificationId)
      return json({ ok: true })
    }
    if (url.pathname === '/api/posts' && url.searchParams.get('author') === 'charlie') {
      expect(url.searchParams.get('limit')).toBe('20')
      return json(profilePostsPayload)
    }
    if (url.pathname === '/api/discussions/' && route.request().method() === 'POST') {
      const requestBody = route.request().postDataJSON()
      expect(requestBody).toMatchObject({
        data: {
          type: 'discussion',
          attributes: {
            title: 'Discussion created through Playwright',
            content: 'Opening post created through Playwright',
          },
          relationships: {
            tags: {
              data: [
                { type: 'tag', id: '1' },
                { type: 'tag', id: '3' },
              ],
            },
          },
        },
      })
      return json(createdDiscussion, { status: 201 })
    }
    if (url.pathname === '/api/discussions/') {
      if (url.searchParams.get('author') === 'charlie') {
        expect(url.searchParams.get('sort')).toBe('newest')
        expect(url.searchParams.get('limit')).toBe('20')
        return json(profileDiscussionPayload)
      }
      if (url.searchParams.get('author') === 'alice') {
        return json({
          ...profileDiscussionPayload,
          data: [
            {
              ...profileDiscussionPayload.data[0],
              title: 'Alice public profile discussion',
              user: alice,
            },
          ],
        })
      }
      if (url.searchParams.get('tag') === 'general') {
        return json(taggedDiscussionListPayload)
      }
      return json(discussionListPayload)
    }
    if (url.pathname === '/api/discussions/101') {
      return json(discussionDetailPayload)
    }
    if (url.pathname === '/api/discussions/202') {
      return json(createdDiscussion)
    }
    if (url.pathname === '/api/discussions/202/posts') {
      expect(url.searchParams.get('limit')).toBe('20')
      expect(url.searchParams.get('near')).toBe('1')
      return json(createdDiscussionPostsPayload)
    }
    if (url.pathname === '/api/discussions/101/posts' && route.request().method() === 'POST') {
      const requestBody = route.request().postDataJSON()
      expect(requestBody).toMatchObject({
        content: 'Reply submitted through Playwright',
        reply_to_post_id: null,
      })
      const post = {
        id: 503,
        discussion_id: 101,
        number: 3,
        type: 'comment',
        content: requestBody.content,
        content_html: '<p>Reply submitted through Playwright</p>',
        created_at: '2026-06-30T10:00:00Z',
        is_hidden: false,
        can_edit: true,
        can_delete: true,
        can_hide: false,
        user: charlie,
      }
      createdReplies.push(post)
      return json(post, { status: 201 })
    }
    if (url.pathname === '/api/discussions/101/posts') {
      expect(url.searchParams.get('limit')).toBe('20')
      expect(url.searchParams.get('near')).toBe('1')
      return json(buildPostStreamPayload(createdReplies))
    }

    return json({ error: `Unhandled E2E API fixture: ${url.pathname}` }, { status: 404 })
  })

  page.browserErrors = browserErrors
})

test('forum home renders discussion list through browser runtime', async ({ page }) => {
  const discussionsResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/discussions/' && response.status() === 200
  })

  await page.goto('/')
  await discussionsResponse

  await expect(page.locator('.logo')).toContainText('Bias E2E Forum')
  await expect(page.locator('[data-discussion-id="101"]')).toBeVisible()
  await expect(page.getByText('正在加载讨论...')).toBeHidden()
  await expect(page.locator('.discussion-list')).toBeVisible()
  const discussionHref = await page.getByRole('link', { name: 'Browser E2E discussion list renders' }).getAttribute('href')
  expect(new URL(discussionHref, 'http://127.0.0.1:3100').pathname).toBe('/d/101')

  expect(page.browserErrors).toEqual([])
})

test('auth browser flow logs in from protected route and returns to composer', async ({ page }) => {
  page.e2eAuthenticated = false

  await page.goto('/discussions/create')
  await expect(page.getByRole('heading', { name: '登录' })).toBeVisible()

  await page.getByLabel('用户名或邮箱').fill('charlie@example.test')
  await page.getByLabel('密码').fill('correct-password')

  const loginResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/login'
      && response.request().method() === 'POST'
      && response.status() === 200
  })
  const meResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/me' && response.status() === 200
  })

  await page.locator('.AuthSessionModal form').getByRole('button', { name: '登录' }).click()
  await loginResponse
  await meResponse

  await expect(page).toHaveURL(/\/discussions\/create$/)
  await expect(page.locator('.floating-composer')).toBeVisible()
  await expect(page.getByPlaceholder('讨论标题')).toBeVisible()

  expect(page.browserErrors).toEqual([])
})

test('auth browser flow registers user and requests password reset link', async ({ page }) => {
  page.e2eAuthenticated = false

  await page.goto('/register')
  await expect(page.getByRole('heading', { name: '加入讨论' })).toBeVisible()

  await page.getByLabel('用户名').fill('browseruser')
  await page.getByLabel('邮箱').fill('browseruser@example.test')
  await page.getByLabel('密码', { exact: true }).fill('browser-password')
  await page.getByLabel('确认密码').fill('browser-password')

  const registerResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/register'
      && response.request().method() === 'POST'
      && response.status() === 201
  })
  await page.locator('.AuthSessionModal form').getByRole('button', { name: '注册' }).click()
  await registerResponse
  await expect(page.getByText('注册成功，请检查邮箱完成验证。')).toBeVisible()

  await page.goto('/forgot-password')
  await expect(page.getByRole('heading', { name: '找回密码' })).toBeVisible()
  await page.getByLabel('邮箱').fill('charlie@example.test')

  const forgotPasswordResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/forgot-password'
      && response.request().method() === 'POST'
      && response.status() === 200
  })
  await page.getByRole('button', { name: '发送重置链接' }).click()
  await forgotPasswordResponse
  await expect(page.getByText('Reset link sent to charlie@example.test')).toBeVisible()
  await expect(page.getByRole('link', { name: /reset-token-1/ })).toBeVisible()

  expect(page.browserErrors).toEqual([])
})

test('account security pages verify email and reset password through browser runtime', async ({ page }) => {
  page.e2eAuthenticated = true

  const verifyResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/verify-email'
      && response.request().method() === 'POST'
      && response.status() === 200
  })
  await page.goto('/verify-email?token=verify-token-1')
  await verifyResponse
  await expect(page.getByRole('heading', { name: '验证邮箱' })).toBeVisible()
  await expect(page.getByText('邮箱验证成功。现在你可以继续登录，或返回个人资料查看最新状态。')).toBeVisible()

  await page.goto('/reset-password?token=reset-token-1')
  await expect(page.getByRole('heading', { name: '重置密码' })).toBeVisible()
  await expect(page.getByLabel('重置令牌')).toHaveValue('reset-token-1')
  await page.getByLabel('新密码', { exact: true }).fill('new-password')
  await page.getByLabel('确认新密码').fill('new-password')

  const resetResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/reset-password'
      && response.request().method() === 'POST'
      && response.status() === 200
  })
  await page.getByRole('button', { name: '重置密码' }).click()
  await resetResponse
  await expect(page.getByText('密码已重置，正在返回登录页...')).toBeVisible()

  expect(page.browserErrors).toEqual([])
})

test('auth browser flow surfaces login, register, verify, and reset failures', async ({ page }) => {
  page.e2eAuthenticated = false

  await page.goto('/login')
  await expect(page.getByRole('heading', { name: '登录' })).toBeVisible()
  await page.getByLabel('用户名或邮箱').fill('wrong@example.test')
  await page.getByLabel('密码').fill('wrong-password')

  const failedLoginResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/login'
      && response.request().method() === 'POST'
      && response.status() === 401
  })
  await page.locator('.AuthSessionModal form').getByRole('button', { name: '登录' }).click()
  await failedLoginResponse
  await expect(page.getByText('用户名或密码错误')).toBeVisible()
  await expect(page.getByLabel('密码')).toHaveValue('')

  await page.goto('/register')
  await expect(page.getByRole('heading', { name: '加入讨论' })).toBeVisible()
  await page.getByLabel('用户名').fill('takenuser')
  await page.getByLabel('邮箱').fill('taken@example.test')
  await page.getByLabel('密码', { exact: true }).fill('browser-password')
  await page.getByLabel('确认密码').fill('different-password')
  await page.locator('.AuthSessionModal form').getByRole('button', { name: '注册' }).click()
  await expect(page.getByText('两次输入的密码不一致')).toBeVisible()

  await page.getByLabel('确认密码').fill('browser-password')
  const failedRegisterResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/register'
      && response.request().method() === 'POST'
      && response.status() === 400
  })
  await page.locator('.AuthSessionModal form').getByRole('button', { name: '注册' }).click()
  await failedRegisterResponse
  await expect(page.getByText('邮箱已被使用')).toBeVisible()

  const failedVerifyResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/verify-email'
      && response.request().method() === 'POST'
      && response.status() === 400
  })
  await page.goto('/verify-email?token=bad-verify-token')
  await failedVerifyResponse
  await expect(page.getByText('邮箱验证令牌无效或已过期')).toBeVisible()

  await page.goto('/reset-password?token=bad-reset-token')
  await page.getByLabel('新密码', { exact: true }).fill('new-password')
  await page.getByLabel('确认新密码').fill('different-password')
  await page.getByRole('button', { name: '重置密码' }).click()
  await expect(page.getByText('两次输入的新密码不一致')).toBeVisible()

  await page.getByLabel('确认新密码').fill('new-password')
  const failedResetResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/reset-password'
      && response.request().method() === 'POST'
      && response.status() === 400
  })
  await page.getByRole('button', { name: '重置密码' }).click()
  await failedResetResponse
  await expect(page.getByText('重置密码令牌无效或已过期')).toBeVisible()

  expect(page.browserErrors.filter(error => !error.startsWith('Failed to load resource:'))).toEqual([])
})

test('authenticated user replies from discussion detail composer through browser runtime', async ({ page }) => {
  page.e2eAuthenticated = true

  await page.goto('/d/101')
  await expect(page.getByRole('heading', { name: 'Browser E2E discussion list renders' })).toBeVisible()
  await expect(page.locator('.posts .post-item')).toHaveCount(2)

  await page.getByRole('button', { name: '回复讨论' }).click()
  await expect(page.locator('.floating-composer')).toBeVisible()
  await expect(page.locator('.floating-composer textarea')).toBeVisible()
  await page.locator('.floating-composer textarea').fill('Reply submitted through Playwright')

  const replyResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/discussions/101/posts'
      && response.request().method() === 'POST'
      && response.status() === 201
  })

  await page.getByRole('button', { name: '发布回复' }).click()
  await replyResponse

  await expect(page.locator('.floating-composer')).toBeHidden()
  await expect(page.locator('#post-3')).toContainText('Reply submitted through Playwright')
  await expect(page.locator('#post-3 .post-number')).toContainText('#3')
  await expect(page.locator('.posts .post-item')).toHaveCount(3)

  expect(page.browserErrors).toEqual([])
})

test('authenticated user creates a discussion through browser runtime', async ({ page }) => {
  page.e2eAuthenticated = true

  await page.goto('/discussions/create')
  await expect(page.locator('.floating-composer')).toBeVisible()
  await expect(page.getByPlaceholder('讨论标题')).toBeVisible()
  await page.locator('.composer-tag-select').first().selectOption('1')
  await page.locator('.composer-tag-select').nth(1).selectOption('3')

  await page.getByPlaceholder('讨论标题').fill('Discussion created through Playwright')
  await page.getByPlaceholder('输入讨论内容... 支持 Markdown、@用户名 和代码块').fill('Opening post created through Playwright')

  const createResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/discussions/'
      && response.request().method() === 'POST'
      && response.status() === 201
  })

  await page.getByRole('button', { name: '发布讨论' }).click()
  await createResponse

  await expect(page.locator('.floating-composer')).toBeHidden()
  await expect(page).toHaveURL(/\/d\/202$/)
  await expect(page.getByRole('heading', { name: 'Discussion created through Playwright' })).toBeVisible()
  await expect(page.locator('#post-1')).toContainText('Opening post created through Playwright')
  await expect(page.locator('#post-1 .post-number')).toContainText('#1')
  await expect(page.locator('.posts .post-item')).toHaveCount(1)

  expect(page.browserErrors).toEqual([])
})

test('tags forum flow renders tags index, filters tag discussions, and contributes composer tag payload', async ({ page }) => {
  page.e2eAuthenticated = true

  const tagsResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/tags' && response.status() === 200
  })

  await page.goto('/tags')
  await tagsResponse

  await expect(page.getByRole('heading', { name: '全部标签' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'General' })).toBeVisible()
  await expect(page.getByText('General forum discussions')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Browser', exact: true })).toBeVisible()
  await expect(page.getByText('Support')).toBeVisible()

  const tagDetailResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/tags/slug/general' && response.status() === 200
  })
  const tagDiscussionResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/discussions/'
      && url.searchParams.get('tag') === 'general'
      && response.status() === 200
  })
  await page.goto('/t/general')
  await tagDetailResponse
  await tagDiscussionResponse

  expect(new URL(page.url()).pathname).toBe('/t/general')
  await expect(page.getByRole('link', { name: 'General', exact: true }).first()).toBeVisible()
  await expect(page.getByRole('link', { name: 'Browser tag filtered discussion' })).toBeVisible()

  await page.getByRole('button', { name: '发起讨论' }).click()
  await expect(page.locator('.floating-composer')).toBeVisible()
  await expect(page.locator('.composer-tag-select').first()).toHaveValue('1')
  await page.locator('.composer-tag-select').nth(1).selectOption('3')

  await page.getByPlaceholder('讨论标题').fill('Discussion created through Playwright')
  await page.getByPlaceholder('输入讨论内容... 支持 Markdown、@用户名 和代码块').fill('Opening post created through Playwright')

  const createResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/discussions/'
      && response.request().method() === 'POST'
      && response.status() === 201
  })

  await page.getByRole('button', { name: '发布讨论' }).click()
  await createResponse

  await expect(page).toHaveURL(/\/d\/202$/)
  await expect(page.getByRole('heading', { name: 'Discussion created through Playwright' })).toBeVisible()

  expect(page.browserErrors).toEqual([])
})

test('authenticated user manages notifications through browser runtime', async ({ page }) => {
  page.e2eAuthenticated = true

  const notificationsResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/notifications' && response.status() === 200
  })

  await page.goto('/notifications')
  await notificationsResponse

  await expect(page.getByRole('heading', { name: '通知' }).first()).toBeVisible()
  await expect(page.getByText('Bob 回复了你的帖子')).toBeVisible()
  await expect(page.getByText('Browser E2E discussion list renders')).toBeVisible()
  await expect(page.getByText('Alice 已封禁你的账号：Browser account moderation notice')).toBeVisible()
  await expect(page.getByRole('button', { name: '全部标记为已读' })).toBeVisible()
  await expect(page.getByRole('button', { name: '当前页清除已读' })).toBeVisible()

  const markOneReadResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/notifications/301/read'
      && response.request().method() === 'POST'
      && response.status() === 200
  })
  await page.getByTitle('标记为已读').first().click()
  await markOneReadResponse
  await expect(page.getByTitle('标记为已读')).toHaveCount(0)

  const clearReadResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/notifications/read/clear'
      && response.request().method() === 'DELETE'
      && response.status() === 200
  })
  await page.getByRole('button', { name: '当前页清除已读' }).click()
  await expect(page.getByRole('heading', { name: '清除当前页已读通知' })).toBeVisible()
  await page.locator('.Modal').getByRole('button', { name: '清除已读' }).click()
  await clearReadResponse
  await expect(page.getByRole('heading', { name: '已清除已读通知' })).toBeVisible()
  await page.locator('.Modal').getByRole('button', { name: '确定' }).click()
  await expect(page.getByText('暂无通知')).toBeVisible()

  expect(page.browserErrors).toEqual([])
})

test('authenticated user filters and deletes notifications through browser runtime', async ({ page }) => {
  page.e2eAuthenticated = true

  await page.goto('/notifications')
  await expect(page.getByText('Bob 回复了你的帖子')).toBeVisible()
  await expect(page.getByText('Alice 已封禁你的账号：Browser account moderation notice')).toBeVisible()

  const postReplyFilterResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/notifications'
      && url.searchParams.get('type') === 'postReply'
      && !url.searchParams.has('is_read')
      && response.status() === 200
  })
  await page.locator('.search-filters .filter-item').filter({ hasText: '回复被回应' }).click()
  await postReplyFilterResponse
  await expect(page).toHaveURL(/\/notifications\?type=postReply$/)
  await expect(page.getByText('Bob 回复了你的帖子')).toBeVisible()
  await expect(page.getByText('Alice 已封禁你的账号：Browser account moderation notice')).toHaveCount(0)

  const unreadFilterResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/notifications'
      && url.searchParams.get('type') === 'postReply'
      && url.searchParams.get('is_read') === 'false'
      && response.status() === 200
  })
  await page.goto('/notifications?type=postReply&state=unread')
  await unreadFilterResponse
  await expect(page).toHaveURL(/\/notifications\?type=postReply&state=unread$/)
  await expect(page.getByRole('button', { name: '查看全部通知' })).toBeVisible()

  const markFilteredResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/notifications/read-filtered'
      && url.searchParams.get('type') === 'postReply'
      && response.request().method() === 'POST'
      && response.status() === 200
  })
  await page.getByRole('button', { name: '当前筛选标记已读' }).click()
  await expect(page.getByRole('heading', { name: '标记当前筛选结果为已读' })).toBeVisible()
  await page.locator('.Modal').getByRole('button', { name: '标记已读' }).click()
  await markFilteredResponse
  await expect(page.getByRole('heading', { name: '已全部标记为已读' })).toBeVisible()
  await page.locator('.Modal').getByRole('button', { name: '确定' }).click()
  await expect(page.getByText('当前没有未读通知')).toBeVisible()

  const allPostReplyResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/notifications'
      && url.searchParams.get('type') === 'postReply'
      && !url.searchParams.has('is_read')
      && response.status() === 200
  })
  await page.getByRole('button', { name: '查看全部通知' }).click()
  await allPostReplyResponse
  await expect(page).toHaveURL(/\/notifications\?type=postReply$/)
  await expect(page.getByText('Bob 回复了你的帖子')).toBeVisible()

  const deleteResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/notifications/301'
      && response.request().method() === 'DELETE'
      && response.status() === 200
  })
  await page.getByTitle('删除通知').click()
  await expect(page.getByRole('heading', { name: '删除通知' })).toBeVisible()
  await page.locator('.Modal').getByRole('button', { name: '删除' }).click()
  await deleteResponse
  await expect(page.getByText('当前筛选下暂无通知')).toBeVisible()

  const accountFilterResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/notifications'
      && url.searchParams.get('type') === 'userSuspended'
      && response.status() === 200
  })
  await page.locator('.search-filters .filter-item').filter({ hasText: '账号封禁通知' }).click()
  await accountFilterResponse
  await expect(page).toHaveURL(/\/notifications\?type=userSuspended$/)
  await expect(page.getByText('Alice 已封禁你的账号：Browser account moderation notice')).toBeVisible()

  const clearFilteredResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/notifications/read/clear-filtered'
      && url.searchParams.get('type') === 'userSuspended'
      && response.request().method() === 'DELETE'
      && response.status() === 200
  })
  await page.getByRole('button', { name: '当前筛选清除已读' }).click()
  await expect(page.getByRole('heading', { name: '清除当前筛选中的已读通知' })).toBeVisible()
  await page.locator('.Modal').getByRole('button', { name: '清除已读' }).click()
  await clearFilteredResponse
  await expect(page.getByRole('heading', { name: '已清除已读通知' })).toBeVisible()
  await page.locator('.Modal').getByRole('button', { name: '确定' }).click()
  await expect(page.getByText('当前筛选下暂无通知')).toBeVisible()

  expect(page.browserErrors).toEqual([])
})

test('profile pages render user activity and save own profile through browser runtime', async ({ page }) => {
  page.e2eAuthenticated = true

  const ownProfileResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/me' && response.status() === 200
  })
  const ownDiscussionsResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/discussions/'
      && url.searchParams.get('author') === 'charlie'
      && response.status() === 200
  })
  const preferencesResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/me/preferences'
      && response.request().method() === 'GET'
      && response.status() === 200
  })

  await page.goto('/profile')
  await ownProfileResponse
  await ownDiscussionsResponse
  await preferencesResponse

  await expect(page.getByRole('heading', { name: 'Charlie' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Charlie profile discussion' })).toBeVisible()
  await expect(page.locator('.user-sidebar').getByText(/^讨论\s*2$/)).toBeVisible()
  await expect(page.locator('.user-sidebar').getByText(/^回复\s*4$/)).toBeVisible()

  const avatarUploadResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/9/avatar'
      && response.request().method() === 'POST'
      && response.status() === 200
  })
  await page.locator('.avatar-input').setInputFiles({
    name: 'browser-avatar.png',
    mimeType: 'image/png',
    buffer: Buffer.from([
      0x89, 0x50, 0x4e, 0x47,
      0x0d, 0x0a, 0x1a, 0x0a,
      0x00, 0x00, 0x00, 0x0d,
      0x49, 0x48, 0x44, 0x52,
    ]),
  })
  await avatarUploadResponse
  await expect(page.locator('.user-avatar img.avatar-large')).toHaveAttribute('src', browserAvatarDataUrl)

  const postsResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/posts'
      && url.searchParams.get('author') === 'charlie'
      && response.status() === 200
  })
  await page.getByText('回复').click()
  await postsResponse
  await expect(page.getByText('Profile reply rendered from author feed')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Browser E2E discussion list renders' })).toBeVisible()

  await page.getByRole('button', { name: '设置' }).click()
  await expect(page.getByRole('heading', { name: '个人设置' })).toBeVisible()
  await expect(page.getByLabel('显示名称')).toHaveValue('Charlie')
  await page.getByLabel('显示名称').fill('Charlie Browser')
  await page.getByLabel('个人简介').fill('Profile updated through Playwright')

  const saveProfileResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/9'
      && response.request().method() === 'PATCH'
      && response.status() === 200
  })
  await page.getByRole('button', { name: '保存资料' }).click()
  await saveProfileResponse
  await expect(page.getByText('资料已保存')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Charlie Browser' })).toBeVisible()

  const publicProfileResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/7' && response.status() === 200
  })
  const publicDiscussionsResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/discussions/'
      && url.searchParams.get('author') === 'alice'
      && response.status() === 200
  })
  await page.goto('/u/7')
  await publicProfileResponse
  await publicDiscussionsResponse

  await expect(page.getByRole('heading', { name: 'Alice' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Alice public profile discussion' })).toBeVisible()
  await expect(page.getByRole('button', { name: '设置' })).toHaveCount(0)

  expect(page.browserErrors).toEqual([])
})

test('profile security page surfaces resend and password failure paths through browser runtime', async ({ page }) => {
  page.e2eAuthenticated = true

  await page.goto('/profile')
  await expect(page.getByRole('heading', { name: 'Charlie' })).toBeVisible()

  await page.evaluate(() => {
    window.__biasE2ESetEmailUnconfirmed?.()
  })
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Charlie' })).toBeVisible()

  await page.locator('.user-sidebar .nav-link').filter({ hasText: '安全' }).click()
  await expect(page.getByRole('heading', { name: '账号安全' })).toBeVisible()
  await expect(page.getByText('未验证', { exact: true })).toBeVisible()

  await page.evaluate(() => {
    window.__biasE2ESetEmailConfirmed?.()
  })
  const resendFailureResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/me/resend-email-verification'
      && response.request().method() === 'POST'
      && response.status() === 400
  })
  await page.getByRole('button', { name: '重新发送验证邮件' }).click()
  await resendFailureResponse
  await expect(page.getByText('当前邮箱已经验证')).toBeVisible()

  await page.getByLabel('当前密码').fill('old-password')
  await page.getByLabel('新密码', { exact: true }).fill('new-secure-password')
  await page.getByLabel('确认新密码').fill('mismatched-password')
  await page.getByRole('button', { name: '更新密码' }).click()
  await expect(page.getByText('两次输入的新密码不一致')).toBeVisible()

  await page.getByLabel('当前密码').fill('wrong-current-password')
  await page.getByLabel('确认新密码').fill('new-secure-password')
  const passwordFailureResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/users/9/password'
      && response.request().method() === 'POST'
      && response.status() === 400
  })
  await page.getByRole('button', { name: '更新密码' }).click()
  await passwordFailureResponse
  await expect(page.getByText('当前密码不正确')).toBeVisible()

  expect(page.browserErrors.filter(error => !error.startsWith('Failed to load resource:'))).toEqual([])
})

test('forum search page renders grouped results and opens discussion result through browser runtime', async ({ page }) => {
  const searchResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/search' && response.status() === 200
  })

  await page.goto('/search?q=browser&type=all')
  await searchResponse

  await expect(page.getByRole('heading', { name: '“browser”' })).toBeVisible()
  await expect(page.getByText('共找到 3 条结果，已按讨论、帖子和用户分组展示。')).toBeVisible()
  await expect(page.getByRole('heading', { name: '讨论' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '帖子' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '用户' })).toBeVisible()
  await expect(page.getByText('Browser E2E discussion list renders').first()).toBeVisible()
  await expect(page.getByText('Browser search discussion excerpt')).toBeVisible()
  await expect(page.getByText('Browser search post excerpt')).toBeVisible()
  await expect(page.getByText('Alice Searcher')).toBeVisible()
  await expect(page.getByText('Browser search user profile')).toBeVisible()
  await expect(page.getByText('搜索中...')).toBeHidden()

  const discussionResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/discussions/101' && response.status() === 200
  })
  const postsResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/discussions/101/posts' && response.status() === 200
  })

  await page.locator('.result-card').filter({ hasText: 'Browser search discussion excerpt' }).click()
  await discussionResponse
  await postsResponse

  expect(new URL(page.url()).pathname).toBe('/d/101')
  await expect(page.getByRole('heading', { name: 'Browser E2E discussion list renders' })).toBeVisible()

  expect(page.browserErrors).toEqual([])
})

test('forum home opens discussion detail and renders post stream through browser runtime', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('[data-discussion-id="101"]')).toBeVisible()

  const discussionResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/discussions/101' && response.status() === 200
  })
  const postsResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/discussions/101/posts' && response.status() === 200
  })

  await page.getByRole('link', { name: 'Browser E2E discussion list renders' }).click()
  await discussionResponse
  await postsResponse

  expect(new URL(page.url()).pathname).toBe('/d/101')
  await expect(page.getByRole('heading', { name: 'Browser E2E discussion list renders' })).toBeVisible()
  await expect(page.getByText('正在加载讨论...')).toBeHidden()
  await expect(page.locator('#post-1')).toContainText('First browser detail post')
  await expect(page.locator('#post-2')).toContainText('Reply rendered from post stream')
  await expect(page.locator('#post-1 .post-number')).toContainText('#1')
  await expect(page.locator('#post-2 .post-number')).toContainText('#2')
  await expect(page.locator('.posts .post-item')).toHaveCount(2)

  expect(page.browserErrors).toEqual([])
})
