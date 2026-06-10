import test from 'node:test'
import assert from 'node:assert/strict'
import { createAuthRoutePage, resolveAuthRouteMode } from './useAuthRoutePage.js'

test('auth route page resolves route mode with login fallback', () => {
  assert.equal(resolveAuthRouteMode('register'), 'register')
  assert.equal(resolveAuthRouteMode('forgot-password'), 'forgot-password')
  assert.equal(resolveAuthRouteMode('login'), 'login')
  assert.equal(resolveAuthRouteMode('anything-else'), 'login')
})

test('auth route page opens target modal and redirects home', () => {
  const calls = []
  const page = createAuthRoutePage({
    route: {
      name: 'register',
      query: {
        redirect: '/profile',
      },
    },
    router: {
      replace(path) {
        calls.push(['replace', path])
      },
    },
    openForgotPassword(options) {
      calls.push(['forgot', options.redirectPath])
    },
    openLogin(options) {
      calls.push(['login', options.redirectPath])
    },
    openRegister(options) {
      calls.push(['register', options.redirectPath])
    },
  })

  page.run()

  assert.equal(page.mode, 'register')
  assert.equal(page.redirectPath, '/profile')
  assert.deepEqual(calls, [
    ['register', '/profile'],
    ['replace', '/'],
  ])
})
