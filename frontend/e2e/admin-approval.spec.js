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
  forum_description: 'Admin approval browser flow fixture',
  enabled_modules: ['users', 'content', 'approval'],
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
}

const approvalExtension = {
  id: 'approval',
  name: 'approval',
  enabled: true,
  product_visible: true,
  module_ids: ['approval'],
  frontend_admin_entry: 'extensions/approval/frontend/admin/index.js',
  frontend_boot: { admin: true },
  icon: 'fas fa-user-check',
  description: 'Approval queue extension',
}

const author = {
  id: 9,
  username: 'pending-author',
  display_name: 'Pending Author',
  avatar_url: '',
}

const baseApprovalItems = [
  {
    id: 701,
    type: 'discussion',
    title: 'Pending browser discussion',
    content: 'Discussion waiting for browser approval',
    created_at: '2026-06-30T11:00:00Z',
    author,
    discussion: {
      id: 701,
      title: 'Pending browser discussion',
    },
    post: null,
  },
  {
    id: 702,
    type: 'post',
    title: 'Pending reply in browser discussion',
    content: 'Reply waiting for browser rejection',
    created_at: '2026-06-30T11:05:00Z',
    author,
    discussion: {
      id: 701,
      title: 'Pending browser discussion',
    },
    post: {
      id: 702,
      number: 2,
    },
  },
]

test.beforeEach(async ({ page }) => {
  const browserErrors = []
  let approvalItems = baseApprovalItems.map(item => cloneApprovalItem(item))

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
        pendingApprovals: approvalItems.length,
        version: 'e2e',
      })
    }
    if (url.pathname === '/api/admin/extensions') {
      return json({
        extensions: [usersExtension, approvalExtension],
        runtime: { stamp: 'admin-approval-e2e' },
      })
    }
    if (url.pathname === '/api/admin/approval-queue' && route.request().method() === 'GET') {
      const contentType = url.searchParams.get('content_type') || 'all'
      return json({
        data: approvalItems
          .filter(item => contentType === 'all' || item.type === contentType)
          .map(item => cloneApprovalItem(item)),
        total: approvalItems.length,
      })
    }
    if (url.pathname.match(/^\/api\/admin\/approval-queue\/[^/]+\/\d+\/(?:approve|reject)$/) && route.request().method() === 'POST') {
      const parts = url.pathname.split('/')
      const contentType = parts.at(-3)
      const contentId = Number(parts.at(-2))
      const action = parts.at(-1)
      const payload = route.request().postDataJSON()

      if (contentType === 'discussion') {
        expect(contentId).toBe(701)
        expect(action).toBe('approve')
        expect(payload).toMatchObject({ note: '内容符合社区规范，已放行。' })
      } else {
        expect(contentType).toBe('post')
        expect(contentId).toBe(702)
        expect(action).toBe('reject')
        expect(payload).toMatchObject({ note: '内容质量不足，请补充更完整的信息后重新提交。' })
      }

      const processed = approvalItems.find(item => item.type === contentType && Number(item.id) === contentId)
      approvalItems = approvalItems.filter(item => !(item.type === contentType && Number(item.id) === contentId))
      return json({
        ...cloneApprovalItem(processed),
        approval_status: action === 'approve' ? 'approved' : 'rejected',
        approval_note: payload.note,
      })
    }

    return json({ error: `Unhandled ${route.request().method()} ${url.pathname}` }, { status: 404 })
  })

  page.assertNoBrowserErrors = () => {
    expect(browserErrors).toEqual([])
  }
})

test('admin approval page approves discussions and rejects replies through browser runtime', async ({ page }) => {
  await page.goto('/admin.html#/admin')
  await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible()
  await expect(page.getByText('待审核内容')).toBeVisible()
  await expect(page.getByRole('link', { name: '处理审核' })).toBeVisible()

  const initialQueueResponse = waitForApprovalQueueResponse(page, 'all')
  await page.getByRole('link', { name: '处理审核' }).click()
  await initialQueueResponse

  await expect(page.getByRole('heading', { name: '审核队列' })).toBeVisible()
  await expect(page.getByText('Pending browser discussion')).toBeVisible()
  await expect(page.getByText('Discussion waiting for browser approval')).toBeVisible()
  await expect(page.getByText('Pending reply in browser discussion')).toBeVisible()
  await expect(page.getByText('Reply waiting for browser rejection')).toBeVisible()
  await expect(page.getByText('楼层 #2')).toBeVisible()

  const approveResponse = waitForPost(page, '/api/admin/approval-queue/discussion/701/approve')
  const reloadAfterApprove = waitForApprovalQueueResponse(page, 'all')
  await approvalCard(page, 'Pending browser discussion').getByRole('button', { name: '审核通过' }).click()
  await expect(page.getByRole('heading', { name: '审核通过' })).toBeVisible()
  await page.getByRole('button', { name: '内容符合规范' }).click()
  await expect(page.locator('#admin-action-note')).toHaveValue('内容符合社区规范，已放行。')
  await page.getByRole('button', { name: '通过审核' }).click()
  await approveResponse
  await reloadAfterApprove
  await expect(page.getByRole('heading', { name: '审核已通过' })).toBeVisible()
  await expect(page.getByText('内容已放行，用户现在可以正常查看。')).toBeVisible()
  await page.getByRole('button', { name: '确定' }).click()

  await expect(page.getByText('Pending browser discussion')).toHaveCount(0)
  await expect(page.getByText('Pending reply in browser discussion')).toBeVisible()

  const rejectResponse = waitForPost(page, '/api/admin/approval-queue/post/702/reject')
  const reloadAfterReject = waitForApprovalQueueResponse(page, 'all')
  await approvalCard(page, 'Pending reply in browser discussion').getByRole('button', { name: '拒绝并隐藏' }).click()
  await expect(page.getByRole('heading', { name: '拒绝内容' })).toBeVisible()
  await page.getByRole('button', { name: '内容质量不足' }).click()
  await expect(page.locator('#admin-action-note')).toHaveValue('内容质量不足，请补充更完整的信息后重新提交。')
  await page.locator('.Modal').getByRole('button', { name: '拒绝并隐藏' }).click()
  await rejectResponse
  await reloadAfterReject
  await expect(page.getByRole('heading', { name: '内容已拒绝' })).toBeVisible()
  await expect(page.getByText('内容已拒绝并隐藏。')).toBeVisible()
  await page.getByRole('button', { name: '确定' }).click()

  await expect(page.getByText('当前没有待审核内容')).toBeVisible()
  page.assertNoBrowserErrors()
})

function cloneApprovalItem(item) {
  return {
    ...item,
    author: item.author ? { ...item.author } : null,
    discussion: item.discussion ? { ...item.discussion } : null,
    post: item.post ? { ...item.post } : null,
  }
}

function approvalCard(page, title) {
  return page.locator('.ApprovalCard').filter({ hasText: title })
}

function waitForApprovalQueueResponse(page, contentType) {
  return page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/admin/approval-queue'
      && url.searchParams.get('content_type') === contentType
      && response.status() === 200
  })
}

function waitForPost(page, pathname) {
  return page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === pathname
      && response.request().method() === 'POST'
      && response.status() === 200
  })
}
