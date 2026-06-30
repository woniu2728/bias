import { expect, test } from '@playwright/test'

const forumSettings = {
  forum_title: 'Bias E2E Forum',
  forum_description: 'Browser flow fixture',
  enabled_modules: ['users', 'discussions', 'posts', 'realtime'],
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
      id: 'realtime',
      frontend_routes: [],
    },
  ],
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

  page.on('pageerror', error => {
    browserErrors.push(error.message)
  })
  page.on('console', message => {
    if (message.type() !== 'error') return
    const text = message.text()
    if (text.includes('WebSocket connection')) return
    if (text.includes('Failed to load resource') && text.includes('/ws/online/')) return
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
        return json({ authenticated: true, user: charlie })
      }
      return json({ authenticated: false, user: null })
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
          relationships: {},
        },
      })
      return json(createdDiscussion, { status: 201 })
    }
    if (url.pathname === '/api/discussions/') {
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
