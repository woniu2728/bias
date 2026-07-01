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
  forum_description: 'Admin extensions browser flow fixture',
  enabled_modules: ['core', 'users', 'content', 'discussions', 'posts', 'likes'],
  enabled_extensions: [
    {
      id: 'users',
      frontend_forum_entry: 'extensions/users/frontend/forum/index.js',
      frontend_routes: [],
    },
    {
      id: 'discussions',
      frontend_forum_entry: 'extensions/discussions/frontend/forum/index.js',
      frontend_routes: [{
        path: '/',
        name: 'home',
        component: './DiscussionListView.vue',
        frontend: 'forum',
        module_id: 'discussions',
      }],
    },
    {
      id: 'posts',
      frontend_forum_entry: 'extensions/posts/frontend/forum/index.js',
      frontend_routes: [],
    },
  ],
}

const discussionListPayload = {
  data: [{
    id: 501,
    title: 'Frontend remains available after rebuild',
    slug: 'frontend-remains-available-after-rebuild',
    excerpt: 'Reloaded forum page still renders after rebuilding extension assets.',
    comment_count: 1,
    participant_count: 1,
    created_at: '2026-06-30T08:00:00Z',
    last_posted_at: '2026-06-30T08:00:00Z',
    is_sticky: false,
    is_locked: false,
    is_hidden: false,
    unread_count: 0,
    can_reply: true,
    can_edit: false,
    tags: [],
    user: {
      id: 1,
      username: 'admin',
      display_name: 'Admin',
      avatar_url: '',
    },
    first_post: {
      id: 901,
      number: 1,
      content: 'Reloaded forum page still renders after rebuilding extension assets.',
      content_html: '<p>Reloaded forum page still renders after rebuilding extension assets.</p>',
      created_at: '2026-06-30T08:00:00Z',
    },
    last_post: null,
  }],
  meta: { page: 1, limit: 20, total: 1, total_pages: 1 },
}

function createExtensionsFixture() {
  return [
    buildExtension({
      id: 'core',
      name: 'Core',
      description: 'Protected runtime services',
      enabled: true,
      protected: true,
      module_ids: ['core'],
      provides: ['settings', 'extension-runtime'],
      runtime_actions: [],
      admin_actions: [{
        key: 'details',
        kind: 'route',
        target: '/admin/extensions/core',
        label: '详情',
        icon: 'fas fa-circle-info',
        tone: 'subtle',
      }],
    }),
    buildExtension({
      id: 'users',
      name: 'Users',
      description: 'User account extension',
      enabled: true,
      protected: true,
      module_ids: ['users'],
      frontend_admin_entry: 'extensions/users/frontend/admin/index.js',
      frontend_boot: { admin: true },
      icon: 'fas fa-users',
      provides: ['auth', 'users'],
      runtime_actions: [],
      admin_actions: [{
        key: 'details',
        kind: 'route',
        target: '/admin/extensions/users',
        label: '详情',
        icon: 'fas fa-circle-info',
        tone: 'subtle',
      }],
    }),
    buildExtension({
      id: 'likes',
      name: 'Likes',
      description: 'Post like extension',
      enabled: true,
      module_ids: ['likes'],
      dependencies: ['posts'],
      provides: ['post-actions', 'notifications'],
      runtime_actions: [disableAction('Likes')],
      admin_actions: [{
        key: 'details',
        kind: 'route',
        target: '/admin/extensions/likes',
        label: '详情',
        icon: 'fas fa-circle-info',
        tone: 'primary',
      }],
      frontend_asset_state: {
        has_frontend: true,
        manifest_exists: true,
        compiled: true,
        requires_rebuild: false,
      },
    }),
    buildExtension({
      id: 'mentions',
      name: 'Mentions',
      description: 'Mention users in posts',
      enabled: false,
      module_ids: ['mentions'],
      dependencies: ['posts', 'users'],
      optional_dependencies: ['notifications'],
      provides: ['formatting'],
      runtime_actions: [enableAction('Mentions'), uninstallAction('Mentions')],
      admin_actions: [{
        key: 'details',
        kind: 'route',
        target: '/admin/extensions/mentions',
        label: '详情',
        icon: 'fas fa-circle-info',
        tone: 'subtle',
      }],
      runtime_status: { key: 'disabled', label: '已停用' },
      diagnostics: {
        warnings: ['optional dependency notifications is disabled'],
      },
      recovery_status: {
        safe_mode: true,
        safe_mode_allowed: false,
      },
      frontend_asset_state: {
        has_frontend: true,
        manifest_exists: true,
        compiled: false,
        requires_rebuild: true,
      },
    }),
  ]
}

