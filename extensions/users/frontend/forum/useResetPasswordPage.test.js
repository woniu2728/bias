import test from 'node:test'
import assert from 'node:assert/strict'
import { createResetPasswordPage } from './useResetPasswordPage.js'

test('reset password page blocks mismatched passwords before request', async () => {
  const page = createResetPasswordPage({
    apiClient: {
      async post() {
        throw new Error('should not call api')
      },
    },
  })

  page.form.password = 'abc123'
  page.form.passwordConfirm = 'xyz999'

  const result = await page.submit()

  assert.equal(result, false)
  assert.equal(page.error.value, '两次输入的新密码不一致')
  assert.equal(page.loading.value, false)
})

test('reset password page stores success and schedules login redirect', async () => {
  const calls = []
  const page = createResetPasswordPage({
    apiClient: {
      async post(path, payload) {
        calls.push(['post', path, payload.token, payload.password])
      },
    },
    initialToken: 'token-1',
    navigateToLogin(path) {
      calls.push(['push', path])
    },
    resolveUiText(surface, fallback) {
      return surface === 'reset-password-success' ? '已重置' : fallback
    },
    scheduleRedirect(callback, delay) {
      calls.push(['schedule', delay])
      callback()
    },
  })

  page.form.password = 'abc123'
  page.form.passwordConfirm = 'abc123'

  const result = await page.submit()

  assert.equal(result, true)
  assert.equal(page.success.value, '已重置')
  assert.equal(page.error.value, '')
  assert.deepEqual(calls, [
    ['post', '/users/reset-password', 'token-1', 'abc123'],
    ['schedule', 1500],
    ['push', '/login'],
  ])
})
