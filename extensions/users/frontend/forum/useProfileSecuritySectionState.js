import { computed } from '@bias/core'
import { getUiCopy } from '@bias/forum'

export function createProfileSecuritySectionState({
  changingPassword,
  getText = getUiCopy,
  user,
  verificationSending,
}) {
  const securitySectionTitleText = computed(() => getText({
    surface: 'profile-security-section-title',
  })?.text || '账号安全')

  const securitySectionDescriptionText = computed(() => getText({
    surface: 'profile-security-section-description',
  })?.text || '查看邮箱验证状态，并修改登录密码。')

  const emailSectionTitleText = computed(() => getText({
    surface: 'profile-security-email-section-title',
  })?.text || '邮箱验证')

  const emailSectionDescriptionText = computed(() => getText({
    surface: 'profile-security-email-section-description',
  })?.text || '验证邮箱后，可确保找回密码和安全通知正常送达。')

  const emailStatusText = computed(() => getText({
    surface: 'profile-security-status-label',
    isEmailConfirmed: user.value?.is_email_confirmed,
  })?.text || (user.value?.is_email_confirmed ? '已验证' : '未验证'))

  const emailHelpText = computed(() => getText({
    surface: 'profile-security-email-help',
    isEmailConfirmed: user.value?.is_email_confirmed,
  })?.text || (user.value?.is_email_confirmed ? '当前邮箱已通过验证。' : '当前邮箱尚未验证，你可以重新发送验证邮件。'))

  const passwordSectionTitleText = computed(() => getText({
    surface: 'profile-security-password-section-title',
  })?.text || '修改密码')

  const passwordSectionDescriptionText = computed(() => getText({
    surface: 'profile-security-password-section-description',
  })?.text || '修改后，下次登录请使用新密码。')

  const oldPasswordLabelText = computed(() => getText({
    surface: 'profile-security-old-password-label',
  })?.text || '当前密码')

  const newPasswordLabelText = computed(() => getText({
    surface: 'profile-security-new-password-label',
  })?.text || '新密码')

  const confirmPasswordLabelText = computed(() => getText({
    surface: 'profile-security-confirm-password-label',
  })?.text || '确认新密码')

  const resendVerificationButtonText = computed(() => getText({
    surface: 'profile-security-resend-button',
    sending: verificationSending.value,
  })?.text || (verificationSending.value ? '发送中...' : '重新发送验证邮件'))

  const oldPasswordPlaceholderText = computed(() => getText({
    surface: 'profile-security-old-password-placeholder',
  })?.text || '请输入当前密码')

  const newPasswordPlaceholderText = computed(() => getText({
    surface: 'profile-security-new-password-placeholder',
  })?.text || '请输入新密码')

  const confirmPasswordPlaceholderText = computed(() => getText({
    surface: 'profile-security-confirm-password-placeholder',
  })?.text || '请再次输入新密码')

  const changePasswordButtonText = computed(() => getText({
    surface: 'profile-security-submit-button',
    submitting: changingPassword.value,
  })?.text || (changingPassword.value ? '提交中...' : '更新密码'))

  return {
    changePasswordButtonText,
    confirmPasswordLabelText,
    confirmPasswordPlaceholderText,
    emailHelpText,
    emailSectionDescriptionText,
    emailSectionTitleText,
    emailStatusText,
    newPasswordLabelText,
    newPasswordPlaceholderText,
    oldPasswordLabelText,
    oldPasswordPlaceholderText,
    passwordSectionDescriptionText,
    passwordSectionTitleText,
    resendVerificationButtonText,
    securitySectionDescriptionText,
    securitySectionTitleText,
  }
}

export function useProfileSecuritySectionState(options) {
  return createProfileSecuritySectionState(options)
}
