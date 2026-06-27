import { onBeforeUnmount, ref } from 'vue'

export function useAdminSaveFeedback(hideDelay = 3000) {
  const saveSuccess = ref(false)
  const saveError = ref(false)
  const saveErrorMessage = ref('')
  let successTimer = null

  function clearSuccessTimer() {
    if (successTimer) {
      clearTimeout(successTimer)
      successTimer = null
    }
  }

  function resetSaveFeedback() {
    clearSuccessTimer()
    saveSuccess.value = false
    saveError.value = false
    saveErrorMessage.value = ''
  }

  function showSaveSuccess() {
    clearSuccessTimer()
    saveSuccess.value = true
    saveError.value = false
    saveErrorMessage.value = ''
    successTimer = setTimeout(() => {
      saveSuccess.value = false
      successTimer = null
    }, hideDelay)
  }

  function showSaveError(message = '') {
    clearSuccessTimer()
    saveSuccess.value = false
    saveError.value = true
    saveErrorMessage.value = String(message || '').trim()
  }

  onBeforeUnmount(() => {
    clearSuccessTimer()
  })

  return {
    saveSuccess,
    saveError,
    saveErrorMessage,
    resetSaveFeedback,
    showSaveSuccess,
    showSaveError
  }
}
