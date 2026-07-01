import { expect, test } from '@playwright/test'

const adminUser = {
  id: 1,
  username: 'admin',
  display_name: 'Admin',
  avatar_url: '',
  is_staff: true,
}

const initialSettings = {
  forum_title: 'Bias E2E Forum',
  forum_description: 'Admin settings fixture',
  seo_title: '',
  seo_description: '',
  seo_keywords: '',
  seo_robots_index: true,
  seo_robots_follow: true,
  announcement_enabled: false,
  announcement_message: '',
  announcement_tone: 'info',
}

const usersExtension = {
  id: 'users',
  name: 'users',
  enabled: true,
  product_visible: true,
  module_ids: ['users'],
  frontend_forum_entry: 'extensions/users/frontend/forum/index.js',
  frontend_admin_entry: 'extensions/users/frontend/admin/index.js',
  frontend_boot: { forum: true, admin: true },
  frontend_routes: [],
  icon: 'fas fa-users',
  description: 'User account extension',
}

const discussionsExtension = {
  id: 'discussions',
  name: 'discussions',
  enabled: true,
  product_visible: true,
  module_ids: ['discussions'],
  frontend_forum_entry: 'extensions/discussions/frontend/forum/index.js',
  frontend_boot: { forum: true },
  frontend_routes: [
    {
      path: '/',
      name: 'home',
      component: './DiscussionListView.vue',
      frontend: 'forum',
      module_id: 'discussions',
    },
  ],
  icon: 'fas fa-comments',
  description: 'Discussion extension',
}

const forumUser = {
  id: 7,
  username: 'alice',
  display_name: 'Alice',
  avatar_url: '',
  is_staff: false,
}

const discussionListPayload = {
  data: [
    {
      id: 101,
      title: 'Runtime settings discussion',
      slug: 'runtime-settings-discussion',
      created_at: '2026-06-30T08:00:00Z',
      last_posted_at: '2026-06-30T09:00:00Z',
      comment_count: 1,
      participant_count: 1,
      unread_count: 0,
      is_sticky: false,
      is_locked: false,
      is_hidden: false,
      can_reply: true,
      can_edit: false,
      can_delete: false,
      can_hide: false,
      is_subscribed: false,
      user: forumUser,
      tags: [],
      last_post: {
        id: 501,
        number: 1,
        created_at: '2026-06-30T09:00:00Z',
        user: forumUser,
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
  let settings = { ...initialSettings }

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
      return json({
        ...settings,
        enabled_modules: ['users', 'discussions'],
        enabled_extensions: [usersExtension, discussionsExtension],
      })
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
        discussions: 1,
        posts: 1,
        users: 1,
        version: 'e2e',
      })
    }
    if (url.pathname === '/api/admin/extensions') {
      return json({
        extensions: [usersExtension, discussionsExtension],
        runtime: { stamp: 'admin-settings-e2e' },
      })
    }
    if (url.pathname === '/api/admin/settings' && route.request().method() === 'GET') {
      return json(settings)
    }
    if (url.pathname === '/api/admin/settings' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON()
      expect(payload).toMatchObject({
        forum_title: 'Runtime Settings Forum',
        forum_description: 'Runtime settings flow fixture',
        seo_title: 'Runtime Settings SEO',
        seo_description: 'Runtime settings SEO description',
        seo_keywords: 'runtime,settings,bias',
        seo_robots_index: false,
        seo_robots_follow: true,
        announcement_enabled: true,
        announcement_message: 'Runtime settings announcement',
        announcement_tone: 'warning',
      })
      settings = { ...settings, ...payload }
      return json(settings)
    }
    if (url.pathname === '/api/discussions/') {
      return json(discussionListPayload)
    }

    return json({ error: `Unhandled ${route.request().method()} ${url.pathname}` }, { status: 404 })
  })

  page.assertNoBrowserErrors = () => {
    expect(browserErrors).toEqual([])
  }
})

test('admin basics settings save is reflected by forum runtime settings', async ({ page }) => {
  const settingsResponse = waitForAdminSettings(page, 'GET')
  await page.goto('/admin.html#/admin/basics')
  await settingsResponse

  await expect(page.getByRole('heading', { name: '基础设置' })).toBeVisible()
  await expect(page.getByLabel('论坛名称')).toHaveValue('Bias E2E Forum')
  await expect(page.getByLabel('论坛描述')).toHaveValue('Admin settings fixture')

  await page.getByLabel('论坛名称').fill('Runtime Settings Forum')
  await page.getByLabel('论坛描述').fill('Runtime settings flow fixture')
  await page.getByLabel('SEO 标题').fill('Runtime Settings SEO')
  await page.getByLabel('SEO 描述').fill('Runtime settings SEO description')
  await page.getByLabel('SEO 关键词').fill('runtime,settings,bias')
  await page.getByLabel('允许搜索引擎建立索引').uncheck()
  await page.getByLabel('启用全站公告').check()
  await page.getByLabel('公告内容').fill('Runtime settings announcement')
  await page.locator('#basics-announcement-tone').selectOption('warning')

  const saveResponse = waitForAdminSettings(page, 'POST')
  await page.getByRole('button', { name: '保存设置' }).click()
  await saveResponse

  await expect(page.getByText('保存成功')).toBeVisible()

  const forumResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/forum' && response.status() === 200
  })
  await page.goto('/')
  await forumResponse

  await expect(page.locator('.logo')).toContainText('Runtime Settings Forum')
  await expect(page.locator('.site-announcement')).toContainText('Runtime settings announcement')
  await expect(page.locator('.site-announcement')).toHaveClass(/site-announcement--warning/)
  await expect(page.getByText('Runtime settings discussion')).toBeVisible()
  await expect(page).toHaveTitle('全部讨论 - Runtime Settings Forum')

  const metaDescription = page.locator('meta[name="description"]')
  const metaKeywords = page.locator('meta[name="keywords"]')
  const metaRobots = page.locator('meta[name="robots"]')
  await expect(metaDescription).toHaveAttribute('content', '浏览论坛最新讨论、热门主题和社区回复。')
  await expect(metaKeywords).toHaveAttribute('content', 'runtime,settings,bias')
  await expect(metaRobots).toHaveAttribute('content', 'noindex, follow')

  page.assertNoBrowserErrors()
})

function waitForAdminSettings(page, method) {
  return page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/admin/settings'
      && response.request().method() === method
      && response.status() === 200
  })
}
