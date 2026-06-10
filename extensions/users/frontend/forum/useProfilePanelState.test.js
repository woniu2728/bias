import { nextTick, ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createProfilePanelState } from './useProfilePanelState.js'

function createPageState(overrides = {}) {
  return {
    user: ref({ id: 7, discussion_count: 3, comment_count: 5 }),
    discussions: ref([]),
    posts: ref([]),
    loadingDiscussions: ref(false),
    loadingPosts: ref(false),
    isOwnProfile: ref(true),
    activeTab: ref('discussions'),
    editForm: ref({ display_name: 'Alice', bio: '', email: 'a@example.com' }),
    preferences: ref({
      values: { email: true },
      ui_values: {},
      definitions: []
    }),
    saving: ref(false),
    settingsSuccess: ref(''),
    settingsError: ref(''),
    loadingPreferences: ref(false),
    savingPreferences: ref(false),
    preferencesSuccess: ref(''),
    preferencesError: ref(''),
    saveProfile() {},
    savePreferences() {},
    passwordForm: ref({ old_password: '', new_password: '', confirm_password: '' }),
    verificationSending: ref(false),
    verificationSuccess: ref(''),
    verificationError: ref(''),
    resendVerificationEmail() {},
    changingPassword: ref(false),
    passwordSuccess: ref(''),
    passwordError: ref(''),
    changePassword() {},
    switchTab() {},
    ...overrides,
  }
}

test('profile panel state exposes active panel from registered panels', () => {
  const state = createProfilePanelState({
    authStore: { user: { id: 7 } },
    formatDate: value => value,
    getPanels: () => [
      { key: 'discussions', label: '讨论' },
      { key: 'settings', label: '设置' },
    ],
    pageState: createPageState(),
  })

  assert.equal(state.profilePanels.value.length, 2)
  assert.equal(state.activePanel.value?.key, 'discussions')
})

test('profile panel state falls back to first visible panel when current tab is unavailable', async () => {
  const switchCalls = []
  const pageState = createPageState({
    activeTab: ref('security'),
    switchTab(tab) {
      switchCalls.push(tab)
    },
  })

  createProfilePanelState({
    authStore: { user: { id: 7 } },
    formatDate: value => value,
    getPanels: () => [
      { key: 'discussions', label: '讨论' },
      { key: 'posts', label: '回复' },
    ],
    pageState,
  })

  await nextTick()

  assert.deepEqual(switchCalls, ['discussions'])
})

test('profile panel state updates profile forms and preferences in place', () => {
  const pageState = createPageState()
  const state = createProfilePanelState({
    authStore: { user: { id: 7 } },
    formatDate: value => value,
    getPanels: () => [{ key: 'discussions', label: '讨论' }],
    pageState,
  })

  state.handleEditFormUpdate({ key: 'display_name', value: 'Bob' })
  state.handlePasswordFormUpdate({ key: 'new_password', value: 'secret' })
  state.handlePreferenceUpdate({ key: 'push', value: 1 })

  assert.equal(pageState.editForm.value.display_name, 'Bob')
  assert.equal(pageState.passwordForm.value.new_password, 'secret')
  assert.equal(pageState.preferences.value.values.push, true)
})
