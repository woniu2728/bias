import test from 'node:test'
import assert from 'node:assert/strict'
import { resolveProfileOnlineState } from './profileOnlineState.js'

test('profile online state prefers realtime presence when available', () => {
  const isOnline = resolveProfileOnlineState({
    userId: 7,
    lastSeenAt: '2000-01-01T00:00:00Z',
    isUserOnline: (userId) => userId === 7,
  })

  assert.equal(isOnline, true)
})

test('profile online state falls back to recent last seen when realtime presence is absent', () => {
  const recent = new Date(Date.now() - (2 * 60 * 1000)).toISOString()
  const isOnline = resolveProfileOnlineState({
    userId: 8,
    lastSeenAt: recent,
    isUserOnline: () => false,
  })

  assert.equal(isOnline, true)
})

test('profile online state marks stale users offline without realtime presence', () => {
  const stale = new Date(Date.now() - (10 * 60 * 1000)).toISOString()
  const isOnline = resolveProfileOnlineState({
    userId: 9,
    lastSeenAt: stale,
    isUserOnline: () => false,
  })

  assert.equal(isOnline, false)
})
