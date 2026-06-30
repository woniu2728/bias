import { expect, test } from '@playwright/test'

const forumSettings = {
  forum_title: 'Bias E2E Forum',
  forum_description: 'Browser flow fixture',
  enabled_modules: ['users', 'discussions'],
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
  ],
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
      user: {
        id: 7,
        username: 'alice',
        display_name: 'Alice',
        avatar_url: '',
        is_staff: false,
      },
      last_post: {
        id: 501,
        number: 3,
        created_at: '2026-06-30T09:00:00Z',
        user: {
          id: 8,
          username: 'bob',
          display_name: 'Bob',
          avatar_url: '',
        },
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

test.beforeEach(async ({ page }) => {
  const browserErrors = []

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
      return json({ authenticated: false, user: null })
    }
    if (url.pathname === '/api/discussions/') {
      return json(discussionListPayload)
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
