import { computed, onMounted, ref, watch } from 'vue'
import api from '@/api'
import {
  normalizeDiscussion,
  normalizePost,
  unwrapList
} from '@/utils/forum'

export function useProfilePage({
  authStore,
  modalStore,
  route
}) {
  const user = ref(null)
  const discussions = ref([])
  const posts = ref([])
  const loading = ref(true)
  const loadingDiscussions = ref(false)
  const loadingPosts = ref(false)
  const activeTab = ref('discussions')
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
    definitions: []
  })

  const isOwnProfile = computed(() => authStore.user && user.value && authStore.user.id === user.value.id)

  onMounted(async () => {
    await refreshProfile()
  })

  watch(() => route.params.id, async () => {
    posts.value = []
    discussions.value = []
    await refreshProfile()
  })

  watch(isOwnProfile, (value) => {
    if (!value && (activeTab.value === 'settings' || activeTab.value === 'security')) {
      activeTab.value = 'discussions'
    }
  })

  async function refreshProfile() {
    await loadUser()
    if (isOwnProfile.value) {
      await loadPreferences()
    }
    await loadDiscussions()
  }

  async function loadUser() {
    loading.value = true

    try {
      let data
      if (route.params.id) {
        const identifier = String(route.params.id)
        data = /^\d+$/.test(identifier)
          ? await api.get(`/users/${identifier}`)
          : await api.get(`/users/by-username/${encodeURIComponent(identifier)}`)
      } else {
        data = await api.get('/users/me')
      }

      user.value = data

      editForm.value = {
        display_name: data.display_name || '',
        bio: data.bio || '',
        email: data.email || ''
      }

      if (!authStore.user || authStore.user.id !== data.id) {
        verificationSuccess.value = ''
        verificationError.value = ''
      }
    } catch (error) {
      console.error('加载用户失败:', error)
    } finally {
      loading.value = false
    }
  }

  async function loadDiscussions() {
    if (!user.value) return

    loadingDiscussions.value = true
    try {
      const data = await api.get('/discussions/', {
        params: {
          author: user.value.username,
          sort: 'newest',
          limit: 20
        }
      })
      discussions.value = unwrapList(data).map(normalizeDiscussion)
    } catch (error) {
      console.error('加载讨论失败:', error)
    } finally {
      loadingDiscussions.value = false
    }
  }

  async function loadPosts() {
    if (!user.value || posts.value.length > 0) return

    loadingPosts.value = true
    try {
      const data = await api.get('/posts', {
        params: {
          author: user.value.username,
          limit: 20
        }
      })
      posts.value = unwrapList(data).map(normalizePost)
    } catch (error) {
      console.error('加载回复失败:', error)
    } finally {
      loadingPosts.value = false
    }
  }

  function switchTab(tab) {
    if (!isOwnProfile.value && (tab === 'settings' || tab === 'security')) {
      activeTab.value = 'discussions'
      return
    }

    activeTab.value = tab
    if (tab === 'posts' && posts.value.length === 0) {
      loadPosts()
    }
  }

  async function saveProfile() {
    saving.value = true
    settingsSuccess.value = ''
    settingsError.value = ''

    try {
      const previousEmail = user.value.email
      const updatedUser = await api.patch(`/users/${user.value.id}`, editForm.value)

      user.value = {
        ...user.value,
        ...updatedUser
      }

      editForm.value = {
        display_name: updatedUser.display_name || '',
        bio: updatedUser.bio || '',
        email: updatedUser.email || ''
      }

      await authStore.fetchUser()

      settingsSuccess.value = previousEmail !== updatedUser.email
        ? `资料已保存，验证邮件已发送到 ${updatedUser.email}`
        : '资料已保存'
    } catch (error) {
      settingsError.value = error.response?.data?.error || error.message || '保存失败'
    } finally {
      saving.value = false
    }
  }

  async function loadPreferences() {
    loadingPreferences.value = true
    preferencesError.value = ''

    try {
      const data = await api.get('/users/me/preferences')
      preferences.value = {
        values: { ...(data.values || {}) },
        definitions: Array.isArray(data.definitions) ? data.definitions : []
      }
      if (authStore.user) {
        authStore.user.preferences = { ...data }
      }
    } catch (error) {
      preferencesError.value = error.response?.data?.error || error.message || '加载通知偏好失败'
    } finally {
      loadingPreferences.value = false
    }
  }

  async function savePreferences() {
    savingPreferences.value = true
    preferencesSuccess.value = ''
    preferencesError.value = ''

    try {
      const data = await api.patch('/users/me/preferences', {
        values: { ...(preferences.value.values || {}) }
      })

      preferences.value = {
        values: { ...(data.values || {}) },
        definitions: Array.isArray(data.definitions) ? data.definitions : []
      }
      if (authStore.user) {
        authStore.user.preferences = { ...data }
      }
      preferencesSuccess.value = '通知偏好已保存'
    } catch (error) {
      preferencesError.value = error.response?.data?.error || error.message || '保存通知偏好失败'
    } finally {
      savingPreferences.value = false
    }
  }

  async function resendVerificationEmail() {
    verificationSending.value = true
    verificationSuccess.value = ''
    verificationError.value = ''

    try {
      const data = await api.post('/users/me/resend-email-verification')
      verificationSuccess.value = data.message || '验证邮件已发送'
    } catch (error) {
      verificationError.value = error.response?.data?.error || error.message || '发送失败'
    } finally {
      verificationSending.value = false
    }
  }

  async function changePassword() {
    passwordSuccess.value = ''
    passwordError.value = ''

    if (!passwordForm.value.old_password || !passwordForm.value.new_password) {
      passwordError.value = '请完整填写密码信息'
      return
    }

    if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
      passwordError.value = '两次输入的新密码不一致'
      return
    }

    changingPassword.value = true
    try {
      const data = await api.post(`/users/${user.value.id}/password`, {
        old_password: passwordForm.value.old_password,
        new_password: passwordForm.value.new_password
      })
      passwordSuccess.value = data.message || '密码修改成功'
      passwordForm.value = {
        old_password: '',
        new_password: '',
        confirm_password: ''
      }
    } catch (error) {
      passwordError.value = error.response?.data?.error || error.message || '密码修改失败'
    } finally {
      changingPassword.value = false
    }
  }

  async function handleAvatarSelected(event) {
    const file = event.target.files?.[0]
    if (!file || !user.value) return

    avatarUploading.value = true
    try {
      const formData = new FormData()
      formData.append('avatar', file)

      const updatedUser = await api.post(`/users/${user.value.id}/avatar`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      user.value = updatedUser
      editForm.value = {
        display_name: updatedUser.display_name || '',
        bio: updatedUser.bio || '',
        email: updatedUser.email || ''
      }
      await authStore.fetchUser()
    } catch (error) {
      await modalStore.alert({
        title: '头像上传失败',
        message: error.response?.data?.error || error.message || '未知错误',
        tone: 'danger'
      })
    } finally {
      avatarUploading.value = false
      if (avatarInput.value) {
        avatarInput.value.value = ''
      }
    }
  }

  return {
    user,
    discussions,
    posts,
    loading,
    loadingDiscussions,
    loadingPosts,
    activeTab,
    saving,
    avatarUploading,
    avatarInput,
    settingsSuccess,
    settingsError,
    verificationSending,
    verificationSuccess,
    verificationError,
    changingPassword,
    passwordSuccess,
    passwordError,
    loadingPreferences,
    savingPreferences,
    preferencesSuccess,
    preferencesError,
    editForm,
    passwordForm,
    preferences,
    isOwnProfile,
    switchTab,
    saveProfile,
    savePreferences,
    resendVerificationEmail,
    changePassword,
    handleAvatarSelected
  }
}
