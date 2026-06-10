import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createProfileSettingsSectionState } from './useProfileSettingsSectionState.js'

test('profile settings section state groups preferences by category and resolves copy', () => {
  const state = createProfileSettingsSectionState({
    getState: () => ({ text: 'loading-copy' }),
    getText: ({ surface, category }) => {
      if (surface === 'profile-preferences-group-label') {
        return { text: `${category}-label` }
      }
      if (surface === 'profile-preferences-group-description') {
        return { text: `${category}-description` }
      }
      return { text: `${surface}-copy` }
    },
    loadingPreferences: ref(true),
    preferences: ref({
      definitions: [
        { key: 'follow_on_reply', category: 'behavior', label: 'reply' },
        { key: 'notify_mentions', category: 'notification', label: 'mention' },
      ],
    }),
    saving: ref(true),
    savingPreferences: ref(false),
    user: ref({ is_email_confirmed: true }),
  })

  assert.deepEqual(state.groupedPreferences.value, [
    {
      key: 'behavior',
      label: 'behavior-label',
      description: 'behavior-description',
      items: [{ key: 'follow_on_reply', category: 'behavior', label: 'reply' }],
    },
    {
      key: 'notification',
      label: 'notification-label',
      description: 'notification-description',
      items: [{ key: 'notify_mentions', category: 'notification', label: 'mention' }],
    },
  ])
  assert.equal(state.sectionTitleText.value, 'profile-settings-section-title-copy')
  assert.equal(state.preferencesLoadingStateText.value, 'loading-copy')
  assert.equal(state.saveProfileButtonText.value, 'profile-settings-save-button-copy')
})

test('profile settings section state falls back to built-in text defaults', () => {
  const state = createProfileSettingsSectionState({
    getState: () => null,
    getText: () => null,
    loadingPreferences: ref(false),
    preferences: ref({ definitions: [{ key: 'x', category: 'behavior' }] }),
    saving: ref(false),
    savingPreferences: ref(true),
    user: ref({ is_email_confirmed: false }),
  })

  assert.equal(state.groupedPreferences.value[0].label, '自动关注')
  assert.equal(state.preferencesLoadingStateText.value, '加载偏好中...')
  assert.equal(state.emailHelpText.value, '修改邮箱后会重新进入未验证状态。')
  assert.equal(state.savePreferencesButtonText.value, '保存中...')
})
