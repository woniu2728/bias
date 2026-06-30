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
  forum_description: 'Admin tags browser flow fixture',
  enabled_modules: ['users', 'content', 'tags'],
  enabled_extensions: [],
}

const tagsExtension = {
  id: 'tags',
  name: 'tags',
  enabled: true,
  product_visible: true,
  module_ids: ['tags'],
  frontend_admin_entry: 'extensions/tags/frontend/admin/index.js',
  frontend_boot: { admin: true },
  icon: 'fas fa-tags',
  description: 'Tag hierarchy and discussion scope extension',
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

const initialTags = [
  {
    id: 11,
    name: 'General',
    slug: 'general',
    description: 'General discussion',
    color: '#3c78d8',
    icon: 'fas fa-comments',
    position: 1,
    default_sort: null,
    is_primary: true,
    parent_id: null,
    parent_name: null,
    discussion_count: 3,
    is_hidden: false,
    is_restricted: false,
    view_scope: 'public',
    start_discussion_scope: 'members',
    reply_scope: 'members',
    view_scope_label: '所有人',
    start_discussion_scope_label: '已登录用户',
    reply_scope_label: '已登录用户',
  },
  {
    id: 12,
    name: 'Support',
    slug: 'support',
    description: 'Support questions',
    color: '#0e7490',
    icon: 'fas fa-life-ring',
    position: 2,
    default_sort: null,
    is_primary: true,
    parent_id: null,
    parent_name: null,
    discussion_count: 1,
    is_hidden: false,
    is_restricted: false,
    view_scope: 'public',
    start_discussion_scope: 'members',
    reply_scope: 'members',
    view_scope_label: '所有人',
    start_discussion_scope_label: '已登录用户',
    reply_scope_label: '已登录用户',
  },
]

test.beforeEach(async ({ page }) => {
  const browserErrors = []
  let tags = initialTags.map(tag => ({ ...tag }))
  let nextTagId = 100

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
        tags: tags.length,
        version: 'e2e',
      })
    }
    if (url.pathname === '/api/admin/extensions') {
      return json({
        extensions: [usersExtension, tagsExtension],
        runtime: { stamp: 'admin-tags-e2e' },
      })
    }
    if (url.pathname === '/api/admin/tags' && route.request().method() === 'GET') {
      return json(tags)
    }
    if (url.pathname === '/api/admin/tags' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON()
      expect(payload).toMatchObject({
        name: expect.any(String),
        slug: expect.any(String),
        view_scope: expect.any(String),
        start_discussion_scope: expect.any(String),
        reply_scope: expect.any(String),
      })
      const parent = tags.find(tag => tag.id === payload.parent_id) || null
      const created = normalizeTag({
        ...payload,
        id: nextTagId++,
        discussion_count: 0,
        parent_name: parent?.name || null,
      })
      tags = [...tags, created]
      return json(created)
    }
    if (url.pathname.match(/^\/api\/admin\/tags\/\d+$/) && route.request().method() === 'PUT') {
      const tagId = Number(url.pathname.split('/').at(-1))
      const payload = route.request().postDataJSON()
      const parent = tags.find(tag => tag.id === payload.parent_id) || null
      tags = tags.map(tag => (
        tag.id === tagId
          ? normalizeTag({
              ...tag,
              ...payload,
              id: tagId,
              parent_name: parent?.name || null,
            })
          : tag
      ))
      return json(tags.find(tag => tag.id === tagId))
    }
    if (url.pathname === '/api/admin/tags/order' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON()
      expect(payload.order).toEqual(expect.any(Array))
      const orderById = new Map(payload.order.map(item => [Number(item.id), item]))
      tags = tags.map(tag => {
        const ordered = orderById.get(Number(tag.id))
        return ordered ? normalizeTag({ ...tag, ...ordered }) : tag
      })
      return json({ data: tags })
    }
    if (url.pathname === '/api/admin/tags/stats/refresh' && route.request().method() === 'POST') {
      tags = tags.map(tag => ({
        ...tag,
        discussion_count: tag.name === 'Roadmap' ? 7 : tag.discussion_count,
      }))
      return json({ ok: true })
    }
    if (url.pathname.match(/^\/api\/admin\/tags\/\d+$/) && route.request().method() === 'DELETE') {
      const tagId = Number(url.pathname.split('/').at(-1))
      tags = tags.filter(tag => tag.id !== tagId)
      return json({ ok: true })
    }

    return json({ error: `Unhandled ${route.request().method()} ${url.pathname}` }, { status: 404 })
  })

  page.assertNoBrowserErrors = () => {
    expect(browserErrors).toEqual([])
  }
})

