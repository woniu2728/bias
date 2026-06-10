import { computed } from '@bias/core'

export function createVerifyEmailViewBindings({
  error,
  idleText,
  loading,
  loadingText,
  loginActionText,
  profileActionText,
  success,
  subtitleText,
  titleText,
}) {
  const pageBindings = computed(() => {
    let statusText = idleText.value
    let statusClass = ''

    if (loading.value) {
      statusText = loadingText.value
    } else if (success.value) {
      statusText = success.value
      statusClass = 'status-success'
    } else if (error.value) {
      statusText = error.value
      statusClass = 'status-error'
    }

    return {
      title: titleText.value,
      subtitle: subtitleText.value,
      statusClass,
      statusText,
      loginActionText: loginActionText.value,
      profileActionText: profileActionText.value,
    }
  })

  return {
    pageBindings,
  }
}

export function useVerifyEmailViewBindings(options) {
  return createVerifyEmailViewBindings(options)
}
