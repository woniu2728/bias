import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createProfileSecuritySectionState } from './useProfileSecuritySectionState.js'

test('profile security section state resolves registry copy', () => {
  const state = createProfileSecuritySectionState({
    changingPassword: ref(true),
    getText: ({ surface }) => ({ text: `${surface}-copy` }),
    user: ref({ is_email_confirmed: true }),
    verificationSending: ref(true),
  })

  assert.equal(state.securitySectionTitleText.value, 'profile-security-section-title-copy')
  assert.equal(state.emailStatusText.value, 'profile-security-status-label-copy')
  assert.equal(state.resendVerificationButtonText.value, 'profile-security-resend-button-copy')
  assert.equal(state.changePasswordButtonText.value, 'profile-security-submit-button-copy')
})

test('profile security section state falls back to built-in defaults', () => {
  const state = createProfileSecuritySectionState({
    changingPassword: ref(false),
    getText: () => null,
    user: ref({ is_email_confirmed: false }),
    verificationSending: ref(false),
  })

  assert.equal(state.securitySectionDescriptionText.value, '查看邮箱验证状态，并修改登录密码。')
  assert.equal(state.emailStatusText.value, '未验证')
  assert.equal(state.emailHelpText.value, '当前邮箱尚未验证，你可以重新发送验证邮件。')
  assert.equal(state.changePasswordButtonText.value, '更新密码')
})
