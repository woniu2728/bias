import { ref } from '@bias/core'

export function createProfileAccountState() {
  const saving = ref(false)
  const avatarUploading = ref(false)
  const avatarInput = ref(null)
  const settingsSuccess = ref('')
  const settingsError = ref('')
  const verificationSending = ref(false)
  const verificationSuccess = ref('')
  const verificationError = ref('')
  const changingPassword = ref(false)
  const passwordSuccess = ref('')
  const passwordError = ref('')
  const loadingPreferences = ref(false)
  const savingPreferences = ref(false)
  const preferencesSuccess = ref('')
  const preferencesError = ref('')

  const editForm = ref({
    display_name: '',
    bio: '',
    email: ''
  })

  const passwordForm = ref({
    old_password: '',
    new_password: '',
    confirm_password: ''
  })

  const preferences = ref({
    values: {},
    ui_values: {},
    definitions: []
  })

  return {
    avatarInput,
    avatarUploading,
    changingPassword,
    editForm,
    loadingPreferences,
    passwordError,
    passwordForm,
    passwordSuccess,
    preferences,
    preferencesError,
    preferencesSuccess,
    saving,
    savingPreferences,
    settingsError,
    settingsSuccess,
    verificationError,
    verificationSending,
    verificationSuccess,
  }
}

export function useProfileAccountState() {
  return createProfileAccountState()
}
