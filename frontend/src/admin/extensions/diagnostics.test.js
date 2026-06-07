import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildExtensionDetailRouteTarget,
  buildExtensionRouteTarget,
  resolveExtensionBackTarget,
  resolveExtensionAdminPageCards,
  resolveExtensionAdminPageLabels,
  resolveExtensionDiagnostics,
  resolveExtensionDiagnosticsBadges,
  resolveExtensionDiagnosticsPreview,
  resolveExtensionPrimaryAdminAction,
  resolveExtensionOperationsActionGroups,
  resolveExtensionOperationsProfile,
  resolveExtensionOperationsFocusSections,
  resolveExtensionOperationsNextSteps,
  resolveExtensionOperationsSections,
  resolveExtensionAdminSurfaceCards,
  resolveExtensionCapabilityPanels,
  resolveExtensionCapabilitySummaryItems,
  resolveExtensionEntryTypeLabel,
  resolveExtensionForumEntryState,
  resolveExtensionMigrationState,
  resolveExtensionNavigationSource,
} from './diagnostics.js'

test('resolveExtensionEntryTypeLabel maps entry kinds to readable labels', () => {
  assert.equal(resolveExtensionEntryTypeLabel('filesystem'), '文件系统扩展')
  assert.equal(resolveExtensionEntryTypeLabel('external'), '外部路径')
  assert.equal(resolveExtensionEntryTypeLabel('unknown'), '未声明')
})

