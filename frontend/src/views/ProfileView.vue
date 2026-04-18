<template>
  <div class="profile-page">
    <div v-if="loading" class="loading-page">加载中...</div>
    <div v-else-if="!user" class="error-page">用户不存在</div>
    <div v-else>
      <div class="user-hero" :style="{ backgroundColor: user.color || '#4d698e' }">
        <div class="hero-background">
          <div class="container">
            <div class="user-card">
              <div class="user-avatar">
                <label
                  v-if="isOwnProfile"
                  class="avatar-uploader"
                  :class="{ disabled: avatarUploading }"
                >
                  <input
                    ref="avatarInput"
                    type="file"
                    accept="image/png,image/jpeg,image/gif,image/webp"
                    class="avatar-input"
                    @change="handleAvatarSelected"
                  />
                  <span class="avatar-upload-badge">
                    {{ avatarUploading ? '上传中...' : '更换头像' }}
                  </span>
                </label>
                <img
                  v-if="user.avatar_url"
                  :src="user.avatar_url"
                  :alt="user.username"
                  class="avatar-large avatar-image"
                />
                <div v-else class="avatar-large" :style="{ backgroundColor: getUserAvatarColor(user) }">
                  {{ user.username.charAt(0).toUpperCase() }}
                </div>
                <span
                  v-if="getUserPrimaryGroupIcon(user)"
                  class="avatar-group-badge"
                  :style="{ backgroundColor: getUserPrimaryGroupColor(user) }"
                  :title="getUserPrimaryGroupLabel(user)"
                >
                  <i :class="getUserPrimaryGroupIcon(user)"></i>
                </span>
              </div>
              <div class="user-info-wrapper">
                <h1 class="user-identity">{{ user.display_name || user.username }}</h1>
                <ul class="user-badges" v-if="user.is_staff">
                  <li class="badge badge-admin">管理员</li>
                </ul>
                <ul class="user-info">
                  <li class="user-last-seen">
                    <i class="fas fa-circle" :class="{ online: isOnline }"></i>
                    {{ isOnline ? '在线' : formatLastSeen(user.last_seen_at) }}
                  </li>
                  <li>
                    <i class="fas fa-clock"></i>
                    加入于 {{ formatJoinDate(user.joined_at) }}
                  </li>
                </ul>
              </div>
              <div class="user-card-controls">
                <button v-if="isOwnProfile" @click="switchTab('settings')" class="btn-control">
                  <i class="fas fa-sliders-h"></i>
                  设置
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="container">
        <div class="user-page-layout">
          <aside class="user-sidebar">
            <nav class="side-nav">
              <ul>
                <li>
                  <a
                    @click.prevent="switchTab('discussions')"
                    :class="{ active: activeTab === 'discussions' }"
                    class="nav-link"
                  >
                    <i class="fas fa-bars"></i>
                    <span>讨论</span>
                    <span class="badge-count">{{ user.discussion_count || 0 }}</span>
                  </a>
                </li>
                <li>
                  <a
                    @click.prevent="switchTab('posts')"
                    :class="{ active: activeTab === 'posts' }"
                    class="nav-link"
                  >
                    <i class="far fa-comment"></i>
                    <span>回复</span>
                    <span class="badge-count">{{ user.comment_count || 0 }}</span>
                  </a>
                </li>
                <li v-if="isOwnProfile">
                  <a
                    @click.prevent="switchTab('settings')"
                    :class="{ active: activeTab === 'settings' }"
                    class="nav-link"
                  >
                    <i class="fas fa-user-cog"></i>
                    <span>设置</span>
                  </a>
                </li>
                <li v-if="isOwnProfile">
                  <a
                    @click.prevent="switchTab('security')"
                    :class="{ active: activeTab === 'security' }"
                    class="nav-link"
                  >
                    <i class="fas fa-shield-alt"></i>
                    <span>安全</span>
                  </a>
                </li>
              </ul>
            </nav>
          </aside>

          <main class="user-content">
            <div v-if="activeTab === 'discussions'" class="content-section">
              <div v-if="loadingDiscussions" class="loading-small">加载中...</div>
              <div v-else-if="discussions.length === 0" class="empty-state">
                <p>{{ isOwnProfile ? '你还没有发起过讨论' : '该用户还没有发起过讨论' }}</p>
              </div>
              <div v-else class="discussion-list">
                <div
                  v-for="discussion in discussions"
                  :key="discussion.id"
                  class="discussion-item"
                >
                  <div class="discussion-main">
                    <div class="discussion-title-row">
                      <router-link :to="buildDiscussionPath(discussion)" class="discussion-title">
                        {{ discussion.title }}
                      </router-link>
                      <span v-if="discussion.approval_status === 'pending'" class="approval-pill">待审核</span>
                      <span v-else-if="discussion.approval_status === 'rejected'" class="approval-pill approval-pill--rejected">已拒绝</span>
                    </div>
                    <p v-if="discussion.approval_status === 'rejected' && discussion.approval_note" class="approval-note">
                      审核反馈：{{ discussion.approval_note }}
                    </p>
                    <div class="discussion-meta">
                      <span>{{ formatDate(discussion.created_at) }}</span>
                    </div>
                  </div>
                  <div class="discussion-stats">
                    <div class="stat">
                      <i class="fas fa-comment"></i>
                      {{ discussion.comment_count }}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="activeTab === 'posts'" class="content-section">
              <div v-if="loadingPosts" class="loading-small">加载中...</div>
              <div v-else-if="posts.length === 0" class="empty-state">
                <p>{{ isOwnProfile ? '你还没有发表过回复' : '该用户还没有发表过回复' }}</p>
              </div>
              <div v-else class="post-list">
                <div v-for="post in posts" :key="post.id" class="post-item">
                  <div class="post-header">
                    <div class="post-header-main">
                      <router-link
                        :to="buildDiscussionPath(post.discussion?.id || post.discussion_id)"
                        class="post-discussion-link"
                      >
                        <i class="fas fa-arrow-right"></i>
                        {{ post.discussion?.title || '讨论' }}
                      </router-link>
                      <span v-if="post.approval_status === 'pending'" class="approval-pill">待审核</span>
                      <span v-else-if="post.approval_status === 'rejected'" class="approval-pill approval-pill--rejected">已拒绝</span>
                    </div>
                    <span class="post-time">{{ formatDate(post.created_at) }}</span>
                  </div>
                  <p v-if="post.approval_status === 'rejected' && post.approval_note" class="approval-note">
                    审核反馈：{{ post.approval_note }}
                  </p>
                  <div class="post-content" v-html="post.content_html || post.content"></div>
                </div>
              </div>
            </div>

            <div v-if="activeTab === 'settings' && isOwnProfile" class="content-section settings-section">
              <div class="section-header">
                <div>
                  <h2>个人设置</h2>
                  <p>维护你的显示名称、邮箱、个人简介和通知偏好。</p>
                </div>
              </div>

              <div v-if="settingsSuccess" class="success-banner">{{ settingsSuccess }}</div>
              <div v-if="settingsError" class="error-banner">{{ settingsError }}</div>

              <div class="settings-card">
                <div class="form-group">
                  <label>显示名称</label>
                  <input
                    v-model="editForm.display_name"
                    type="text"
                    class="form-control"
                    placeholder="显示名称"
                  />
                </div>

                <div class="form-group">
                  <label>邮箱</label>
                  <input
                    v-model="editForm.email"
                    type="email"
                    class="form-control"
                    placeholder="name@example.com"
                  />
                  <small class="form-help">
                    {{ user.is_email_confirmed ? '当前邮箱已完成验证。' : '修改邮箱后会重新进入未验证状态。' }}
                  </small>
                </div>

                <div class="form-group">
                  <label>个人简介</label>
                  <textarea
                    v-model="editForm.bio"
                    class="form-control"
                    rows="5"
                    placeholder="介绍一下自己..."
                  ></textarea>
                </div>

                <div class="form-actions">
                  <button @click="saveProfile" class="btn-primary" :disabled="saving">
                    {{ saving ? '保存中...' : '保存资料' }}
                  </button>
                </div>
              </div>

              <div class="settings-card settings-card--stacked">
                <div class="settings-card-header">
                  <div>
                    <h3>通知偏好</h3>
                    <p>按照 Flarum 的习惯，把自动关注和新回复通知放在个人设置中管理。</p>
                  </div>
                  <button @click="savePreferences" class="btn-secondary" :disabled="loadingPreferences || savingPreferences">
                    {{ savingPreferences ? '保存中...' : '保存偏好' }}
                  </button>
                </div>

                <div v-if="preferencesSuccess" class="success-banner">{{ preferencesSuccess }}</div>
                <div v-if="preferencesError" class="error-banner">{{ preferencesError }}</div>
                <div v-if="loadingPreferences" class="loading-small loading-small--inline">加载偏好中...</div>
                <div v-else class="preferences-list">
                  <label class="preference-item">
                    <span class="preference-copy">
                      <strong>回复后自动关注</strong>
                      <small>参与讨论后，自动把该讨论加入关注列表。</small>
                    </span>
                    <input v-model="preferences.follow_after_reply" type="checkbox">
                  </label>

                  <label class="preference-item">
                    <span class="preference-copy">
                      <strong>发起讨论后自动关注</strong>
                      <small>你创建的新讨论会默认出现在关注中。</small>
                    </span>
                    <input v-model="preferences.follow_after_create" type="checkbox">
                  </label>

                  <label class="preference-item">
                    <span class="preference-copy">
                      <strong>关注讨论有新回复时通知我</strong>
                      <small>关闭后，仍会保留关注状态，但不再接收新回复通知。</small>
                    </span>
                    <input v-model="preferences.notify_new_post" type="checkbox">
                  </label>
                </div>
              </div>
            </div>

            <div v-if="activeTab === 'security' && isOwnProfile" class="content-section security-section">
              <div class="section-header">
                <div>
                  <h2>账号安全</h2>
                  <p>查看邮箱验证状态，并修改登录密码。</p>
                </div>
              </div>

              <div class="security-grid">
                <section class="settings-card">
                  <div class="security-card-header">
                    <div>
                      <h3>邮箱验证</h3>
                      <p>验证邮箱后，可确保找回密码和安全通知正常送达。</p>
                    </div>
                    <span
                      class="email-status"
                      :class="{ confirmed: user.is_email_confirmed, pending: !user.is_email_confirmed }"
                    >
                      {{ user.is_email_confirmed ? '已验证' : '未验证' }}
                    </span>
                  </div>

                  <div class="email-summary">
                    <strong>{{ user.email }}</strong>
                    <p v-if="user.is_email_confirmed">当前邮箱已通过验证。</p>
                    <p v-else>当前邮箱尚未验证，你可以重新发送验证邮件。</p>
                  </div>

                  <div v-if="verificationSuccess" class="success-banner">{{ verificationSuccess }}</div>
                  <div v-if="verificationError" class="error-banner">{{ verificationError }}</div>

                  <button
                    v-if="!user.is_email_confirmed"
                    @click="resendVerificationEmail"
                    class="btn-secondary"
                    :disabled="verificationSending"
                  >
                    {{ verificationSending ? '发送中...' : '重新发送验证邮件' }}
                  </button>
                </section>

                <section class="settings-card">
                  <div class="security-card-header">
                    <div>
                      <h3>修改密码</h3>
                      <p>修改后，下次登录请使用新密码。</p>
                    </div>
                  </div>

                  <div v-if="passwordSuccess" class="success-banner">{{ passwordSuccess }}</div>
                  <div v-if="passwordError" class="error-banner">{{ passwordError }}</div>

                  <div class="form-group">
                    <label>当前密码</label>
                    <input
                      v-model="passwordForm.old_password"
                      type="password"
                      class="form-control"
                      placeholder="请输入当前密码"
                    />
                  </div>

                  <div class="form-group">
                    <label>新密码</label>
                    <input
                      v-model="passwordForm.new_password"
                      type="password"
                      class="form-control"
                      placeholder="请输入新密码"
                    />
                  </div>

                  <div class="form-group">
                    <label>确认新密码</label>
                    <input
                      v-model="passwordForm.confirm_password"
                      type="password"
                      class="form-control"
                      placeholder="请再次输入新密码"
                    />
                  </div>

                  <div class="form-actions">
                    <button @click="changePassword" class="btn-primary" :disabled="changingPassword">
                      {{ changingPassword ? '提交中...' : '更新密码' }}
                    </button>
                  </div>
                </section>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useModalStore } from '@/stores/modal'