test('admin tags page manages hierarchy, permissions, stats and deletion through browser runtime', async ({ page }) => {
  await page.goto('/admin.html#/admin')
  await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible()

  const initialTagsResponse = waitForTagsResponse(page)
  await page.getByRole('link', { name: '管理标签' }).click()
  await initialTagsResponse

  await expect(page.getByRole('heading', { name: '标签管理' })).toBeVisible()
  await expect(page.getByText('General')).toBeVisible()
  await expect(page.getByText('Support')).toBeVisible()

  await page.getByRole('button', { name: '创建顶级标签' }).first().click()
  await fillTagBasics(page, {
    name: 'Roadmap',
    slug: 'roadmap',
    description: 'Browser-created roadmap tag',
    color: '#dc2626',
    icon: 'fas fa-rocket',
  })
  await selectMenuOption(page, '默认讨论排序', '热门讨论')

  const createPrimaryResponse = waitForTagCreate(page)
  const reloadAfterCreatePrimary = waitForTagsResponse(page)
  await page.getByRole('button', { name: '保存' }).click()
  await createPrimaryResponse
  await reloadAfterCreatePrimary

  await expect(page.getByText('Roadmap')).toBeVisible()
  await expect(page.getByText('标签总数').locator('..').getByText('3')).toBeVisible()

  await page.getByRole('button', { name: '创建子标签' }).click()
  await fillTagBasics(page, {
    name: 'Roadmap Ideas',
    slug: 'roadmap-ideas',
    description: 'Child tag managed from browser',
    color: '#7c3aed',
    icon: 'fas fa-lightbulb',
  })
  await selectMenuOption(page, '父标签', 'Roadmap')

  const createChildResponse = waitForTagCreate(page)
  const reloadAfterCreateChild = waitForTagsResponse(page)
  await page.getByRole('button', { name: '保存' }).click()
  await createChildResponse
  await reloadAfterCreateChild

  await expect(page.getByText('Roadmap Ideas')).toBeVisible()
  await expect(page.getByText('隶属 Roadmap')).toBeVisible()

  await editTag(page, 'Roadmap')
  await page.locator('#tag-description').fill('Updated from admin tags browser flow')
  await page.locator('label', { hasText: '隐藏标签' }).click()
  await page.locator('label', { hasText: '限制发帖' }).click()
  await selectMenuOption(page, '查看权限', '仅管理员')
  await selectMenuOption(page, '发帖权限', '仅管理员')
  await selectMenuOption(page, '回帖权限', '仅管理员')

  const updateResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/admin/tags/100' && response.status() === 200
  })
  const reloadAfterUpdate = waitForTagsResponse(page)
  await page.getByRole('button', { name: '保存' }).click()
  await updateResponse
  await reloadAfterUpdate

  await expect(page.getByText('隐藏标签').first()).toBeVisible()
  await expect(page.getByText('限制发帖').first()).toBeVisible()

  const refreshResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/admin/tags/stats/refresh' && response.status() === 200
  })
  const reloadAfterRefresh = waitForTagsResponse(page)
  await page.getByRole('button', { name: '刷新统计' }).click()
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await refreshResponse
  await reloadAfterRefresh

  await editTag(page, 'Roadmap Ideas')
  const deleteResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/admin/tags/101' && response.status() === 200
  })
  const reloadAfterDelete = waitForTagsResponse(page)
  await page.getByRole('button', { name: '删除' }).click()
  await page.getByRole('button', { name: '删除' }).last().click()
  await deleteResponse
  await reloadAfterDelete
  await page.getByRole('button', { name: '确定' }).click()
  await expect(page.getByRole('heading', { name: '编辑标签' })).toHaveCount(0)

  await expect(page.getByText('Roadmap Ideas')).toHaveCount(0)
  await expect(page.locator('.TagCard').filter({ hasText: 'Roadmap' })).toBeVisible()

  page.assertNoBrowserErrors()
})

async function fillTagBasics(page, { name, slug, description, color, icon }) {
  await page.locator('#tag-name').fill(name)
  await page.locator('#tag-slug').fill(slug)
  await page.locator('#tag-description').fill(description)
  await page.locator('#tag-color-text').fill(color)
  await page.locator('#tag-icon').fill(icon)
}

async function editTag(page, tagName) {
  const card = page.locator('.TagCard').filter({ hasText: tagName }).first()
  await card.getByTitle('编辑').click()
  await expect(page.getByRole('heading', { name: '编辑标签' })).toBeVisible()
}

async function selectMenuOption(page, label, option) {
  await page.getByLabel(label).click()
  await page.getByRole('button', { name: option }).click()
}

function waitForTagsResponse(page) {
  return page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/admin/tags'
      && response.request().method() === 'GET'
      && response.status() === 200
  })
}

function waitForTagCreate(page) {
  return page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/admin/tags'
      && response.request().method() === 'POST'
      && response.status() === 200
  })
}

function normalizeTag(tag) {
  const isChild = tag.parent_id != null
  return {
    id: Number(tag.id),
    name: tag.name,
    slug: tag.slug,
    description: tag.description || '',
    color: tag.color || '#888888',
    icon: tag.icon || '',
    position: tag.position,
    default_sort: tag.default_sort ?? null,
    is_primary: Boolean(isChild || tag.is_primary),
    parent_id: tag.parent_id ?? null,
    parent_name: tag.parent_name ?? null,
    discussion_count: Number(tag.discussion_count || 0),
    is_hidden: Boolean(tag.is_hidden),
    is_restricted: Boolean(tag.is_restricted),
    view_scope: tag.view_scope || 'public',
    start_discussion_scope: tag.start_discussion_scope || 'members',
    reply_scope: tag.reply_scope || 'members',
    view_scope_label: scopeLabel(tag.view_scope || 'public'),
    start_discussion_scope_label: scopeLabel(tag.start_discussion_scope || 'members'),
    reply_scope_label: scopeLabel(tag.reply_scope || 'members'),
  }
}

function scopeLabel(scope) {
  if (scope === 'staff') return '仅管理员'
  if (scope === 'members') return '已登录用户'
  return '所有人'
}