test.beforeEach(async ({ page }) => {
  const browserErrors = []
  let extensions = createExtensionsFixture()
  let runtimeStamp = 1
  let synced = false
  let orderSynced = false
  let frontendRebuilt = false

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
    if (url.pathname === '/api/discussions/' && route.request().method() === 'GET') {
      return json(discussionListPayload)
    }
    if (url.pathname === '/api/admin/extensions' && route.request().method() === 'GET') {
      return json(buildExtensionsPayload(extensions, {
        runtimeStamp,
        synced,
        orderSynced,
        frontendRebuilt,
      }))
    }
    if (url.pathname === '/api/admin/extensions/sync' && route.request().method() === 'POST') {
      expect(route.request().postDataJSON()).toMatchObject({ prune_missing: true })
      synced = true
      runtimeStamp += 1
      return json(buildExtensionsPayload(extensions, {
        runtimeStamp,
        synced,
        orderSynced,
        frontendRebuilt,
      }))
    }
    if (url.pathname === '/api/admin/extensions/sync-order' && route.request().method() === 'POST') {
      orderSynced = true
      runtimeStamp += 1
      return json(buildExtensionsPayload(extensions, {
        runtimeStamp,
        synced,
        orderSynced,
        frontendRebuilt,
      }))
    }
    if (url.pathname === '/api/admin/extensions/rebuild-frontend' && route.request().method() === 'POST') {
      expect(route.request().postDataJSON()).toMatchObject({
        run_build: true,
        include_disabled: false,
        publish: false,
      })
      frontendRebuilt = true
      runtimeStamp += 1
      extensions = extensions.map(extension => ({
        ...extension,
        frontend_asset_state: extension.frontend_asset_state?.has_frontend
          ? {
              ...extension.frontend_asset_state,
              manifest_exists: true,
              compiled: true,
              requires_rebuild: false,
            }
          : extension.frontend_asset_state,
      }))
      return json(buildExtensionsPayload(extensions, {
        runtimeStamp,
        synced,
        orderSynced,
        frontendRebuilt,
      }))
    }
    if (url.pathname.match(/^\/api\/admin\/extensions\/[^/]+$/) && route.request().method() === 'GET') {
      const extensionId = decodeURIComponent(url.pathname.split('/').at(-1))
      const extension = extensions.find(item => item.id === extensionId)
      if (!extension) {
        return json({ error: 'Extension not found' }, { status: 404 })
      }
      return json({ extension })
    }
    if (url.pathname.match(/^\/api\/admin\/extensions\/[^/]+\/disable$/) && route.request().method() === 'POST') {
      const extensionId = decodeURIComponent(url.pathname.split('/').at(-2))
      const extension = extensions.find(item => item.id === extensionId)
      expect(extension?.protected).not.toBe(true)
      extensions = extensions.map(item => (
        item.id === extensionId
          ? buildExtension({
              ...item,
              enabled: false,
              booted: false,
              runtime_status: { key: 'disabled', label: '已停用' },
              runtime_actions: [enableAction(item.name), uninstallAction(item.name)],
            })
          : item
      ))
      runtimeStamp += 1
      return json({
        extension: extensions.find(item => item.id === extensionId),
        runtime: runtime(runtimeStamp, { synced, orderSynced, frontendRebuilt }),
      })
    }
    if (url.pathname.match(/^\/api\/admin\/extensions\/[^/]+\/enable$/) && route.request().method() === 'POST') {
      const extensionId = decodeURIComponent(url.pathname.split('/').at(-2))
      extensions = extensions.map(item => (
        item.id === extensionId
          ? buildExtension({
              ...item,
              enabled: true,
              booted: true,
              runtime_status: { key: 'active', label: '已启用' },
              runtime_actions: item.protected ? [] : [disableAction(item.name)],
            })
          : item
      ))
      runtimeStamp += 1
      return json({
        extension: extensions.find(item => item.id === extensionId),
        runtime: runtime(runtimeStamp, { synced, orderSynced, frontendRebuilt }),
      })
    }

    return json({ error: `Unhandled ${route.request().method()} ${url.pathname}` }, { status: 404 })
  })

  page.assertNoBrowserErrors = () => {
    expect(browserErrors).toEqual([])
  }
})

