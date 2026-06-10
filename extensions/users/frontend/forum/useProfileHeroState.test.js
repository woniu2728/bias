import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createProfileHeroState } from './useProfileHeroState.js'

test('profile hero state splits group badge from inline badges and resolves copy', () => {
  const state = createProfileHeroState({
    avatarUploading: ref(true),
    formatJoinDate: value => `join:${value}`,
    formatLastSeen: value => `seen:${value}`,
    getHeroMeta: () => [{ key: 'joined', text: '2024-01' }],
    getText: ({ surface }) => ({ text: `${surface}-copy` }),
    isOnline: ref(true),
    user: ref({ id: 7 }),
    userBadges: ref([
      { key: 'group', variant: 'group', label: 'Admin' },
      { key: 'vip', variant: 'role', label: 'VIP' },
    ]),
  })

  assert.deepEqual(state.primaryGroupBadge.value, { key: 'group', variant: 'group', label: 'Admin' })
  assert.deepEqual(state.inlineBadges.value, [{ key: 'vip', variant: 'role', label: 'VIP' }])
  assert.deepEqual(state.heroMetaItems.value, [{ key: 'joined', text: '2024-01' }])
  assert.equal(state.avatarUploadText.value, 'profile-hero-avatar-upload-copy')
  assert.equal(state.settingsButtonText.value, 'profile-hero-settings-button-copy')
})

test('profile hero state falls back to defaults when registry values are absent', () => {
  const state = createProfileHeroState({
    avatarUploading: ref(false),
    formatJoinDate: value => value,
    formatLastSeen: value => value,
    getHeroMeta: () => [],
    getText: () => null,
    isOnline: ref(false),
    user: ref({ id: 7 }),
    userBadges: ref(null),
  })

  assert.equal(state.primaryGroupBadge.value, null)
  assert.deepEqual(state.inlineBadges.value, [])
  assert.equal(state.avatarUploadText.value, '更换头像')
  assert.equal(state.settingsButtonText.value, '设置')
})
