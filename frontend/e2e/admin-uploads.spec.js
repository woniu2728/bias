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
  forum_description: 'Admin uploads browser flow fixture',
  enabled_modules: ['users', 'content', 'uploads'],
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

const uploadsExtension = {
  id: 'uploads',
  name: 'uploads',
  enabled: true,
  product_visible: true,
  module_ids: ['uploads'],
  frontend_admin_entry: 'extensions/uploads/frontend/admin/index.js',
  frontend_boot: { admin: true },
  icon: 'fas fa-file-upload',
  description: 'Upload policy and storage extension',
  action_links: {
    settings_page: '/admin/extensions/uploads/settings',
  },
  settings_pages: ['/admin/extensions/uploads/settings'],
}

const initialUploadSettings = {
  attachments_dir: 'attachments',
  attachment_max_size_mb: 10,
  upload_site_asset_max_size_mb: 2,
  avatars_dir: 'avatars',
  avatar_max_size_mb: 2,
  storage_driver: 'local',
  storage_local_path: '',
  storage_local_base_url: '/media/',
}

test.beforeEach(async ({ page }) => {
  const browserErrors = []
  let uploadSettings = { ...initialUploadSettings }

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
        version: 'e2e',
      })
    }
    if (url.pathname === '/api/admin/extensions') {
      return json({
        extensions: [usersExtension, uploadsExtension],
        runtime: { stamp: 'admin-uploads-e2e' },
      })
    }
    if (url.pathname === '/api/admin/extensions/uploads' && route.request().method() === 'GET') {
      return json({
        extension: {
          ...uploadsExtension,
          settings_values: { ...uploadSettings },
        },
      })
    }
    if (url.pathname === '/api/admin/extensions/uploads/settings' && route.request().method() === 'GET') {
      return json({ settings: { ...uploadSettings } })
    }
    if (url.pathname === '/api/admin/extensions/uploads/settings' && route.request().method() === 'POST') {
      const payload = route.request().postDataJSON()
      expect(payload).toMatchObject({
        attachments_dir: 'forum-files',
        attachment_max_size_mb: 7,
        upload_site_asset_max_size_mb: 4,
        avatars_dir: 'profile-images',
        avatar_max_size_mb: 3,
        storage_driver: 'local',
        storage_local_path: 'D:\\uploads\\bias-e2e',
        storage_local_base_url: '/uploads/',
      })
      uploadSettings = { ...uploadSettings, ...payload }
      return json({ settings: { ...uploadSettings } })
    }

    return json({ error: `Unhandled ${route.request().method()} ${url.pathname}` }, { status: 404 })
  })

  page.assertNoBrowserErrors = () => {
    expect(browserErrors).toEqual([])
  }
})

test('admin uploads settings page saves storage and upload limits through browser runtime', async ({ page }) => {
  const settingsResponse = waitForUploadSettings(page, 'GET')
  await page.goto('/admin.html#/admin/extensions/uploads/settings')
  await settingsResponse

  await expect(page.getByRole('heading', { name: 'uploads · 设置页' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '上传策略' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '存储驱动' })).toBeVisible()
  await expect(page.getByLabel('附件目录')).toHaveValue('attachments')
  await expect(page.getByLabel('附件最大体积（MB）')).toHaveValue('10')
  await expect(page.getByLabel('本地访问基地址')).toHaveValue('/media/')

  await page.getByLabel('附件目录').fill('forum-files')
  await page.getByLabel('附件最大体积（MB）').fill('7')
  await page.getByLabel('站点资源最大体积（MB）').fill('4')
  await page.getByLabel('头像目录').fill('profile-images')
  await page.getByLabel('头像最大体积（MB）').fill('3')
  await selectMenuOption(page, '当前驱动', '本地存储')
  await page.getByLabel('本地保存目录').fill('D:\\uploads\\bias-e2e')
  await page.getByLabel('本地访问基地址').fill('/uploads/')

  const saveResponse = waitForUploadSettings(page, 'POST')
  await page.getByRole('button', { name: '保存上传设置' }).click()
  await saveResponse

  await expect(page.getByText('上传设置已保存').first()).toBeVisible()
  await expect(page.getByText('新的上传策略和存储驱动配置已生效。')).toBeVisible()
  await page.getByRole('button', { name: '确定' }).click()
  await expect(page.getByLabel('附件目录')).toHaveValue('forum-files')
  await expect(page.getByLabel('附件最大体积（MB）')).toHaveValue('7')
  await expect(page.getByLabel('站点资源最大体积（MB）')).toHaveValue('4')
  await expect(page.getByLabel('头像目录')).toHaveValue('profile-images')
  await expect(page.getByLabel('头像最大体积（MB）')).toHaveValue('3')
  await expect(page.getByLabel('本地保存目录')).toHaveValue('D:\\uploads\\bias-e2e')
  await expect(page.getByLabel('本地访问基地址')).toHaveValue('/uploads/')

  page.assertNoBrowserErrors()
})

async function selectMenuOption(page, label, option) {
  await page.getByLabel(label).click()
  await page.getByRole('button', { name: option }).click()
}

function waitForUploadSettings(page, method) {
  return page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/admin/extensions/uploads/settings'
      && response.request().method() === method
      && response.status() === 200
  })
}