test('admin extensions page manages runtime actions and frontend rebuild through browser runtime', async ({ page }) => {
  await page.goto('/admin.html#/admin')
  await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible()

  const initialExtensionsResponse = waitForExtensionsResponse(page)
  await page.getByRole('link', { name: '管理扩展' }).click()
  await initialExtensionsResponse

  await expect(page.getByRole('heading', { name: '扩展中心' })).toBeVisible()
  await expect(page.getByText('扩展包状态需要关注：')).toBeVisible()
  await expect(extensionCard(page, 'Core').getByText('已启用')).toBeVisible()
  await expect(extensionCard(page, 'Core').getByRole('button', { name: /停用/ })).toHaveCount(0)
  await expect(extensionCard(page, 'Likes').getByText('前端已生成')).toBeVisible()
  await expect(extensionCard(page, 'Mentions').getByText('恢复模式停用')).toBeVisible()
  await expect(extensionCard(page, 'Mentions').getByText('前端待重建')).toBeVisible()

  const syncResponse = waitForPost(page, '/api/admin/extensions/sync')
  await page.getByRole('button', { name: '同步扩展' }).click()
  await syncResponse
  await expect(page.getByText('扩展包状态需要关注：未安装发现 1。')).toHaveCount(0)

  const orderResponse = waitForPost(page, '/api/admin/extensions/sync-order')
  await page.getByRole('button', { name: '同步顺序' }).click()
  await orderResponse

  const rebuildResponse = waitForPost(page, '/api/admin/extensions/rebuild-frontend')
  await page.getByRole('button', { name: '重建前端' }).click()
  await rebuildResponse
  await expect(extensionCard(page, 'Mentions').getByText('前端已生成')).toBeVisible()

  await page.reload()
  await waitForExtensionsResponse(page)
  await expect(page.getByRole('heading', { name: '扩展中心' })).toBeVisible()
  await expect(extensionCard(page, 'Mentions').getByText('前端已生成')).toBeVisible()

  const forumSettingsReloadResponse = page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/forum' && response.status() === 200
  })
  await page.goto('/')
  await forumSettingsReloadResponse
  await expect(page.locator('.logo')).toContainText('Bias E2E Forum')
  await expect(page.getByText('Powered by')).toBeVisible()

  await page.goto('/admin.html#/admin/extensions')
  await waitForExtensionsResponse(page)
  await expect(page.getByRole('heading', { name: '扩展中心' })).toBeVisible()

  const detailResponse = waitForExtensionDetail(page, 'likes')
  await extensionCard(page, 'Likes').getByRole('link', { name: '详情' }).click()
  await detailResponse
  await expect(page.getByRole('heading', { name: 'Likes' })).toBeVisible()

  const disableResponse = waitForPost(page, '/api/admin/extensions/likes/disable')
  await page.locator('.ExtensionDetailToggle').click()
  await page.getByRole('button', { name: '停用', exact: true }).click()
  await disableResponse
  await expect(page.locator('.ExtensionDetailToggle')).toContainText('未启用')
  await expect(page.getByText('启用扩展后可查看设置和权限。')).toBeVisible()

  const enableResponse = waitForPost(page, '/api/admin/extensions/likes/enable')
  await page.locator('.ExtensionDetailToggle').click()
  await page.getByRole('button', { name: '启用', exact: true }).click()
  await enableResponse
  await expect(page.getByText('扩展已启用。')).toBeVisible()
  await page.getByRole('button', { name: '确定' }).click()
  await expect(page.locator('.ExtensionDetailToggle')).toContainText('已启用')

  await page.goto('/admin.html#/admin/extensions/core')
  await waitForExtensionDetail(page, 'core')
  await expect(page.getByRole('heading', { name: 'Core' })).toBeVisible()
  await expect(page.locator('.ExtensionDetailToggle')).toHaveCount(0)
  await expect(page.getByText('已启用')).toBeVisible()

  page.assertNoBrowserErrors()
})

