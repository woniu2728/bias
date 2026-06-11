import test from 'node:test'
import assert from 'node:assert/strict'

import './bootstrap/dashboard.js'
import {
  getAdminDashboardConfig,
  getAdminDashboardCopy,
  getAdminDashboardStats,
} from './dashboard.js'

test('core dashboard bootstrap registers fallback forum stats', () => {
  const copy = getAdminDashboardCopy({ isModuleEnabled: () => true })
  const config = getAdminDashboardConfig({ isModuleEnabled: () => true })
  const stats = getAdminDashboardStats({
    stats: {
      ...(config?.defaultStats || {}),
      totalUsers: 2,
      totalDiscussions: 3,
      totalPosts: 5,
    },
    copy,
    isModuleEnabled: () => true,
  })

  assert.deepEqual(
    stats
      .filter(item => ['users', 'discussions', 'posts'].includes(item.key))
      .map(item => ({ key: item.key, label: item.label, value: item.value })),
    [
      { key: 'users', label: '用户总数', value: 2 },
      { key: 'discussions', label: '讨论总数', value: 3 },
      { key: 'posts', label: '帖子总数', value: 5 },
    ],
  )
})
