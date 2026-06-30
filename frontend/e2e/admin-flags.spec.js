import { expect, test } from '@playwright/test'

const adminUser = {
  id: 1,
  username: 'admin',
  display_name: 'Admin',
  avatar_url: '',
  is_staff: true,
}

const forumSettings = {
  forum_title: 'Bias E2E Forum',
  forum_description: 'Admin browser flow fixture',
  enabled_modules: ['users', 'content', 'flags'],
  enabled_extensions: [],
}

const flagsExtension = {
  id: 'flags',
  name: 'flags',
  enabled: true,
  product_visible: true,
  module_ids: ['flags'],
  frontend_admin_entry: 'extensions/flags/frontend/admin/index.js',
  frontend_boot: { admin: true },
  icon: 'fas fa-flag',
  description: 'Moderation reporting extension',
}

const usersExtension = {
  id: 'users',
  name: 'users',
  enabled: true,
  product_visible: true,
  module_ids: ['users'],
  frontend_admin_entry: 'extensions/users/frontend/admin/index.js',
  frontend_boot: { admin: true },
  icon: 'fas fa-users',
  description: 'User account extension',
}

const baseOpenFlag = {
  id: 401,
  reason: '违规内容',
  message: 'Browser admin should review this flagged post',
  status: 'open',
  created_at: '2026-06-30T11:10:00Z',
  user: {
    id: 9,
    username: 'reporter',
    display_name: 'Reporter',
    avatar_url: '',
  },
  post: {
    id: 502,
    discussion_id: 101,
    discussion_title: 'Browser E2E discussion list renders',
    number: 2,
    content: 'Reply rendered from post stream',
    user: {
      id: 8,
      username: 'bob',
      display_name: 'Bob',
      avatar_url: '',
    },
  },
  resolved_by: null,
  resolved_at: null,
  resolution_note: '',
}

test.beforeEach(async ({ page }) => {
  const browserErrors = []
  let flags = [{ ...baseOpenFlag }]

  page.on('pageerror', error => {
    browserErrors.push(error.message)
  })
  page.on('console', message => {
    if (message.type() !== 'error') return
    const text = message.text()
    if (text.includes('WebSocket connection')) return
    if (text.includes('Failed to load resource') && text.includes('/ws/')) return
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
      return json({ authenticated: true, user: adminUser })
    }
    if (url.pathname === '/api/users/me') {
      return json(adminUser)
    }
    if (url.pathname === '/api/users/me/preferences') {
      return json({ values: {}, ui_values: {}, definitions: [] })
    }
    if (url.pathname === '/api/admin/stats') {
      return json({
        discussions: 4,
        posts: 12,
        users: 3,
        openFlags: flags.filter(flag => flag.status === 'open').length,
        version: 'e2e',
      })
    }
    if (url.pathname === '/api/admin/extensions') {
      return json({
        extensions: [usersExtension, flagsExtension],
        runtime: { stamp: 'admin-flags-e2e' },
      })
    }
    if (url.pathname === '/api/admin/flags' && route.request().method() === 'GET') {
      const status = url.searchParams.get('status') || 'open'
      const visibleFlags = flags.filter(flag => flag.status === status)
      return json({
        total: visibleFlags.length,
        page: 1,
        limit: 20,
        data: visibleFlags,
      })
    }
    if (url.pathname.match(/^\/api\/admin\/flags\/\d+\/resolve$/) && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON()
      expect(payload).toMatchObject({
        status: 'resolved',
        resolution_note: '已在后台浏览器流程中处理',
      })
      flags = flags.map(flag => (
        String(flag.id) === url.pathname.split('/').at(-2)
          ? {
              ...flag,
              status: 'resolved',
              resolution_note: payload.resolution_note,
              resolved_by: adminUser,
              resolved_at: '2026-06-30T11:20:00Z',
            }
          : flag
      ))
      return json(flags.find(flag => flag.id === baseOpenFlag.id))
    }

    return json({ error: `Unhandled ${route.request().method()} ${url.pathname}` }, { status: 404 })
  })

  page.assertNoBrowserErrors = () => {
    expect(browserErrors).toEqual([])
  }
})

test('admin flags page lists and resolves reported posts through browser runtime', async ({ page }) => {
  await page.goto('/admin.html#/admin')
  await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible()

  const openFlagsResponse = waitForFlagsResponse(page, 'open')
  await page.getByRole('link', { name: '处理举报' }).click()
  await openFlagsResponse

  await expect(page.getByRole('heading', { name: '举报管理' })).toBeVisible()
  await expect(page.getByText('Browser admin should review this flagged post')).toBeVisible()
  await expect(page.getByText('Browser E2E discussion list renders')).toBeVisible()
  await expect(page.getByText('Reply rendered from post stream')).toBeVisible()

  await page.getByRole('button', { name: '标记已处理' }).click()
  await expect(page.getByRole('heading', { name: '标记举报已处理' })).toBeVisible()
  await page.locator('#admin-action-note').fill('已在后台浏览器流程中处理')

  const resolveResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/admin/flags/401/resolve' && response.status() === 200
  })
  const reloadResponse = waitForFlagsResponse(page, 'open')

  await page.getByRole('button', { name: '标记已处理' }).last().click()
  await resolveResponse
  await reloadResponse

  await expect(page.getByText('暂无举报记录')).toBeVisible()
  await expect(page.getByText('举报已处理')).toBeVisible()
  await page.getByRole('button', { name: '确定' }).click()

  const resolvedResponse = waitForFlagsResponse(page, 'resolved')
  await page.getByRole('tab', { name: '已处理' }).click()
  await resolvedResponse

  await expect(page.getByText('已在后台浏览器流程中处理')).toBeVisible()
  await expect(page.getByText('处理人：Admin')).toBeVisible()

  page.assertNoBrowserErrors()
})

function waitForFlagsResponse(page, status) {
  return page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/admin/flags'
      && url.searchParams.get('status') === status
      && response.status() === 200
  })
}
