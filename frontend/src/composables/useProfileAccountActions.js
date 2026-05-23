export function createProfileAccountActions({
  apiClient,
  authStore,
  avatarInput,
  editForm,
  forumUiStore,
  getProfileErrorMessage,
  getProfileUiCopy,
  modalStore,
  passwordForm,
  preferences,
  setAvatarUploading,
  setChangingPassword,
  setLoadingPreferences,
  setPasswordError,
  setPasswordSuccess,
  setPreferencesError,
  setPreferencesSuccess,
  setSaving,
  setSavingPreferences,
  setSettingsError,
  setSettingsSuccess,
  setVerificationError,
  setVerificationSending,
  setVerificationSuccess,
  user,
  userId,
  normalizeUser,
  resourceStore,
}) {
  async function saveProfile() {
    setSaving(true)
    setSettingsSuccess('')
    setSettingsError('')

    try {
      const previousEmail = user().email
      const updatedUser = await apiClient.patch(`/users/${user().id}`, editForm())

      const nextUser = resourceStore.upsert('users', {
        ...user(),
        ...normalizeUser(updatedUser)
      })
      userId(nextUser.id)

      editForm({
        display_name: nextUser.display_name || '',
        bio: nextUser.bio || '',
        email: nextUser.email || ''
      })

      await authStore.fetchUser()

      setSettingsSuccess(getProfileUiCopy(
        'profile-settings-save-success',
        {
          emailChanged: previousEmail !== nextUser.email,
          email: nextUser.email,
        },
        previousEmail !== nextUser.email
          ? `资料已保存，验证邮件已发送到 ${nextUser.email}`
          : '资料已保存'
      ))
    } catch (error) {
      setSettingsError(getProfileErrorMessage(
        error,
        getProfileUiCopy('profile-settings-save-error', {}, '保存失败')
      ))
    } finally {
      setSaving(false)
    }
  }

  async function loadPreferences() {
    setLoadingPreferences(true)
    setPreferencesError('')

    try {
      const data = await apiClient.get('/users/me/preferences')
      preferences({
        values: { ...(data.values || {}) },
        ui_values: {},
        definitions: Array.isArray(data.definitions) ? data.definitions : []
      })
      if (authStore.user) {
        authStore.user.preferences = { ...data }
      }
    } catch (error) {
      setPreferencesError(getProfileErrorMessage(
        error,
        getProfileUiCopy('profile-preferences-load-error', {}, '加载通知偏好失败')
      ))
    } finally {
      setLoadingPreferences(false)
    }
  }

  async function savePreferences() {
    setSavingPreferences(true)
    setPreferencesSuccess('')
    setPreferencesError('')

    try {
      const data = await apiClient.patch('/users/me/preferences', {
        values: { ...(preferences().values || {}) },
        ui_values: {},
      })

      preferences({
        values: { ...(data.values || {}) },
        ui_values: {},
        definitions: Array.isArray(data.definitions) ? data.definitions : []
      })
      if (authStore.user) {
        authStore.user.preferences = { ...data }
      }
      forumUiStore?.hydrateFromUiValues?.(data.ui_values || {})
      setPreferencesSuccess(getProfileUiCopy(
        'profile-preferences-save-success',
        {},
        '偏好已保存'
      ))
    } catch (error) {
      setPreferencesError(getProfileErrorMessage(
        error,
        getProfileUiCopy('profile-preferences-save-error', {}, '保存通知偏好失败')
      ))
    } finally {
      setSavingPreferences(false)
    }
  }

  async function resendVerificationEmail() {
    setVerificationSending(true)
    setVerificationSuccess('')
    setVerificationError('')

    try {
      const data = await apiClient.post('/users/me/resend-email-verification')
      setVerificationSuccess(
        data.message
        || getProfileUiCopy('profile-verification-success', {}, '验证邮件已发送')
      )
    } catch (error) {
      setVerificationError(getProfileErrorMessage(
        error,
        getProfileUiCopy('profile-verification-error', {}, '发送失败')
      ))
    } finally {
      setVerificationSending(false)
    }
  }

  async function changePassword() {
    setPasswordSuccess('')
    setPasswordError('')

    if (!passwordForm().old_password || !passwordForm().new_password) {
      setPasswordError(getProfileUiCopy('profile-password-empty-error', {}, '请完整填写密码信息'))
      return
    }

    if (passwordForm().new_password !== passwordForm().confirm_password) {
      setPasswordError(getProfileUiCopy('profile-password-mismatch-error', {}, '两次输入的新密码不一致'))
      return
    }

    setChangingPassword(true)
    try {
      const data = await apiClient.post(`/users/${user().id}/password`, {
        old_password: passwordForm().old_password,
        new_password: passwordForm().new_password
      })
      setPasswordSuccess(
        data.message || getProfileUiCopy('profile-password-success', {}, '密码修改成功')
      )
      passwordForm({
        old_password: '',
        new_password: '',
        confirm_password: ''
      })
    } catch (error) {
      setPasswordError(getProfileErrorMessage(
        error,
        getProfileUiCopy('profile-password-error', {}, '密码修改失败')
      ))
    } finally {
      setChangingPassword(false)
    }
  }

  async function handleAvatarSelected(event) {
    const file = event.target.files?.[0]
    if (!file || !user()) return

    setAvatarUploading(true)
    try {
      const formData = new FormData()
      formData.append('avatar', file)

      const updatedUser = await apiClient.post(`/users/${user().id}/avatar`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      const nextUser = resourceStore.upsert('users', normalizeUser(updatedUser))
      userId(nextUser.id)
      editForm({
        display_name: nextUser.display_name || '',
        bio: nextUser.bio || '',
        email: nextUser.email || ''
      })
      await authStore.fetchUser()
    } catch (error) {
      await modalStore.alert({
        title: getProfileUiCopy('profile-avatar-upload-error-title', {}, '头像上传失败'),
        message: getProfileErrorMessage(
          error,
          getProfileUiCopy('profile-avatar-upload-error-message', {}, '未知错误')
        ),
        tone: 'danger'
      })
    } finally {
      setAvatarUploading(false)
      if (avatarInput()) {
        avatarInput().value = ''
      }
    }
  }

  return {
    changePassword,
    handleAvatarSelected,
    loadPreferences,
    resendVerificationEmail,
    savePreferences,
    saveProfile,
  }
}

export function useProfileAccountActions({
  apiClient,
  authStore,
  avatarInput,
  editForm,
  forumUiStore,
  getProfileErrorMessage,
  getProfileUiCopy,
  modalStore,
  passwordForm,
  preferences,
  avatarUploading,
  changingPassword,
  loadingPreferences,
  passwordError,
  passwordSuccess,
  preferencesError,
  preferencesSuccess,
  resourceStore,
  saving,
  savingPreferences,
  settingsError,
  settingsSuccess,
  user,
  userId,
  verificationError,
  verificationSending,
  verificationSuccess,
  normalizeUser,
}) {
  return createProfileAccountActions({
    apiClient,
    authStore,
    avatarInput: () => avatarInput.value,
    editForm(value) {
      if (arguments.length > 0) {
        editForm.value = value
      }
      return editForm.value
    },
    forumUiStore,
    getProfileErrorMessage,
    getProfileUiCopy,
    modalStore,
    passwordForm(value) {
      if (arguments.length > 0) {
        passwordForm.value = value
      }
      return passwordForm.value
    },
    preferences(value) {
      if (arguments.length > 0) {
        preferences.value = value
      }
      return preferences.value
    },
    setAvatarUploading(value) {
      avatarUploading.value = value
    },
    setChangingPassword(value) {
      changingPassword.value = value
    },
    setLoadingPreferences(value) {
      loadingPreferences.value = value
    },
    setPasswordError(value) {
      passwordError.value = value
    },
    setPasswordSuccess(value) {
      passwordSuccess.value = value
    },
    setPreferencesError(value) {
      preferencesError.value = value
    },
    setPreferencesSuccess(value) {
      preferencesSuccess.value = value
    },
    resourceStore,
    setSaving(value) {
      saving.value = value
    },
    setSavingPreferences(value) {
      savingPreferences.value = value
    },
    setSettingsError(value) {
      settingsError.value = value
    },
    setSettingsSuccess(value) {
      settingsSuccess.value = value
    },
    setVerificationError(value) {
      verificationError.value = value
    },
    setVerificationSending(value) {
      verificationSending.value = value
    },
    setVerificationSuccess(value) {
      verificationSuccess.value = value
    },
    user: () => user.value,
    userId(value) {
      userId.value = value
    },
    normalizeUser,
  })
}
