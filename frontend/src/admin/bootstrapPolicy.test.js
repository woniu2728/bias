import test from 'node:test'
import assert from 'node:assert/strict'

import {
  filterPreloadAdminExtensions,
  shouldPreloadAdminExtension,
} from './bootstrapPolicy.js'

test('admin boot preloads only enabled extensions that declare admin boot work', () => {
  const auth = { id: 'users', enabled: true, frontend_boot: { admin: true } }
  const tags = { id: 'tags', enabled: true, frontend_boot: { admin: false } }
  const uploads = { id: 'uploads', enabled: true }
  const disabledAuth = { id: 'disabled-users', enabled: false, frontend_boot: { admin: true } }

  assert.equal(shouldPreloadAdminExtension(auth), true)
  assert.equal(shouldPreloadAdminExtension(tags), false)
  assert.equal(shouldPreloadAdminExtension(uploads), false)
  assert.equal(shouldPreloadAdminExtension(disabledAuth), false)
  assert.deepEqual(
    filterPreloadAdminExtensions([auth, tags, uploads, disabledAuth]).map(extension => extension.id),
    ['users'],
  )
})
