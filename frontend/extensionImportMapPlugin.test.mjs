import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'

import { normalizeExtensionImportMapSource } from './extensionImportMapPlugin.mjs'

test('normalizeExtensionImportMapSource removes stale relative dynamic imports', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bias-import-map-'))
  try {
    const generatedDir = path.join(root, 'frontend', 'src', 'generated')
    const liveEntry = path.join(root, 'extensions', 'live', 'frontend', 'forum')
    fs.mkdirSync(generatedDir, { recursive: true })
    fs.mkdirSync(liveEntry, { recursive: true })
    fs.writeFileSync(path.join(liveEntry, 'index.js'), 'export const extend = []\n')

    const source = [
      'export const generatedForumExtensionModules = {',
      '  "live": () => import("../../../extensions/live/frontend/forum/index.js"),',
      '  "stale": () => import("../../../extensions/stale/frontend/forum/index.js"),',
      '}',
      '',
    ].join('\n')

    const normalized = normalizeExtensionImportMapSource(
      source,
      path.join(root, 'frontend'),
      path.join(generatedDir, 'extensionImportMap.js'),
    )

    assert.match(normalized, /"live"/)
    assert.doesNotMatch(normalized, /"stale"/)
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('normalizeExtensionImportMapSource returns fallback for empty files', () => {
  const normalized = normalizeExtensionImportMapSource('', process.cwd())

  assert.match(normalized, /generatedAdminExtensionModules = \{\}/)
  assert.match(normalized, /generatedForumExtensionModules = \{\}/)
})
