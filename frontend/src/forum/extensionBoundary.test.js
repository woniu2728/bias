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
  const forumRegistrySource = readFileSync(resolve(repoRoot, 'frontend/src/forum/registry.js'), 'utf8')
  const composerSource = readFileSync(resolve(repoRoot, 'frontend/src/utils/composer.js'), 'utf8')
  const mentionsForumSource = readFileSync(resolve(extensionRoot, 'mentions/frontend/forum/index.js'), 'utf8')

  assert.equal(forumRegistrySource.includes("key: 'default-users'"), false)
  assert.equal(forumRegistrySource.includes("composer-mention-loading"), false)
  assert.equal(forumRegistrySource.includes("composer-mention-empty"), false)
  assert.equal(forumRegistrySource.includes("composer-mention-picker-label"), false)
  assert.equal(composerSource.includes("key: 'mention'"), false)
  assert.equal(mentionsForumSource.includes('registerComposerMentionProvider'), true)
  assert.equal(mentionsForumSource.includes('registerComposerTool'), true)
  assert.equal(mentionsForumSource.includes('registerStateBlock'), true)
  assert.equal(mentionsForumSource.includes('registerUiCopy'), true)
  assert.equal(mentionsForumSource.includes("key: 'mention'"), true)
  assert.equal(mentionsForumSource.includes("moduleId: 'mentions'"), true)
})

test('emoji extension owns composer emoji tool and picker copy registration', () => {
  const forumRegistrySource = readFileSync(resolve(repoRoot, 'frontend/src/forum/registry.js'), 'utf8')
  const emojiForumSource = readFileSync(resolve(extensionRoot, 'emoji/frontend/forum/index.js'), 'utf8')

  assert.equal(forumRegistrySource.includes("key: 'emoji'"), false)
  assert.equal(forumRegistrySource.includes('composer-emoji-picker-empty'), false)
  assert.equal(forumRegistrySource.includes('composer-emoji-picker-dialog-label'), false)
  assert.equal(forumRegistrySource.includes('composer-emoji-picker-search-placeholder'), false)
  assert.equal(forumRegistrySource.includes('composer-emoji-picker-summary'), false)
  assert.equal(forumRegistrySource.includes('composer-emoji-autocomplete-label'), false)
  assert.equal(emojiForumSource.includes('registerComposerTool'), true)
  assert.equal(emojiForumSource.includes('registerUiCopy'), true)
  assert.equal(emojiForumSource.includes("key: 'emoji'"), true)
  assert.equal(emojiForumSource.includes("moduleId: 'emoji'"), true)
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
