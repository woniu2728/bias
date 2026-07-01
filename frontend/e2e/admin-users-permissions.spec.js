import { expect, test } from '@playwright/test'

const adminUser = {
  id: 1,
  username: 'admin',
  display_name: 'Admin',
  avatar_url: '',
  is_staff: true,
}

const moderatorGroup = {
  id: 2,
  name: 'Moderators',
  icon: 'fas fa-shield-alt',
  color: '#4d698e',
  is_hidden: false,
  is_system: false,
}

const memberGroup = {
  id: 3,
  name: 'Members',
  icon: 'fas fa-user',
  color: '#2d8fdd',
  is_hidden: false,
  is_system: true,
}

const createdGroup = {
  id: 8,
  name: 'Reviewers',
  icon: 'fas fa-eye',
  color: '#8e44ad',
  is_hidden: true,
  is_system: false,
}

const baseGroups = [moderatorGroup, memberGroup]

const managedUserBase = {
  id: 9,
  username: 'charlie',
  display_name: 'Charlie',
  email: 'charlie@example.test',
  bio: 'Original user biography',
  is_staff: false,
  is_email_confirmed: false,
  is_suspended: false,
  suspended_until: null,
  suspend_reason: '',
  suspend_message: '',
  joined_at: '2026-06-01T08:00:00Z',
  discussion_count: 2,
  comment_count: 4,
  primary_group: memberGroup,
  groups: [memberGroup],
}

const forumSettings = {
  forum_title: 'Bias E2E Forum',
  forum_description: 'Admin users and permissions fixture',
  enabled_modules: ['users'],
  enabled_extensions: [],
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
  action_links: {
    admin_page: '/admin/users',
  },
}

test.beforeEach(async ({ page }) => {
  const browserErrors = []
  let groups = baseGroups.map(group => ({ ...group }))
  let managedUser = cloneUser(managedUserBase)
  let permissions = {
    2: ['viewForum'],
    3: ['viewForum'],
  }

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
        discussions: 6,
        posts: 18,
        users: 3,
        totalUsers: 3,
        version: 'e2e',
      })
    }
    if (url.pathname === '/api/admin/extensions') {
      return json({
        extensions: [usersExtension],
        runtime: { stamp: 'admin-users-permissions-e2e' },
      })
    }
    if (url.pathname === '/api/admin/groups' && route.request().method() === 'GET') {
      return json(groups)
    }
    if (url.pathname === '/api/admin/groups' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON()
      expect(payload).toMatchObject({
        name: 'Reviewers',
        icon: 'fas fa-eye',
        color: '#8e44ad',
        is_hidden: true,
      })
      groups = [...groups, { ...createdGroup }]
      permissions[createdGroup.id] = []
      return json(createdGroup, { status: 201 })
    }
    if (url.pathname === '/api/admin/permissions/meta') {
      return json({
        sections: [
          {
            name: 'view',
            label: '查看',
            permissions: [
              {
                name: 'viewForum',
                label: '查看论坛',
                description: '允许访问论坛。',
                icon: 'fas fa-eye',
              },
            ],
          },
          {
            name: 'moderate',
            label: '管理',
            permissions: [
              {
                name: 'discussion.lock',
                label: '锁定讨论',
                description: '允许锁定或解锁讨论。',
                icon: 'fas fa-lock',
              },
              {
                name: 'discussion.sticky',
                label: '置顶讨论',
                description: '允许置顶或取消置顶讨论。',
                icon: 'fas fa-thumbtack',
              },
            ],
          },
        ],
        modules: [
          { id: 'core', name: 'Core' },
          { id: 'discussions', name: 'Discussions' },
        ],
      })
    }
    if (url.pathname === '/api/admin/permissions' && route.request().method() === 'GET') {
      return json(permissions)
    }
    if (url.pathname === '/api/admin/permissions' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON()
      expect(payload[String(createdGroup.id)] || payload[createdGroup.id]).toEqual([
        'viewForum',
        'discussion.lock',
      ])
      permissions = payload
      return json({ ok: true })
    }
    if (url.pathname === '/api/admin/users' && route.request().method() === 'GET') {
      expect(url.searchParams.get('page')).toBe('1')
      expect(url.searchParams.get('limit')).toBe('20')
      return json({
        data: [managedUser],
        total: 1,
      })
    }
    if (url.pathname === '/api/admin/users/9' && route.request().method() === 'GET') {
      return json(managedUser)
    }
    if (url.pathname === '/api/admin/users/9' && route.request().method() === 'PUT') {
      const payload = route.request().postDataJSON()
      expect(payload).toMatchObject({
        username: 'charlie-reviewed',
        email: 'charlie.reviewed@example.test',
        bio: 'Reviewed through admin browser flow',
        is_staff: true,
        is_email_confirmed: true,
        group_ids: [3, 2],
        suspend_reason: 'policy-review',
        suspend_message: 'Please contact support after the review window.',
      })
      expect(payload.suspended_until).toMatch(/^2026-07-02T10:30/)
      managedUser = {
        ...managedUser,
        ...payload,
        is_suspended: true,
        primary_group: moderatorGroup,
        groups: [memberGroup, moderatorGroup],
      }
      return json(managedUser)
    }

    return json({ error: `Unhandled ${route.request().method()} ${url.pathname}` }, { status: 404 })
  })

  page.assertNoBrowserErrors = () => {
    expect(browserErrors).toEqual([])
  }
})