import api from '@/api'
import {
  buildDiscussionPath,
  formatMonth,
  formatRelativeTime,
  getUserAvatarColor,
  normalizeDiscussion,
  normalizePost,
  unwrapList
} from '@/utils/forum'

const route = useRoute()
const authStore = useAuthStore()
const modalStore = useModalStore()

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
  email: '',
})

const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})
const preferences = ref({
  follow_after_reply: false,
  follow_after_create: false,
  notify_new_post: true,
})

const isOwnProfile = computed(() => {
  return authStore.user && user.value && authStore.user.id === user.value.id
})

const isOnline = computed(() => {
  if (!user.value?.last_seen_at) return false
  const lastSeen = new Date(user.value.last_seen_at)
  const now = new Date()
  return (now - lastSeen) < 5 * 60 * 1000
})

function getUserPrimaryGroup(userValue) {
  return userValue?.primary_group || null
}

function getUserPrimaryGroupIcon(userValue) {
  return getUserPrimaryGroup(userValue)?.icon || ''
}

function getUserPrimaryGroupColor(userValue) {
  return getUserPrimaryGroup(userValue)?.color || '#4d698e'
}

function getUserPrimaryGroupLabel(userValue) {
  return getUserPrimaryGroup(userValue)?.name || ''
}

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
    const data = route.params.id
      ? await api.get(`/users/${route.params.id}`)
      : await api.get('/users/me')

    user.value = data

    editForm.value = {
      display_name: data.display_name || '',
      bio: data.bio || '',
      email: data.email || '',
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
        limit: 20,
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
        limit: 20,
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
      ...updatedUser,
    }

    editForm.value = {
      display_name: updatedUser.display_name || '',
      bio: updatedUser.bio || '',
      email: updatedUser.email || '',
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
      follow_after_reply: Boolean(data.follow_after_reply),
      follow_after_create: Boolean(data.follow_after_create),
      notify_new_post: Boolean(data.notify_new_post),
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
      follow_after_reply: preferences.value.follow_after_reply,
      follow_after_create: preferences.value.follow_after_create,
      notify_new_post: preferences.value.notify_new_post,
    })

    preferences.value = { ...data }
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
      new_password: passwordForm.value.new_password,
    })
    passwordSuccess.value = data.message || '密码修改成功'
    passwordForm.value = {
      old_password: '',
      new_password: '',
      confirm_password: '',
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
      email: updatedUser.email || '',
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

function formatDate(dateString) {
  return formatRelativeTime(dateString)
}

function formatJoinDate(dateString) {
  return formatMonth(dateString)
}

function formatLastSeen(dateString) {
  if (!dateString) return '从未'
  const date = new Date(dateString)
  const now = new Date()
  const diff = now - date
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚活跃'
  if (minutes < 60) return `${minutes}分钟前活跃`
  if (hours < 24) return `${hours}小时前活跃`
  if (days < 30) return `${days}天前活跃`
  return date.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.profile-page {
  background: #f5f8fa;
  min-height: calc(100vh - 56px);
}

.loading-page,
.error-page {
  text-align: center;
  padding: 100px 20px;
  color: #aaa;
  font-size: 15px;
}

.user-hero {
  color: white;
  position: relative;
  margin-bottom: -20px;
}

.hero-background {
  background: linear-gradient(rgba(0, 0, 0, 0.1), rgba(0, 0, 0, 0.2));
  padding: 40px 0 60px 0;
}

.user-card {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.user-avatar {
  flex-shrink: 0;
  position: relative;
}

.avatar-large {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.25);
  border: 3px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  font-weight: 600;
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.avatar-image {
  object-fit: cover;
  background: rgba(255, 255, 255, 0.18);
}

.avatar-group-badge {
  position: absolute;
  right: -2px;
  top: -2px;
  z-index: 1;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.92);
  color: white;
  box-shadow: 0 8px 18px rgba(18, 29, 41, 0.22);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.avatar-group-badge i {
  font-size: 13px;
}

.avatar-uploader {
  position: absolute;
  right: -8px;
  bottom: -6px;
  z-index: 2;
  cursor: pointer;
}

.avatar-uploader.disabled {
  cursor: default;
}

.avatar-input {
  display: none;
}

.avatar-upload-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 76px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(47, 60, 77, 0.88);
  color: white;
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 8px 20px rgba(21, 32, 43, 0.2);
}

.user-info-wrapper {
  flex: 1;
  padding-top: 8px;
}

.user-identity {
  font-size: 32px;
  font-weight: 300;
  margin: 0 0 10px 0;
  display: block;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  color: white;
}

.user-badges {
  list-style: none;
  padding: 0;
  margin: 0 0 12px 0;
  display: flex;
  gap: 6px;
}

.user-badges li {
  display: inline-block;
}

.badge-admin {
  background: rgba(231, 76, 60, 0.95);
  color: white;
  padding: 4px 12px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.user-info {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 13px;
  opacity: 0.95;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  color: white;
}

.user-info li {
  display: inline-block;
  margin-right: 18px;
}

.user-info i {
  margin-right: 6px;
}

.user-last-seen .fa-circle {
  font-size: 8px;
  vertical-align: middle;
}

.user-last-seen .fa-circle.online {
  color: #2ecc71;
}

.user-card-controls {
  display: flex;
  align-items: flex-start;
  padding-top: 8px;
}

.btn-control {
  background: rgba(255, 255, 255, 0.15);
  border: 2px solid rgba(255, 255, 255, 0.4);
  color: white;
  padding: 9px 18px;
  border-radius: 3px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.btn-control:hover {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.6);
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

.btn-control i {
  font-size: 13px;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.user-page-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 25px;
  padding: 40px 0 30px 0;
}

.user-sidebar {
  position: sticky;
  top: 76px;
  height: fit-content;
}

.side-nav ul {
  list-style: none;
  padding: 0;
  margin: 0;
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
  overflow: hidden;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  color: #555;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.15s;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
}

.side-nav ul li:last-child .nav-link {
  border-bottom: none;
}

.nav-link:hover {
  background: #f8fafb;
  text-decoration: none;
  color: #333;
}

.nav-link.active {
  background: #4d698e;
  color: white;
}

.nav-link i {
  width: 18px;
  text-align: center;
  font-size: 15px;
}

.nav-link span:first-of-type {
  flex: 1;
  font-weight: 500;
}

.badge-count {
  background: rgba(0, 0, 0, 0.08);
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  min-width: 24px;
  text-align: center;
}

.nav-link.active .badge-count {
  background: rgba(255, 255, 255, 0.25);
}

.user-content {
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.content-section {
  padding: 25px;
  min-height: 200px;
}

.section-header {
  margin-bottom: 24px;
}

.section-header h2 {
  font-size: 22px;
  color: #24313f;
  margin-bottom: 8px;
}

.section-header p {
  color: #6b7a88;
  line-height: 1.6;
}

.loading-small {
  text-align: center;
  padding: 50px;
  color: #aaa;
  font-size: 14px;
}

.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: #aaa;
  font-size: 15px;
}

.empty-state p {
  margin: 0;
  line-height: 1.6;
}

.discussion-list,
.post-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.discussion-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 0;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.15s;
}

.discussion-item:hover,
.post-item:hover {
  background: #fafbfc;
  margin: 0 -25px;
}

.discussion-item:hover {
  padding: 18px 25px;
}

.discussion-item:last-child,
.post-item:last-child {
  border-bottom: none;
}

.discussion-main {
  flex: 1;
  min-width: 0;
}

.discussion-title {
  font-size: 16px;
  color: #333;
  font-weight: 500;
  display: block;
  margin-bottom: 6px;
  line-height: 1.4;
}

.discussion-title:hover {
  color: #4d698e;
  text-decoration: none;
}

.discussion-title-row,
.post-header-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.discussion-meta {
  font-size: 13px;
  color: #aaa;
}

.discussion-stats {
  display: flex;
  gap: 15px;
  color: #aaa;
  font-size: 14px;
  padding-left: 15px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stat i {
  font-size: 14px;
}

.post-item {
  padding: 20px 0;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.15s;
}

.post-item:hover {
  padding: 20px 25px;
}

.post-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.approval-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fff3cd;
  color: #856404;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.approval-pill--rejected {
  background: #fdeeee;
  color: #b14545;
}

.approval-note {
  margin: 10px 0 0;
  color: #9a5050;
  font-size: 13px;
  line-height: 1.6;
}

.post-discussion-link {
  color: #4d698e;
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}

.post-discussion-link:hover {
  text-decoration: none;
  color: #3d5875;
}

.post-discussion-link i {
  font-size: 12px;
}

.post-time {
  font-size: 13px;
  color: #aaa;
}

.post-content {
  color: #555;
  line-height: 1.7;
  font-size: 15px;
}

.settings-card {
  border: 1px solid #e5ebf0;
  border-radius: 12px;
  padding: 22px 24px;
  background: #fbfcfd;
}

.settings-card--stacked {
  margin-top: 18px;
}

.settings-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}

.settings-card-header h3 {
  font-size: 18px;
  color: #24313f;
  margin-bottom: 6px;
}

.settings-card-header p {
  color: #6b7a88;
  line-height: 1.6;
}

.security-grid {
  display: grid;
  gap: 18px;
}

.security-card-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.security-card-header h3 {
  font-size: 18px;
  color: #24313f;
  margin-bottom: 6px;
}

.security-card-header p,
.email-summary p {
  color: #6b7a88;
  line-height: 1.6;
}

.email-summary {
  margin-bottom: 18px;
}

.email-summary strong {
  color: #24313f;
}

.email-status {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.email-status.confirmed {
  background: #edf8f1;
  color: #1f7a45;
}

.email-status.pending {
  background: #fff3cd;
  color: #856404;
}

.success-banner,
.error-banner {
  padding: 12px 14px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
  line-height: 1.6;
}

.success-banner {
  background: #edf8f1;
  color: #1f7a45;
}

.error-banner {
  background: #fdf0f0;
  color: #b03a37;
}

.form-group {
  margin-bottom: 20px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #333;
  font-size: 14px;
}

.form-control {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 14px;
  font-family: inherit;
}

.form-control:focus {
  outline: none;
  border-color: #4d698e;
}

.form-help {
  display: block;
  margin-top: 6px;
  color: #7a8895;
  font-size: 12px;
}

.form-actions {
  display: flex;
  justify-content: flex-start;
  gap: 10px;
}

.preferences-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preference-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 8px;
  background: white;
  border: 1px solid #e7edf2;
}

.preference-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #324150;
}

.preference-copy small {
  color: #7d8b97;
}

.preference-item input {
  width: 18px;
  height: 18px;
  accent-color: #4d698e;
  flex-shrink: 0;
}

.loading-small--inline {
  padding: 16px 0;
}

.btn-primary,
.btn-secondary {
  padding: 8px 16px;
  border-radius: 3px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background: #4d698e;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #3d5875;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #e3e8ed;
  color: #555;
}

.btn-secondary:hover:not(:disabled) {
  background: #d3d8dd;
}

@media (max-width: 768px) {
  .user-card {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .user-info-wrapper {
    text-align: center;
  }

  .user-badges {
    justify-content: center;
  }

  .avatar-group-badge {
    width: 24px;
    height: 24px;
  }

  .avatar-group-badge i {
    font-size: 11px;
  }

  .user-page-layout {
    grid-template-columns: 1fr;
  }

  .user-sidebar {
    position: static;
  }

  .security-card-header {
    flex-direction: column;
  }

  .settings-card-header,
  .preference-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
