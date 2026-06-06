import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { resolve, relative } from 'node:path'

const repoRoot = resolve(process.cwd(), '..')
const extensionRoot = resolve(repoRoot, 'extensions')
const allowedPublicImports = new Set([
  '@/forum/registry',
  '@/admin/registry',
  '@/forum/documentRuntime',
  '@/common/extensionRuntime',
])

function listFrontendFiles(directory) {
  const output = []
  for (const entry of readdirSync(directory)) {
    const path = resolve(directory, entry)
    const stat = statSync(path)
    if (stat.isDirectory()) {
      output.push(...listFrontendFiles(path))
      continue
    }
    if (/\.(js|ts|vue)$/.test(entry)) {
      output.push(path)
    }
  }
  return output
}

function extractImports(source) {
  const imports = []
  const staticImportPattern = /import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]/g
  const dynamicImportPattern = /import\(\s*['"]([^'"]+)['"]\s*\)/g
  for (const pattern of [staticImportPattern, dynamicImportPattern]) {
    let match = pattern.exec(source)
    while (match) {
      imports.push(match[1])
      match = pattern.exec(source)
    }
  }
  return imports
}

function readExtensionForumSource(extensionId) {
  return readFileSync(resolve(extensionRoot, `${extensionId}/frontend/forum/index.js`), 'utf8')
}

function assertCoreRegistryDoesNotOwn(keys) {
  const forumRegistrySource = readFileSync(resolve(repoRoot, 'frontend/src/forum/registry.js'), 'utf8')
  for (const key of keys) {
    assert.equal(forumRegistrySource.includes(key), false, key)
  }
}

test('extension frontend imports only public app APIs', () => {
  const offenders = []
  for (const path of listFrontendFiles(extensionRoot)) {
    const source = readFileSync(path, 'utf8')
    for (const importPath of extractImports(source)) {
      if (!importPath.startsWith('@/')) {
        continue
      }
      if (allowedPublicImports.has(importPath)) {
        continue
      }
      offenders.push(`${relative(repoRoot, path)} imports ${importPath}`)
    }
  }

  assert.deepEqual(offenders, [])
})

test('mentions extension owns composer mention provider and toolbar tool registration', () => {
  const composerSource = readFileSync(resolve(repoRoot, 'frontend/src/utils/composer.js'), 'utf8')
  const mentionsForumSource = readExtensionForumSource('mentions')

  assertCoreRegistryDoesNotOwn([
    "key: 'default-users'",
    'composer-mention-loading',
    'composer-mention-empty',
    'composer-mention-picker-label',
  ])
  assert.equal(composerSource.includes("key: 'mention'"), false)
  assert.equal(mentionsForumSource.includes('new Forum()'), true)
  assert.equal(mentionsForumSource.includes('forum.composerMentionProvider'), true)
  assert.equal(mentionsForumSource.includes('forum.composerTool'), true)
  assert.equal(mentionsForumSource.includes('forum.stateBlock'), true)
  assert.equal(mentionsForumSource.includes('forum.uiCopy'), true)
  assert.equal(mentionsForumSource.includes("key: 'mention'"), true)
  assert.equal(mentionsForumSource.includes("moduleId: 'mentions'"), true)
})

test('emoji extension owns composer emoji tool and picker copy registration', () => {
  const emojiForumSource = readExtensionForumSource('emoji')

  assertCoreRegistryDoesNotOwn([
    "key: 'emoji'",
    'composer-emoji-picker-empty',
    'composer-emoji-picker-dialog-label',
    'composer-emoji-picker-search-placeholder',
    'composer-emoji-picker-summary',
    'composer-emoji-autocomplete-label',
  ])
  assert.equal(emojiForumSource.includes('new Forum()'), true)
  assert.equal(emojiForumSource.includes('forum.composerTool'), true)
  assert.equal(emojiForumSource.includes('forum.uiCopy'), true)
  assert.equal(emojiForumSource.includes("key: 'emoji'"), true)
  assert.equal(emojiForumSource.includes("moduleId: 'emoji'"), true)
})

test('tags and notifications extensions own navigational forum contributions', () => {
  const tagsForumSource = readExtensionForumSource('tags')
  const notificationsForumSource = readExtensionForumSource('notifications')

  assertCoreRegistryDoesNotOwn([
    "key: 'tags'",
    'tags-page-empty',
    'tags-page-hero-title',
    "key: 'notifications'",
    'notifications-page-empty',
    'notifications-menu-empty',
  ])
  assert.equal(tagsForumSource.includes('new Forum()'), true)
  assert.equal(tagsForumSource.includes('forum.navItem'), true)
  assert.equal(tagsForumSource.includes('forum.emptyState'), true)
  assert.equal(tagsForumSource.includes("moduleId: 'tags'"), true)
  assert.equal(notificationsForumSource.includes('new Forum()'), true)
  assert.equal(notificationsForumSource.includes('forum.navItem'), true)
  assert.equal(notificationsForumSource.includes('forum.headerItem'), true)
  assert.equal(notificationsForumSource.includes('forum.notificationRenderer'), true)
  assert.equal(notificationsForumSource.includes("moduleId: 'notifications'"), true)
})

test('approval flags subscriptions and likes own interaction contributions', () => {
  const approvalForumSource = readExtensionForumSource('approval')
  const flagsForumSource = readExtensionForumSource('flags')
  const subscriptionsForumSource = readExtensionForumSource('subscriptions')
  const likesForumSource = readExtensionForumSource('likes')

  assertCoreRegistryDoesNotOwn([
    'discussionApproved',
    'open-report-modal',
    'toggle-subscription',
    'postLiked',
  ])
  assert.equal(approvalForumSource.includes('new Forum()'), true)
  assert.equal(approvalForumSource.includes('forum.approvalNote'), true)
  assert.equal(approvalForumSource.includes('forum.discussionReviewBanner'), true)
  assert.equal(approvalForumSource.includes("moduleId: 'approval'"), true)
  assert.equal(flagsForumSource.includes('new Forum()'), true)
  assert.equal(flagsForumSource.includes('forum.postActionHandler'), true)
  assert.equal(flagsForumSource.includes('forum.postFlagPanel'), true)
  assert.equal(flagsForumSource.includes("moduleId: 'flags'"), true)
  assert.equal(subscriptionsForumSource.includes('new Forum()'), true)
  assert.equal(subscriptionsForumSource.includes('forum.discussionActionHandler'), true)
  assert.equal(subscriptionsForumSource.includes('forum.notificationRenderer'), true)
  assert.equal(subscriptionsForumSource.includes("moduleId: 'subscriptions'"), true)
  assert.equal(likesForumSource.includes('new Forum().notificationRenderer'), true)
  assert.equal(likesForumSource.includes("moduleId: 'likes'"), true)
})

test('extension frontend contributions do not claim core module ownership', () => {
  const offenders = []
  for (const path of listFrontendFiles(extensionRoot)) {
    const source = readFileSync(path, 'utf8')
    if (/\bmoduleId\s*:\s*['"]core['"]/.test(source)) {
      offenders.push(relative(repoRoot, path))
    }
  }

  assert.deepEqual(offenders, [])
})