function buildExtension(overrides = {}) {
  const enabled = overrides.enabled !== false
  return {
    id: overrides.id,
    name: overrides.name || overrides.id,
    version: overrides.version || '1.0.0',
    source: overrides.source || 'filesystem',
    description: overrides.description || '',
    enabled,
    installed: overrides.installed ?? true,
    booted: overrides.booted ?? enabled,
    healthy: overrides.healthy ?? true,
    protected: overrides.protected ?? false,
    product_visible: overrides.product_visible ?? true,
    icon: overrides.icon || 'fas fa-puzzle-piece',
    dependencies: overrides.dependencies || [],
    optional_dependencies: overrides.optional_dependencies || [],
    provides: overrides.provides || [],
    module_ids: overrides.module_ids || [overrides.id],
    runtime_status: overrides.runtime_status || (enabled
      ? { key: 'active', label: '已启用' }
      : { key: 'disabled', label: '已停用' }),
    lifecycle: overrides.lifecycle || { registration_mode_label: '静态注册' },
    links: overrides.links || {},
    readme: overrides.readme || { available: false, html: '' },
    action_links: overrides.action_links || {},
    admin_actions: overrides.admin_actions || [],
    runtime_actions: overrides.runtime_actions || [],
    frontend_admin_entry: overrides.frontend_admin_entry || '',
    frontend_boot: overrides.frontend_boot || {},
    settings_schema: overrides.settings_schema || [],
    settings_pages: overrides.settings_pages || [],
    permission_sections: overrides.permission_sections || [],
    diagnostics: overrides.diagnostics || {},
    recovery_status: overrides.recovery_status || {},
    frontend_asset_state: overrides.frontend_asset_state || { has_frontend: false },
    distribution: overrides.distribution || {},
    migration_plan: overrides.migration_plan || null,
  }
}

function enableAction(name) {
  return {
    key: 'enable',
    label: '启用扩展',
    action: 'enable',
    tone: 'primary',
    confirm_title: '启用扩展',
    confirm_message: `确定启用 ${name || '该扩展'} 吗？依赖校验通过后会立即恢复能力。`,
    confirm_text: '启用',
    success_message: '',
    requires_installed: true,
    order: 10,
  }
}

function disableAction(name) {
  return {
    key: 'disable',
    label: '停用扩展',
    action: 'disable',
    tone: 'danger',
    confirm_title: '停用扩展',
    confirm_message: `确定停用 ${name || '该扩展'} 吗？相关后台入口和运行能力会立即隐藏。`,
    confirm_text: '停用',
    success_message: '',
    requires_installed: true,
    order: 20,
  }
}

function uninstallAction(name) {
  return {
    key: 'uninstall',
    label: '卸载扩展',
    action: 'uninstall',
    tone: 'danger',
    confirm_title: '卸载扩展',
    confirm_message: `确定卸载 ${name || '该扩展'} 吗？扩展会从当前站点移除，相关运行能力会停用。`,
    confirm_text: '卸载',
    success_message: '',
    requires_installed: true,
    order: 30,
  }
}

function buildExtensionsPayload(extensions, state = {}) {
  return {
    extensions,
    summary: {
      extension_count: extensions.length,
      enabled_count: extensions.filter(extension => extension.enabled !== false).length,
      healthy_count: extensions.filter(extension => extension.healthy !== false).length,
      blocking_count: 0,
      warning_count: extensions.filter(extension => hasWarnings(extension)).length,
      frontend_bundle_count: extensions.filter(extension => extension.frontend_asset_state?.has_frontend).length,
      migration_bundle_count: 0,
      filesystem_count: extensions.filter(extension => extension.source === 'filesystem').length,
    },
    runtime: runtime(state.runtimeStamp || 1, state),
  }
}

function runtime(stamp, state = {}) {
  return {
    stamp: `admin-extensions-e2e-${stamp}`,
    package_lock: {
      summary: {
        locked_count: state.synced ? 4 : 3,
        missing_count: state.synced ? 0 : 1,
        version_drift_count: 0,
        source_drift_count: 0,
        unmanaged_discovered_count: 0,
      },
      enabled_order: {
        drift: !state.orderSynced,
        stale: state.orderSynced ? [] : ['missing-extension'],
      },
    },
    recovery: {
      safe_mode: true,
      safe_mode_extensions: ['core'],
      bisect: { active: false, current: [] },
    },
    frontend_rebuild: {
      rebuilt: Boolean(state.frontendRebuilt),
    },
  }
}

function hasWarnings(extension) {
  const warnings = extension?.diagnostics?.warnings
  return Array.isArray(warnings) && warnings.length > 0
}

function extensionCard(page, name) {
  return page.locator('.ExtensionCard').filter({ hasText: name }).first()
}

function waitForExtensionsResponse(page) {
  return page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === '/api/admin/extensions'
      && response.request().method() === 'GET'
      && response.status() === 200
  })
}

function waitForExtensionDetail(page, extensionId) {
  return page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === `/api/admin/extensions/${extensionId}`
      && response.request().method() === 'GET'
      && response.status() === 200
  })
}

function waitForPost(page, path) {
  return page.waitForResponse(response => {
    const url = new URL(response.url())
    return url.pathname === path
      && response.request().method() === 'POST'
      && response.status() === 200
  })
}
