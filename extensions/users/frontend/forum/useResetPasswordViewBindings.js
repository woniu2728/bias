import { computed } from '@bias/core'

export function createResetPasswordViewBindings({
  backToLoginText,
  confirmPasswordLabelText,
  confirmPasswordPlaceholderText,
  error,
  form,
  loading,
  newPasswordLabelText,
  newPasswordPlaceholderText,
  submit,
  submitButtonText,
  success,
  subtitleText,
  titleText,
  tokenLabelText,
  tokenPlaceholderText,
}) {
  const pageBindings = computed(() => ({
    form,
    loading: loading.value,
    error: error.value,
    success: success.value,
    title: titleText.value,
    subtitle: subtitleText.value,
    tokenLabelText: tokenLabelText.value,
    newPasswordLabelText: newPasswordLabelText.value,
    confirmPasswordLabelText: confirmPasswordLabelText.value,
    tokenPlaceholderText: tokenPlaceholderText.value,
    newPasswordPlaceholderText: newPasswordPlaceholderText.value,
    confirmPasswordPlaceholderText: confirmPasswordPlaceholderText.value,
    submitButtonText: submitButtonText.value,
    backToLoginText: backToLoginText.value,
  }))

  const pageEvents = {
    submit,
  }

  return {
    pageBindings,
    pageEvents,
  }
}

export function useResetPasswordViewBindings(options) {
  return createResetPasswordViewBindings(options)
}
