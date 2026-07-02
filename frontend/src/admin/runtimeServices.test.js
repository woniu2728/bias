import assert from 'node:assert/strict'
import test from 'node:test'

import { clearFrontendServices, registerFrontendService } from '../common/services.js'
import { getAuthStore } from './runtimeServices.js'

test('admin auth store falls back before users extension service is registered', async () => {
  clearFrontendServices()
  const store = getAuthStore()

  assert.equal(store.user, null)
  assert.equal(store.isAuthenticated, false)
  assert.equal(store.hasPermission('startDiscussion'), false)

  await store.checkAuth()

  assert.equal(store.user, null)
  assert.equal(store.isAuthenticated, false)
})

test('admin auth store prefers registered users auth service', () => {
  clearFrontendServices()
  const registeredStore = {
    user: { username: 'admin', is_staff: true },
    isAuthenticated: true,
    hasPermission: () => true,
    checkAuth: async () => ({ username: 'admin', is_staff: true }),
    logout() {},
  }
  registerFrontendService('users.auth', {
    store: () => registeredStore,
  }, { extensionId: 'users' })

  assert.equal(getAuthStore(), registeredStore)
  clearFrontendServices()
})
