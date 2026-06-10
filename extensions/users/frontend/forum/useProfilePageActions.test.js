import test from 'node:test'
import assert from 'node:assert/strict'
import { useProfilePageActions } from './useProfilePageActions.js'

test('profile page actions skip unchanged tabs', () => {
  const calls = []
  const actions = useProfilePageActions({
    activeTab: { value: 'discussions' },
    markPostsRequestedForCurrentUser() {
      calls.push('markPostsRequestedForCurrentUser')
    },
    pushRouteState(payload) {
      calls.push(['pushRouteState', payload])
    },
    userId: { value: 7 },
  })

  const changed = actions.switchTab(' discussions ')

  assert.equal(changed, false)
  assert.deepEqual(calls, [])
})

test('profile page actions normalize target tab and prepare post panel loading', () => {
  const calls = []
  const actions = useProfilePageActions({
    activeTab: { value: 'discussions' },
    markPostsRequestedForCurrentUser() {
      calls.push('markPostsRequestedForCurrentUser')
    },
    pushRouteState(payload) {
      calls.push(['pushRouteState', payload])
      return true
    },
    userId: { value: 7 },
  })

  const changed = actions.switchTab('posts')

  assert.equal(changed, true)
  assert.deepEqual(calls, [
    'markPostsRequestedForCurrentUser',
    ['pushRouteState', { activeTab: 'posts' }],
  ])
})

test('profile page actions fall back to discussions without post preload when user is absent', () => {
  const calls = []
  const actions = useProfilePageActions({
    activeTab: { value: 'settings' },
    markPostsRequestedForCurrentUser() {
      calls.push('markPostsRequestedForCurrentUser')
    },
    pushRouteState(payload) {
      calls.push(['pushRouteState', payload])
    },
    userId: { value: null },
  })

  const changed = actions.switchTab('')

  assert.equal(changed, true)
  assert.deepEqual(calls, [
    ['pushRouteState', { activeTab: 'discussions' }],
  ])
})