test('admin manages user status groups and permission matrix through browser runtime', async ({ page }) => {
  await page.goto('/admin.html#/admin')
  await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible()

  const usersResponse = waitForApi(page, '/api/admin/users', 'GET')
  await page.getByRole('link', { name: '管理用户' }).click()
  await usersResponse

  const userTable = page.locator('.UserTable')
  await expect(page.getByRole('heading', { name: '用户管理' })).toBeVisible()
  await expect(userTable.getByRole('cell', { name: 'charlie', exact: true })).toBeVisible()
  await expect(userTable.getByText('未激活')).toBeVisible()
  await expect(userTable.getByText('Members')).toBeVisible()

  const userDetailResponse = waitForApi(page, '/api/admin/users/9', 'GET')
  await page.getByRole('button', { name: '编辑' }).click()
  await userDetailResponse

  await page.getByRole('textbox', { name: '用户名' }).fill('charlie-reviewed')
  await page.getByRole('textbox', { name: '邮箱', exact: true }).fill('charlie.reviewed@example.test')
  await page.getByRole('textbox', { name: '个人简介' }).fill('Reviewed through admin browser flow')
  await page.getByRole('checkbox', { name: '管理员' }).check()
  await page.getByRole('checkbox', { name: '邮箱已验证' }).check()
  await page.getByLabel('用户组').click()
  await page.getByRole('button', { name: /Moderators/ }).click()
  await page.getByLabel('用户组').click()
  await page.getByLabel('封禁截止时间').fill('2026-07-02T10:30')
  await page.getByLabel('封禁原因').fill('policy-review')
  await page.getByLabel('对用户显示的信息').fill('Please contact support after the review window.')

  const saveUserResponse = waitForApi(page, '/api/admin/users/9', 'PUT')
  await page.getByRole('button', { name: '保存' }).click()
  await expect(page.getByRole('heading', { name: '保存用户变更' })).toBeVisible()
  await expect(page.getByText('管理员权限、用户组、封禁状态')).toBeVisible()
  await page.locator('.ModalManager').getByRole('button', { name: '保存' }).click()
  await saveUserResponse
  await page.getByRole('button', { name: '确定' }).click()

  await expect(userTable.getByRole('cell', { name: 'charlie-reviewed', exact: true })).toBeVisible()
  await expect(userTable.getByText('已封禁')).toBeVisible()
  await expect(userTable.getByText('Moderators')).toBeVisible()

  const permissionsResponse = waitForApi(page, '/api/admin/permissions', 'GET')
  await page.goto('/admin.html#/admin/permissions')
  await permissionsResponse

  await expect(page.getByRole('heading', { name: '权限管理' })).toBeVisible()
  await expect(page.getByText('当前共注册 3 项权限')).toBeVisible()

  await page.getByRole('button', { name: '添加用户组' }).click()
  await page.getByRole('textbox', { name: '名称' }).fill('Reviewers')
  await page.locator('#group-color-text').fill('#8e44ad')
  await page.getByRole('textbox', { name: '图标' }).fill('fas fa-eye')
  await page.locator('.GroupHiddenToggle').click()
  await expect(page.getByRole('checkbox', { name: '隐藏用户组' })).toBeChecked()

  const createGroupResponse = waitForApi(page, '/api/admin/groups', 'POST')
  await page.locator('.GroupModal-actions').getByRole('button', { name: '保存' }).click()
  await createGroupResponse

  await expect(page.getByRole('button', { name: /Reviewers/ })).toBeVisible()
  await page.getByRole('button', { name: /Reviewers/ }).click()

  await togglePermissionRow(page, '查看论坛')
  await togglePermissionRow(page, '锁定讨论')

  const savePermissionsResponse = waitForApi(page, '/api/admin/permissions', 'POST')
  await page.getByRole('button', { name: '保存权限' }).click()
  await expect(page.getByRole('heading', { name: '保存权限配置' })).toBeVisible()
  await page.locator('.ModalManager').getByRole('button', { name: '保存' }).click()
  await savePermissionsResponse

  await expect(page.getByText('保存成功')).toBeVisible()
  page.assertNoBrowserErrors()
})

async function togglePermissionRow(page, permissionLabel) {
  await page.locator('tr', { hasText: permissionLabel }).locator('input[type="checkbox"]').check()
}

function waitForApi(page, pathname, method) {
  return page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === pathname
      && response.request().method() === method
      && response.status() >= 200
      && response.status() < 300
  })
}

function cloneUser(user) {
  return {
    ...user,
    primary_group: user.primary_group ? { ...user.primary_group } : null,
    groups: Array.isArray(user.groups) ? user.groups.map(group => ({ ...group })) : [],
  }
}
