import test from 'node:test'
import assert from 'node:assert/strict'

import {
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
