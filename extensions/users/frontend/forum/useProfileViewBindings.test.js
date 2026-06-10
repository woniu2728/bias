import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createProfileViewBindings } from './useProfileViewBindings.js'

test('profile view bindings expose hero and sidebar props from reactive state', () => {
  const bindings = createProfileViewBindings({
    activeTab: ref('discussions'),
    activePanel: ref({
      component: 'PanelComponent',
      componentProps: { posts: [] },
      componentEvents: { save: () => 'saved' },
    }),
    avatarInput: ref('avatar-ref'),
    avatarUploading: ref(true),
    formatJoinDate: value => `join:${value}`,
    formatLastSeen: value => `seen:${value}`,
    getUserAvatarColor: () => '#000',
    getUserPrimaryGroupColor: () => '#111',
    getUserPrimaryGroupIcon: () => 'shield',
    getUserPrimaryGroupLabel: () => 'Admin',
    handleAvatarSelected: () => 'avatar',
    isOnline: ref(true),
    isOwnProfile: ref(true),
    profilePanels: ref([{ key: 'discussions' }]),
    switchTab() {},
    user: ref({ id: 7 }),
    userBadges: ref([{ key: 'founder' }]),
  })

  assert.deepEqual(bindings.heroBindings.value.user, { id: 7 })
  assert.equal(bindings.heroBindings.value.isOnline, true)
  assert.deepEqual(bindings.sidebarBindings.value, {
    activeTab: 'discussions',
    items: [{ key: 'discussions' }],
  })
  assert.equal(bindings.activePanelComponent.value, 'PanelComponent')
  assert.deepEqual(bindings.activePanelProps.value, { posts: [] })
  assert.equal(typeof bindings.activePanelEvents.value.save, 'function')
})

test('profile view bindings expose stable events for hero and sidebar actions', () => {
  const calls = []
  const bindings = createProfileViewBindings({
    activeTab: ref('discussions'),
    activePanel: ref(null),
    avatarInput: ref(null),
    avatarUploading: ref(false),
    formatJoinDate: value => value,
    formatLastSeen: value => value,
    getUserAvatarColor: () => '#000',
    getUserPrimaryGroupColor: () => '#111',
    getUserPrimaryGroupIcon: () => 'shield',
    getUserPrimaryGroupLabel: () => 'Admin',
    handleAvatarSelected() {
      calls.push('avatar')
    },
    isOnline: ref(false),
    isOwnProfile: ref(false),
    profilePanels: ref([]),
    switchTab(tab) {
      calls.push(tab)
    },
    user: ref(null),
    userBadges: ref([]),
  })

  bindings.heroEvents.avatarSelected()
  bindings.heroEvents.openSettings()
  bindings.sidebarEvents.changeTab('posts')

  assert.deepEqual(calls, ['avatar', 'settings', 'posts'])
})
