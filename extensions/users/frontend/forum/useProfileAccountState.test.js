import test from 'node:test'
import assert from 'node:assert/strict'
import { createProfileAccountState } from './useProfileAccountState.js'

test('profile account state exposes default runtime flags and forms', () => {
  const state = createProfileAccountState()

  assert.equal(state.saving.value, false)
  assert.equal(state.avatarUploading.value, false)
  assert.equal(state.verificationSending.value, false)
  assert.equal(state.loadingPreferences.value, false)
  assert.equal(state.settingsSuccess.value, '')
  assert.equal(state.passwordError.value, '')
  assert.deepEqual(state.editForm.value, {
    display_name: '',
    bio: '',
    email: '',
  })
  assert.deepEqual(state.passwordForm.value, {
    old_password: '',
    new_password: '',
    confirm_password: '',
  })
  assert.deepEqual(state.preferences.value, {
    values: {},
    ui_values: {},
    definitions: [],
  })
})
