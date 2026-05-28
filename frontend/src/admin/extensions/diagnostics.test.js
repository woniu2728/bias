import test from 'node:test'
import assert from 'node:assert/strict'

import {
  resolveExtensionAdminPageCards,
  resolveExtensionAdminPageLabels,
  resolveExtensionAdminSurfaceCards,
  resolveExtensionEntryTypeLabel,
  resolveExtensionForumEntryState,
  resolveExtensionMigrationState,
} from './diagnostics.js'

test('resolveExtensionEntryTypeLabel maps entry kinds to readable labels', () => {
  assert.equal(resolveExtensionEntryTypeLabel('builtin'), '内置入口')
  assert.equal(resolveExtensionEntryTypeLabel('filesystem'), '文件系统扩展')
  assert.equal(resolveExtensionEntryTypeLabel('external'), '外部路径')
  assert.equal(resolveExtensionEntryTypeLabel('unknown'), '未声明')
})

test('resolveExtensionForumEntryState detects forum entry health', () => {
  assert.equal(resolveExtensionForumEntryState({}), '未声明')
  assert.equal(resolveExtensionForumEntryState({
    frontend_forum_entry: 'extensions/sample-hello/frontend/forum/index.js',
    debug_info: {
      frontend_forum_entry: {
        exists: false,
      },
    },
  }), '缺失')
  assert.equal(resolveExtensionForumEntryState({
    frontend_forum_entry: 'extensions/sample-hello/frontend/forum/index.js',
    debug_info: {
      frontend_forum_entry: {
        exists: true,
        required_exports: ['bootForumExtension'],
        available_exports: ['bootForumExtension'],
      },
    },
  }), '已就绪')
})

test('resolveExtensionMigrationState reflects pending and applied migration plans', () => {
  assert.equal(resolveExtensionMigrationState({}), '未声明')
  assert.equal(resolveExtensionMigrationState({
    migration_plan: {
      pending_files: ['0001_initial.py'],
      applied_files: [],
    },
  }), '待执行')
  assert.equal(resolveExtensionMigrationState({
    migration_execution: {
      status: 'ok',
    },
    migration_plan: {
      pending_files: ['0002_seed.py'],
      applied_files: ['0001_initial.py'],
    },
  }), '有更新')
  assert.equal(resolveExtensionMigrationState({
    migration_plan: {
      pending_files: [],
      applied_files: ['0001_initial.py'],
    },
  }), '已同步')
})

test('resolveExtensionAdminSurfaceCards builds readable admin host summaries', () => {
  const cards = resolveExtensionAdminSurfaceCards({
    action_links: {
      settings_page: '/admin/extensions/sample-hello/settings',
      permissions_page: '/admin/extensions/sample-hello/permissions',
      operations_page: '/admin/extensions/sample-hello/operations',
    },
    settings_schema: [{ key: 'welcome_message' }, { key: 'card_tone' }],
    permission_summary: {
      permission_count: 3,
      section_count: 2,
    },
    admin_actions: [{ key: 'details' }, { key: 'docs' }],
    runtime_actions: [{ key: 'install' }],
    debug_info: {
      admin_surface_statuses: [
        { key: 'settings', mode: 'generated', mode_label: '自动生成' },
        { key: 'permissions', mode: 'generated', mode_label: '自动生成' },
        { key: 'operations', mode: 'custom', mode_label: '自定义组件' },
      ],
    },
  })

  assert.equal(cards.length, 3)
  assert.deepEqual(cards.map(item => item.key), ['settings', 'permissions', 'operations'])
  assert.equal(cards[0].summary, '自动生成 2 个设置项')
  assert.equal(cards[1].summary, '3 项权限，2 个分组')
  assert.equal(cards[2].summary, '2 个后台动作，1 个运行操作')
})

test('resolveExtensionAdminPageCards normalizes core internal carrier targets', () => {
  const cards = resolveExtensionAdminPageCards({
    admin_page_details: [
      { path: '/admin', label: '仪表盘' },
      { path: '/admin/basics', label: '基础设置', settings_group: 'basic', icon: 'fas fa-pencil-alt' },
      { path: '/admin/appearance', label: '外观设置', settings_group: 'appearance' },
      { path: '/admin/mail', label: '邮件设置', settings_group: 'mail' },
      { path: '/admin/advanced', label: '高级设置', settings_group: 'advanced' },
      { path: '/admin/audit-logs', label: '审计日志' },
      { path: '/admin/docs', label: '开发者文档' },
    ],
  }, { hostKind: 'operations' })

  assert.deepEqual(cards.map(item => item.path), ['/admin/advanced', '/admin/audit-logs', '/admin/docs'])
  assert.deepEqual(cards.map(item => item.target), [
    '/admin/internal/core/advanced',
    '/admin/internal/core/audit-logs',
    '/admin/internal/core/docs',
  ])
})

test('resolveExtensionAdminPageLabels extracts readable labels from admin pages', () => {
  assert.deepEqual(resolveExtensionAdminPageLabels({
    admin_page_details: [
      { path: '/admin/basics', label: '基础设置' },
      { path: '/admin/mail', label: '邮件设置' },
    ],
  }), ['基础设置', '邮件设置'])
})
