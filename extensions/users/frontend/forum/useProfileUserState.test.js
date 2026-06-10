import test from 'node:test'
import assert from 'node:assert/strict'
import { createProfileUserState } from './useProfileUserState.js'

function createResourceStore() {
  const bucket = {}

  return {
    get(_type, id) {
      return bucket[String(id)] || null
    },
    upsert(_type, value) {
      const normalized = { ...value, id: Number(value.id) }
      bucket[String(normalized.id)] = normalized
      return normalized
    },
  }
}

function createHarness(overrides = {}) {
  const calls = []
  const userId = { value: null }
  const activeTab = { value: overrides.activeTab ?? 'discussions' }
  const authStore = {
    user: overrides.authUser ?? { id: 7 },
  }
  const resourceStore = createResourceStore()
  const route = {
    params: {
      id: overrides.routeId ?? '7',
    },
  }

  const state = createProfileUserState({
    activeTab,
    apiClient: {
      async get(url) {
        calls.push(['get', url])
        return {
          id: Number(overrides.routeId ?? 7),
        }
      },
    },
    authStore,
    getLoadUserErrorText() {
      return '加载用户失败'
    },
    getProfileErrorMessage(error, fallback) {
      return error?.message || fallback
    },
    async loadPreferences() {
      calls.push('loadPreferences')
    },
    markPostsRequestedForCurrentUser() {
      calls.push('markPostsRequestedForCurrentUser')
    },
    normalizeUser(value) {
      return value
    },
    resourceStore,
    route,
    setEditForm(payload) {
      calls.push(['setEditForm', payload])
    },
    setLoading(value) {
      calls.push(['setLoading', value])
    },
    setSettingsError(message) {
      calls.push(['setSettingsError', message])
    },
    setVerificationError(message) {
      calls.push(['setVerificationError', message])
    },
    setVerificationSuccess(message) {
      calls.push(['setVerificationSuccess', message])
    },
    userId,
  })

  return {
    calls,
    state,
    userId,
  }
}

test('profile user state loads numeric route users and refreshes own preferences', async () => {
  const harness = createHarness()

  await harness.state.refreshProfile()

  assert.equal(harness.userId.value, 7)
  assert.deepEqual(harness.calls, [
    ['setLoading', true],
    ['get', '/users/7'],
    ['setEditForm', {
      display_name: '',
      bio: '',
      email: '',
    }],
    ['setLoading', false],
    'loadPreferences',
  ])
})

test('profile user state marks posts requested and clears verification state for foreign users', async () => {
  const harness = createHarness({
    activeTab: 'posts',
    authUser: { id: 99 },
  })

  await harness.state.loadUser()

  assert.deepEqual(harness.calls, [
    ['setLoading', true],
    ['get', '/users/7'],
    'markPostsRequestedForCurrentUser',
    ['setEditForm', {
      display_name: '',
      bio: '',
      email: '',
    }],
    ['setVerificationSuccess', ''],
    ['setVerificationError', ''],
    ['setLoading', false],
  ])
})

test('profile user state can reset current user scope', () => {
  const harness = createHarness()
  harness.userId.value = 8

  harness.state.resetUserScope()

  assert.equal(harness.userId.value, null)
})