test('resolveExtensionForumEntryState detects forum entry health', () => {
  assert.equal(resolveExtensionForumEntryState({}), '未声明')
  assert.equal(resolveExtensionForumEntryState({
    frontend_forum_entry: 'extensions/alpha-tools/frontend/forum/index.js',
    debug_info: {
      frontend_forum_entry: {
        exists: false,
      },
    },
  }), '缺失')
  assert.equal(resolveExtensionForumEntryState({
    frontend_forum_entry: 'extensions/alpha-tools/frontend/forum/index.js',
    debug_info: {
      frontend_forum_entry: {
        exists: true,
        required_exports: ['extend'],
        available_exports: ['extend'],
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

test('resolveExtensionDiagnostics normalizes blocking and warning payloads', () => {
  const diagnostics = resolveExtensionDiagnostics({
    diagnostics: {
      blocking: true,
      warning: true,
      has_attention: true,
      blocking_reasons: ['运行时健康检查未通过'],
      warning_reasons: ['迁移状态待完善'],
    },
  })

  assert.equal(diagnostics.blocking, true)
  assert.equal(diagnostics.warning, true)
  assert.equal(diagnostics.hasAttention, true)
  assert.deepEqual(diagnostics.blockingReasons, ['运行时健康检查未通过'])
  assert.deepEqual(diagnostics.warningReasons, ['迁移状态待完善'])
})

test('resolveExtensionDiagnosticsBadges and preview build concise UI payloads', () => {
  const extension = {
    diagnostics: {
      blocking: true,
      warning: true,
      has_attention: true,
      blocking_reasons: ['存在运行时问题', '依赖状态异常'],
      warning_reasons: ['迁移状态待完善'],
    },
  }

  assert.deepEqual(resolveExtensionDiagnosticsBadges(extension), [
    { key: 'blocking', label: '阻断 2', tone: 'danger' },
    { key: 'warning', label: '告警 1', tone: 'warning' },
  ])
  assert.deepEqual(resolveExtensionDiagnosticsPreview(extension), [
    { key: 'blocking-存在运行时问题', tone: 'danger', text: '存在运行时问题' },
    { key: 'blocking-依赖状态异常', tone: 'danger', text: '依赖状态异常' },
  ])
})

test('resolveExtensionAdminSurfaceCards builds readable admin host summaries', () => {
  const cards = resolveExtensionAdminSurfaceCards({
    action_links: {
      settings_page: '/admin/extensions/alpha-tools/settings',
      permissions_page: '/admin/extensions/alpha-tools/permissions',
      operations_page: '/admin/extensions/alpha-tools/operations',
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

test('resolveExtensionAdminPageCards keeps core admin targets as first-class admin routes', () => {
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

  assert.deepEqual(cards.map(item => item.path), ['/admin/advanced', '/admin/audit-logs'])
  assert.deepEqual(cards.map(item => item.target), [
    '/admin/advanced',
    '/admin/audit-logs',
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

test('extension navigation helpers preserve source and fallback targets', () => {
  assert.equal(resolveExtensionNavigationSource('extensions'), 'extensions')
  assert.equal(resolveExtensionNavigationSource({ query: { from: 'extensions' } }), 'extensions')
  assert.equal(resolveExtensionNavigationSource({ query: {} }), '')

  assert.deepEqual(buildExtensionRouteTarget('/admin/extensions/core/settings', 'extensions'), {
    path: '/admin/extensions/core/settings',
    query: { from: 'extensions' },
  })
  assert.equal(buildExtensionRouteTarget('/admin/extensions/core/settings', ''), '/admin/extensions/core/settings')
  assert.deepEqual(buildExtensionDetailRouteTarget('core', { query: { from: 'extensions' } }), {
    path: '/admin/extensions/core',
    query: { from: 'extensions' },
  })
  assert.deepEqual(buildExtensionRouteTarget('/admin/extensions/approval', {
    query: {
      from: 'extensions',
      module: 'approval',
    },
  }), {
    path: '/admin/extensions/approval',
    query: {
      from: 'extensions',
      module: 'approval',
    },
  })
  assert.equal(resolveExtensionBackTarget({ query: { from: 'unknown', module: 'approval' } }, '/admin'), '/admin')
  assert.equal(resolveExtensionBackTarget({ query: { from: 'extensions' } }, '/admin'), '/admin')
  assert.equal(resolveExtensionBackTarget({ query: {} }, '/admin'), '/admin')
})

test('resolveExtensionCapabilitySummaryItems keeps only non-zero capability counters', () => {
  const items = resolveExtensionCapabilitySummaryItems({
    capability_summary: {
      notification_type_count: 2,
      user_preference_count: 0,
      event_listener_count: 1,
      search_filter_count: 0,
      resource_field_count: 3,
    },
  })

  assert.deepEqual(items, [
    { key: 'notification_type_count', label: '通知类型', count: 2 },
    { key: 'event_listener_count', label: '事件监听', count: 1 },
    { key: 'resource_field_count', label: '资源字段', count: 3 },
  ])
})

test('resolveExtensionCapabilityPanels normalizes capability groups for detail page', () => {
  const panels = resolveExtensionCapabilityPanels({
    notification_types: [
      {
        module_id: 'approval',
        code: 'discussionApproved',
        label: '讨论审核通过',
        preference_key: 'notify_discussion_approval',
        description: '通知作者其讨论已通过审核。',
      },
    ],
    search_filters: [
      {
        module_id: 'discussions',
        target: 'discussion',
        code: 'author',
        label: '按作者过滤',
        syntax: 'author:<username>',
        description: '按讨论作者用户名过滤搜索结果。',
      },
    ],
    resource_fields: [
      {
        module_id: 'tags',
        resource: 'tag',
        field: 'can_start_discussion',
        description: '标签是否允许发帖。',
      },
    ],
  })

  assert.equal(panels.length, 3)
  assert.deepEqual(panels.map(item => item.key), ['notification_types', 'search_filters', 'resource_fields'])
  assert.equal(panels[0].items[0].meta, 'notify_discussion_approval')
  assert.equal(panels[0].items[0].moduleId, 'approval')
  assert.equal(panels[1].items[0].meta, 'author:<username>')
  assert.equal(panels[1].items[0].moduleId, 'discussions')
  assert.equal(panels[2].items[0].label, 'tag.can_start_discussion')
  assert.equal(panels[2].items[0].moduleId, 'tags')
})

test('resolveExtensionAdminPageCards can isolate operations host pages', () => {
  const cards = resolveExtensionAdminPageCards({
    admin_page_details: [
      { path: '/admin/advanced', label: '高级设置', icon: 'fas fa-cog' },
      { path: '/admin/audit-logs', label: '审计日志', icon: 'fas fa-clipboard-list' },
      { path: '/admin/docs', label: '开发者文档', icon: 'fas fa-book' },
      { path: '/admin/mail', label: '邮件设置', settings_group: 'mail' },
    ],
  }, { hostKind: 'operations' })

  assert.deepEqual(cards.map(item => item.path), [
    '/admin/advanced',
    '/admin/audit-logs',
  ])
})

test('resolveExtensionPrimaryAdminAction prefers hosted settings and operations routes', () => {
  assert.equal(resolveExtensionPrimaryAdminAction({
    admin_actions: [
      { key: 'details', kind: 'route', target: '/admin/extensions/notifications' },
      { key: 'operations', kind: 'route', target: '/admin/extensions/notifications/operations' },
    ],
  })?.key, 'operations')

  assert.equal(resolveExtensionPrimaryAdminAction({
    admin_actions: [
      { key: 'details', kind: 'route', target: '/admin/extensions/tags' },
      { key: 'settings', kind: 'route', target: '/admin/extensions/tags/settings' },
    ],
  })?.key, 'settings')
})

test('resolveExtensionOperationsProfile derives default copy from capabilities', () => {
  const profile = resolveExtensionOperationsProfile({
    id: 'runtime-demo',
    name: '运行演示',
    notification_types: [{ module_id: 'runtime-demo', code: 'demo', label: '演示通知' }],
    event_listeners: [{ module_id: 'runtime-demo', event: 'DemoEvent', listener: 'handle_demo' }],
  })

  assert.equal(profile.kicker, 'Extension Operations')
  assert.equal(profile.title, '运行演示 操作宿主')
  assert.ok(profile.description.includes('通知类型、事件监听'))
  assert.deepEqual(profile.highlights, ['通知类型', '事件监听'])
  assert.deepEqual(profile.focusPanels.map(item => item.key), ['notification_types', 'event_listeners'])
})

test('resolveExtensionOperationsProfile accepts explicit extension profile overrides', () => {
  const profile = resolveExtensionOperationsProfile({
    id: 'custom-profile',
    name: '自定义扩展',
    notification_types: [{ module_id: 'custom-profile', code: 'demo', label: '演示通知' }],
    operations_profile: {
      kicker: 'Custom Runtime',
      title: '自定义操作页',
      highlights: ['自定义摘要'],
      focus_panels: [
        { key: 'notification_types', title: '自定义通知', description: '扩展自己声明的说明。' },
      ],
      recommended_action_keys: ['settings'],
      next_steps: ['补齐自定义页面。'],
    },
  })

  assert.equal(profile.kicker, 'Custom Runtime')
  assert.equal(profile.title, '自定义操作页')
  assert.deepEqual(profile.highlights, ['自定义摘要'])
  assert.equal(profile.focusPanels[0].title, '自定义通知')
  assert.deepEqual(profile.recommendedActionKeys, ['settings'])
  assert.deepEqual(profile.nextSteps, ['补齐自定义页面。'])
})

test('resolveExtensionOperationsFocusSections maps profile focus panels to capability groups', () => {
  const sections = resolveExtensionOperationsFocusSections({
    id: 'subscriptions',
    user_preferences: [
      {
        module_id: 'subscriptions',
        key: 'follow_after_reply',
        label: '回复后自动关注',
        description: '参与讨论后自动关注。',
      },
    ],
    discussion_list_filters: [
      {
        module_id: 'subscriptions',
        code: 'following',
        label: '关注中',
        route_path: '/following',
        description: '仅看已关注讨论。',
      },
    ],
    event_listeners: [
      {
        module_id: 'subscriptions',
        event: 'PostCreatedEvent',
        listener: 'handle_post_created',
        description: '回复后分发关注通知。',
      },
    ],
  })

  assert.deepEqual(sections.map(item => item.key), [
    'user_preferences',
    'event_listeners',
    'discussion_list_filters',
  ])
  assert.equal(sections[0].title, '用户偏好')
  assert.equal(sections[2].items[0].label, '关注中')
})

test('resolveExtensionOperationsActionGroups promotes primary actions and keeps runtime actions separate', () => {
  const groups = resolveExtensionOperationsActionGroups({
    admin_actions: [
      { key: 'details', kind: 'route', target: '/admin/extensions/likes' },
      { key: 'operations', kind: 'route', target: '/admin/extensions/likes/operations' },
      { key: 'documentation', kind: 'link', target: 'https://example.com/docs' },
    ],
    runtime_actions: [
      { key: 'enable', action: 'enable', label: '启用' },
    ],
  })

  assert.deepEqual(groups.map(item => item.key), ['recommended', 'admin', 'runtime'])
  assert.deepEqual(groups[0].actions.map(item => item.key), ['operations', 'details'])
  assert.deepEqual(groups[1].actions.map(item => item.key), ['documentation'])
  assert.deepEqual(groups[2].actions.map(item => item.key), ['enable'])
})

test('resolveExtensionOperationsNextSteps warns when extension still uses generated operations host', () => {
  const nextSteps = resolveExtensionOperationsNextSteps({
    id: 'generated-demo',
    debug_info: {
      admin_surface_statuses: [
        { key: 'operations', mode: 'generated' },
      ],
    },
  })

  assert.ok(nextSteps.some(item => item.includes('resolveOperationsPage')))
})

test('resolveExtensionOperationsSections returns a normalized operations payload', () => {
  const sections = resolveExtensionOperationsSections({
    id: 'mentions',
    admin_actions: [
      { key: 'operations', kind: 'route', target: '/admin/extensions/mentions/operations' },
    ],
    notification_types: [
      {
        module_id: 'mentions',
        code: 'userMentioned',
        label: '@提及通知',
        preference_key: 'notify_user_mentioned',
      },
    ],
  })

  assert.equal(sections.profile.title, 'mentions 操作宿主')
  assert.equal(sections.capabilitySummaryItems[0].key, 'notification_type_count')
  assert.equal(sections.actionGroups[0].key, 'recommended')
})

test('resolveExtensionOperationsSections can summarize core discussion capabilities without backend counters', () => {
  const sections = resolveExtensionOperationsSections({
    id: 'discussions',
    admin_actions: [
      { key: 'permissions', kind: 'route', target: '/admin/extensions/discussions/permissions' },
      { key: 'operations', kind: 'route', target: '/admin/extensions/discussions/operations' },
    ],
    discussion_sorts: [
      { module_id: 'discussions', code: 'latest', label: '最新活跃' },
    ],
    discussion_list_filters: [
      { module_id: 'discussions', code: 'all', label: '全部讨论', route_path: '/' },
    ],
    search_filters: [
      { module_id: 'discussions', target: 'discussion', code: 'author', label: '按作者过滤', syntax: 'author:<username>' },
    ],
  })

  assert.deepEqual(sections.capabilitySummaryItems.map(item => item.key), [
    'search_filter_count',
    'discussion_sort_count',
    'discussion_list_filter_count',
  ])
  assert.deepEqual(sections.focusSections.map(item => item.key), [
    'search_filters',
    'discussion_sorts',
    'discussion_list_filters',
  ])
})
