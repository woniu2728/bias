import test from 'node:test'
import assert from 'node:assert/strict'

import {
  loadEnabledForumExtensions,
  loadExtensionForumEntryModule,
  normalizeExtensionForumEntry,
  validateForumExtensionModule,
} from './extensionLoader.js'

test('normalizeExtensionForumEntry rewrites extension paths', () => {
  assert.equal(
    normalizeExtensionForumEntry('extensions/sample-hello/frontend/forum/index.js'),
    '../../../extensions/sample-hello/frontend/forum/index.js',
  )
  assert.equal(normalizeExtensionForumEntry(''), '')
})

test('loadExtensionForumEntryModule loads filesystem importer entries', async () => {
  const loaded = await loadExtensionForumEntryModule('../../../extensions/sample-hello/frontend/forum/index.js', {
    importers: {
      '../../../extensions/sample-hello/frontend/forum/index.js': async () => ({
        boot: true,
      }),
    },
  })

  assert.equal(loaded.boot, true)
})

test('validateForumExtensionModule rejects modules without bootForumExtension', () => {
  assert.throws(
    () => validateForumExtensionModule({}),
    /bootForumExtension/,
  )
})

test('loadEnabledForumExtensions loads enabled extension entries once and applies payload', async () => {
  const calls = []
  const forumStore = {
    applied: null,
    applyPublicSettings(payload) {
      this.applied = payload
    },
  }

  const payload = {
    enabled_extensions: [
      {
        id: 'sample-hello',
        frontend_forum_entry: 'extensions/sample-hello/frontend/forum/index.js',
      },
      {
        id: 'sample-hello',
        frontend_forum_entry: 'extensions/sample-hello/frontend/forum/index.js',
      },
    ],
  }

  const result = await loadEnabledForumExtensions({
    forumStore,
    fetchPayload: async () => payload,
    importers: {
      '../../../extensions/sample-hello/frontend/forum/index.js': async () => {
        calls.push('sample-hello')
        return {
          bootForumExtension: async ({ extension }) => {
            calls.push(extension.id)
          },
        }
      },
    },
  })

  assert.equal(calls.length, 2)
  assert.equal(result.loadedExtensionIds.has('sample-hello'), true)
  assert.equal(forumStore.applied, payload)
})
