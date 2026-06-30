import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveForumRouteGuard } from './guards.js'

test('auth route guard waits for session restoration before protecting direct routes', async () => {
  const calls = []
  const authStore = {
    isAuthenticated: false,
    isRestoringSession: true,
    async checkAuth() {
      calls.push('checkAuth')
      this.isAuthenticated = true
      this.isRestoringSession = false
    },
  }

  const result = await resolveForumRouteGuard({
    to: {
      name: 'discussion-create',
      fullPath: '/discussions/create',
      meta: { requiresAuth: true },
    },
    from: { matched: [], fullPath: '/' },
    authStore,
  })

  assert.equal(result, true)
  assert.deepEqual(calls, ['checkAuth'])
})

test('auth route guard redirects direct protected routes when restored session is guest', async () => {
  const authStore = {
    isAuthenticated: false,
    isRestoringSession: true,
    async checkAuth() {
      this.isRestoringSession = false
    },
  }

  const result = await resolveForumRouteGuard({
    to: {
      name: 'discussion-create',
      fullPath: '/discussions/create',
      meta: { requiresAuth: true },
    },
    from: { matched: [], fullPath: '/' },
    authStore,
  })

  assert.deepEqual(result, {
    name: 'login',
    query: { redirect: '/discussions/create' },
  })
})

test('auth route guard opens login modal for in-app protected navigation by guests', async () => {
  const loginCalls = []
  const result = await resolveForumRouteGuard({
    to: {
      name: 'discussion-create',
      fullPath: '/discussions/create',
      meta: { requiresAuth: true },
    },
    from: { matched: [{}], fullPath: '/' },
    authStore: {
      isAuthenticated: false,
      isRestoringSession: false,
    },
    openLogin(options) {
      loginCalls.push(options)
    },
  })

  assert.equal(result, false)
  assert.deepEqual(loginCalls, [{ redirectPath: '/discussions/create' }])
})
