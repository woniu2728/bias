import test from 'node:test'
import assert from 'node:assert/strict'
import { createVerifyEmailPage } from './useVerifyEmailPage.js'

test('verify email page skips empty token without loading', async () => {
  const page = createVerifyEmailPage({
    apiClient: {
      post() {
        throw new Error('should not call api')
      },
    },
    authStore: {
      isAuthenticated: false,
      async fetchUser() {},
    },
  })

  const result = await page.verifyToken('')

  assert.equal(result, false)
  assert.equal(page.loading.value, false)
  assert.equal(page.success.value, '')
  assert.equal(page.error.value, '')
})

test('verify email page stores success and refreshes current user', async () => {
  const calls = []
  const page = createVerifyEmailPage({
    apiClient: {
      async post(path, payload) {
        calls.push(['post', path, payload.token])
      },
    },
    authStore: {
      isAuthenticated: true,
      async fetchUser() {
        calls.push('fetch-user')
      },
    },
    resolveUiText(surface, fallback) {
      return surface === 'verify-email-success' ? '验证成功' : fallback
    },
  })

  const result = await page.verifyToken('abc123')

  assert.equal(result, true)
  assert.equal(page.success.value, '验证成功')
  assert.equal(page.error.value, '')
  assert.deepEqual(calls, [
    ['post', '/users/verify-email', 'abc123'],
    'fetch-user',
  ])
})
