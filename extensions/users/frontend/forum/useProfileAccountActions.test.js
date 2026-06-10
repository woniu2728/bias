import test from 'node:test'
import assert from 'node:assert/strict'
import { createProfileAccountActions } from './useProfileAccountActions.js'

function createHarness(overrides = {}) {
  const calls = []
  const state = {
    user: overrides.user || {
      id: 7,
      email: 'old@example.com',
      display_name: 'Old',
      bio: '',
    },
    userId: 7,
    editForm: {
      display_name: 'New Name',
      bio: 'Bio',
      email: 'new@example.com',
    },
    passwordForm: {
      old_password: 'old-pass',
      new_password: 'new-pass',
      confirm_password: 'new-pass',
    },
    preferences: {
      values: { mentions: true },
      ui_values: {},
      definitions: [],
    },
    saving: false,
    settingsSuccess: '',
    settingsError: '',
    verificationSending: false,
    verificationSuccess: '',
    verificationError: '',
    changingPassword: false,
    passwordSuccess: '',
    passwordError: '',
    loadingPreferences: false,
    savingPreferences: false,
    preferencesSuccess: '',
    preferencesError: '',
    avatarUploading: false,
  }

  const authStore = {
    user: { id: 7, preferences: {} },
    async fetchUser() {
      calls.push('fetchUser')
    },
  }
  const apiClient = {
    async patch(url, payload) {
      calls.push(['patch', url, payload])
      if (url === `/users/${state.user.id}`) {
        return {
          id: state.user.id,
          ...payload,
        }
      }
      if (url === '/users/me/preferences') {
        return {
          values: { ...(payload.values || {}) },
          ui_values: {},
          definitions: [],
        }
      }
      return {}
    },
    async get(url) {
      calls.push(['get', url])
      return {
        values: { mentions: true },
        ui_values: {},
        definitions: [],
      }
    },
    async post(url, payload) {
      calls.push(['post', url, payload])
      if (url.endsWith('/password')) {
        return { message: '密码修改成功' }
      }
      if (url === '/users/me/resend-email-verification') {
        return { message: '验证邮件已发送' }
      }
      return {}
    },
  }
  const modalStore = {
    async alert(payload) {
      calls.push(['alert', payload])
    },
  }
  const resourceStore = {
    upsert(_type, value) {
      calls.push(['upsert', value])
      state.user = { ...state.user, ...value }
      return state.user
    },
  }

  const actions = createProfileAccountActions({
    apiClient,
    authStore,
    avatarInput: () => null,
    editForm(value) {
      if (arguments.length > 0) state.editForm = value
      return state.editForm
    },
    forumUiStore: {
      hydrateFromUiValues(value) {
        calls.push(['hydrateFromUiValues', value])
      },
    },
    getProfileErrorMessage(error) {
      return error.message
    },
    getProfileUiCopy(_surface, _context, fallback = '') {
      return fallback
    },
    modalStore,
    passwordForm(value) {
      if (arguments.length > 0) state.passwordForm = value
      return state.passwordForm
    },
    preferences(value) {
      if (arguments.length > 0) state.preferences = value
      return state.preferences
    },
    setAvatarUploading(value) {
      state.avatarUploading = value
    },
    setChangingPassword(value) {
      state.changingPassword = value
    },
    setLoadingPreferences(value) {
      state.loadingPreferences = value
    },
    setPasswordError(value) {
      state.passwordError = value
    },
    setPasswordSuccess(value) {
      state.passwordSuccess = value
    },
    setPreferencesError(value) {
      state.preferencesError = value
    },
    setPreferencesSuccess(value) {
      state.preferencesSuccess = value
    },
    resourceStore,
    setSaving(value) {
      state.saving = value
    },
    setSavingPreferences(value) {
      state.savingPreferences = value
    },
    setSettingsError(value) {
      state.settingsError = value
    },
    setSettingsSuccess(value) {
      state.settingsSuccess = value
    },
    setVerificationError(value) {
      state.verificationError = value
    },
    setVerificationSending(value) {
      state.verificationSending = value
    },
    setVerificationSuccess(value) {
      state.verificationSuccess = value
    },
    user: () => state.user,
    userId(value) {
      state.userId = value
    },
    normalizeUser(value) {
      return value
    },
  })

  return {
    actions,
    authStore,
    calls,
    state,
  }
}

test('profile account actions validates password confirmation before submitting', async () => {
  const harness = createHarness()
  harness.state.passwordForm.confirm_password = 'mismatch'

  await harness.actions.changePassword()

  assert.equal(harness.state.passwordError, '两次输入的新密码不一致')
})

test('profile account actions saves profile and refreshes auth user', async () => {
  const harness = createHarness()

  await harness.actions.saveProfile()

  assert.equal(harness.state.settingsSuccess, '资料已保存，验证邮件已发送到 new@example.com')
  assert.equal(harness.calls.some(item => item === 'fetchUser'), true)
  assert.equal(harness.state.userId, 7)
})

test('profile account actions loads and saves ui preferences', async () => {
  const harness = createHarness()

  await harness.actions.loadPreferences()
  assert.deepEqual(harness.state.preferences.ui_values, {})

  harness.state.preferences.ui_values = {}
  await harness.actions.savePreferences()

  const patchCall = harness.calls.find(item => Array.isArray(item) && item[0] === 'patch' && item[1] === '/users/me/preferences')
  assert.deepEqual(patchCall[2].ui_values, {})
  assert.equal(harness.calls.some(item => Array.isArray(item) && item[0] === 'hydrateFromUiValues'), true)
})
