import { expect, test } from '@playwright/test'

const adminUser = {
  id: 1,
  username: 'admin',
  display_name: 'Admin',
  email: 'admin@example.test',
  avatar_url: '',
  is_staff: true,
}

const forumSettings = {
  forum_title: 'Bias E2E Forum',
  forum_description: 'Admin mail browser flow fixture',
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
}

const initialMailSettings = {
  mail_driver: 'smtp',
  mail_from: 'Bias Mailer <service@example.com>',
  mail_format: 'multipart',
  mail_host: 'smtp.gmail.com',
  mail_port: 587,
  mail_encryption: 'tls',
  mail_username: 'service@example.com',
  mail_password: '',
  mail_test_recipient: '',
  test_to_email: 'admin@example.test',
  sending: true,
  errors: {},
  drivers: {
    smtp: { label: 'SMTP' },
  },
  driver_options: [{ value: 'smtp', label: 'SMTP' }],
}

test.beforeEach(async ({ page }) => {
  const browserErrors = []
  let mailSettings = { ...initialMailSettings }

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
        totalUsers: 3,
        version: 'e2e',
      })
    }
    if (url.pathname === '/api/admin/extensions') {
      return json({
        extensions: [usersExtension],
        runtime: { stamp: 'admin-mail-e2e' },
      })
    }
    if (url.pathname === '/api/admin/mail' && route.request().method() === 'GET') {
      return json(mailSettings)
    }
    if (url.pathname === '/api/admin/mail' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON()
      expect(payload).toMatchObject({
        mail_driver: 'smtp',
        mail_from: 'Bias Runtime <runtime@example.test>',
        mail_format: 'multipart',
        mail_host: 'smtp.runtime.example.test',
        mail_port: 2525,
        mail_encryption: 'tls',
        mail_username: 'runtime@example.test',
        mail_password: 'runtime-secret',
        mail_test_recipient: 'ops@example.test',
      })
      mailSettings = {
        ...mailSettings,
        ...payload,
        mail_port: Number(payload.mail_port),
        settings: {
          ...mailSettings,
          ...payload,
          mail_port: Number(payload.mail_port),
        },
        test_to_email: payload.mail_test_recipient,
        sending: true,
        errors: {},
      }
      return json({
        settings: mailSettings.settings,
        test_to_email: mailSettings.test_to_email,
        sending: true,
        errors: {},
      })
    }
    if (url.pathname === '/api/admin/mail/test' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON()
      expect(payload).toMatchObject({
        to_email: 'ops@example.test',
      })
      return json({
        message: '测试邮件已发送',
        sent_count: 1,
        to_email: 'ops@example.test',
      })
    }

    return json({ error: `Unhandled ${route.request().method()} ${url.pathname}` }, { status: 404 })
  })

  page.assertNoBrowserErrors = () => {
    expect(browserErrors).toEqual([])
  }
})

test('admin mail settings save enables sending a test email through browser runtime', async ({ page }) => {
  const mailResponse = waitForApi(page, '/api/admin/mail', 'GET')
  await page.goto('/admin.html#/admin/mail')
  await mailResponse

  await expect(page.getByRole('heading', { name: '邮件设置' })).toBeVisible()
  await expect(page.getByLabel('发件地址')).toHaveValue('Bias Mailer <service@example.com>')
  await expect(page.getByLabel('SMTP 主机')).toHaveValue('smtp.gmail.com')
  await expect(page.getByText('实际发送到：admin@example.test')).toBeVisible()

  await page.getByLabel('发件地址').fill('Bias Runtime <runtime@example.test>')
  await page.getByLabel('SMTP 主机').fill('smtp.runtime.example.test')
  await page.getByLabel('SMTP 端口').fill('2525')
  await page.getByLabel('SMTP 用户名').fill('runtime@example.test')
  await page.getByLabel('SMTP 密码').fill('runtime-secret')
  await page.getByLabel('测试收件箱').fill('ops@example.test')

  await expect(page.getByRole('button', { name: '发送测试邮件' })).toBeDisabled()
  await expect(page.getByText('请先保存当前修改，再发送测试邮件。')).toBeVisible()

  const saveResponse = waitForApi(page, '/api/admin/mail', 'POST')
  await page.getByRole('button', { name: '保存设置' }).click()
  await saveResponse

  await expect(page.getByText('保存成功')).toBeVisible()
  await expect(page.getByRole('button', { name: '发送测试邮件' })).toBeEnabled()
  await expect(page.getByText('实际发送到：ops@example.test')).toBeVisible()

  const testMailResponse = waitForApi(page, '/api/admin/mail/test', 'POST')
  await page.getByRole('button', { name: '发送测试邮件' }).click()
  await testMailResponse

  await expect(page.getByRole('heading', { name: '测试邮件已发送' })).toBeVisible()
  await expect(page.getByText('测试邮件已发送到 ops@example.test，请检查收件箱')).toBeVisible()
  await page.getByRole('button', { name: '确定' }).click()

  page.assertNoBrowserErrors()
})

function waitForApi(page, pathname, method) {
  return page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === pathname
      && response.request().method() === method
      && response.status() >= 200
      && response.status() < 300
  })
}
