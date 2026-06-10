<template>
  <AdminPage
    class-name="UsersPage"
    icon="fas fa-users"
    :title="usersCopy?.pageTitle || '用户管理'"
    :description="usersCopy?.pageDescription || '管理论坛用户'"
  >
    <div class="UsersPage-content">
      <!-- 搜索栏 -->
      <div class="UsersPage-search">
        <label class="sr-only" for="user-search">{{ usersCopy?.searchLabel || '搜索用户' }}</label>
        <input
          id="user-search"
          v-model="searchQuery"
          name="user_search"
          type="text"
          class="FormControl"
          :placeholder="usersCopy?.searchPlaceholder || '搜索用户名或邮箱...'"
          @input="handleSearch"
        />
      </div>

      <!-- 用户列表 -->
      <div class="UsersPage-list">
        <div class="UserTable-wrap">
          <table class="UserTable">
            <thead>
              <tr>
                <th>{{ usersCopy?.tableIdHeader || 'ID' }}</th>
                <th>{{ usersCopy?.tableUsernameHeader || '用户名' }}</th>
                <th>{{ usersCopy?.tableEmailHeader || '邮箱' }}</th>
                <th>{{ usersCopy?.groupsLabel || '用户组' }}</th>
                <th>{{ usersCopy?.tableDiscussionHeader || '讨论' }}</th>
                <th>{{ usersCopy?.tableReplyHeader || '回复' }}</th>
                <th>{{ usersCopy?.tableJoinedHeader || '加入时间' }}</th>
                <th>{{ usersCopy?.tableStatusHeader || '状态' }}</th>
                <th>{{ usersCopy?.tableActionHeader || '操作' }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="9" class="UserTable-loading">
                  <AdminStateBlock tone="subtle">{{ usersCopy?.loadingText || '加载中...' }}</AdminStateBlock>
                </td>
              </tr>
              <tr v-else-if="loadError">
                <td colspan="9" class="UserTable-empty">
                  <AdminStateBlock tone="danger">{{ loadError }}</AdminStateBlock>
                </td>
              </tr>
              <tr v-else-if="users.length === 0">
                <td colspan="9" class="UserTable-empty">
                  <AdminStateBlock>{{ usersCopy?.emptyText || '暂无用户' }}</AdminStateBlock>
                </td>
              </tr>
              <tr v-for="user in users" v-else :key="user.id">
                <td :data-label="usersCopy?.tableIdHeader || 'ID'">{{ user.id }}</td>
                <td :data-label="usersCopy?.tableUsernameHeader || '用户名'">
                  <strong>{{ user.username }}</strong>
                </td>
                <td :data-label="usersCopy?.tableEmailHeader || '邮箱'">{{ user.email }}</td>
                <td :data-label="usersCopy?.groupsLabel || '用户组'">
                  <div v-if="getUserGroupBadges(user).length" class="UserGroupBadges">
                    <span
                      v-for="group in getUserGroupBadges(user)"
                      :key="`${user.id}-${group.id}-${group.name}`"
                      class="UserGroupBadge"
                    >
                      <span
                        class="UserGroupBadge-icon"
                        :style="{ backgroundColor: group.color || usersConfig?.groupBadgeFallbackColor || '#7f8c8d' }"
                      >
                        <i v-if="group.icon" :class="group.icon"></i>
                        <span v-else>{{ getGroupFallbackLabel(group) }}</span>
                      </span>
                      <span class="UserGroupBadge-name">{{ group.name }}</span>
                    </span>
                  </div>
                  <span v-else class="UserGroupEmpty">{{ usersCopy?.noGroupsText || '-' }}</span>
                </td>
                <td :data-label="usersCopy?.tableDiscussionHeader || '讨论'">{{ user.discussion_count }}</td>
                <td :data-label="usersCopy?.tableReplyHeader || '回复'">{{ user.comment_count }}</td>
                <td :data-label="usersCopy?.tableJoinedHeader || '加入时间'">{{ formatDate(user.joined_at) }}</td>
                <td :data-label="usersCopy?.tableStatusHeader || '状态'">
                  <span
                    class="UserStatus"
                    :class="statusClass(user)"
                  >
                    {{ statusLabel(user) }}
                  </span>
                </td>
                <td :data-label="usersCopy?.tableActionHeader || '操作'">
                  <button type="button" class="Button Button--small" :disabled="savingDetails" @click="editUser(user)">
                    {{ usersCopy?.editLabel || '编辑' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="UserMobileList">
          <AdminStateBlock v-if="loading" class="UserMobileState" tone="subtle">{{ usersCopy?.loadingText || '加载中...' }}</AdminStateBlock>
          <AdminStateBlock v-else-if="loadError" class="UserMobileState" tone="danger">{{ loadError }}</AdminStateBlock>
          <AdminStateBlock v-else-if="users.length === 0" class="UserMobileState">{{ usersCopy?.emptyText || '暂无用户' }}</AdminStateBlock>
          <article v-for="user in users" v-else :key="`mobile-${user.id}`" class="UserMobileCard">
            <div class="UserMobileCard-header">
              <div class="UserMobileCard-identity">
                <div class="UserMobileCard-nameRow">
                  <strong>{{ user.username }}</strong>
                  <span
                    class="UserStatus"
                    :class="statusClass(user)"
                  >
                    {{ statusLabel(user) }}
                  </span>
                </div>
              </div>

              <button type="button" class="Button Button--small UserMobileCard-edit" :disabled="savingDetails" @click="editUser(user)">
                {{ usersCopy?.editLabel || '编辑' }}
              </button>
            </div>

            <dl class="UserMobileCard-meta">
              <div class="UserMobileCard-metaItem">
                <dt>{{ usersCopy?.mobileEmailLabel || '邮箱' }}</dt>
                <dd>{{ user.email || (usersCopy?.noEmailValueText || '-') }}</dd>
              </div>
              <div class="UserMobileCard-metaItem UserMobileCard-metaItem--full">
                <dt>{{ usersCopy?.groupsLabel || '用户组' }}</dt>
                <dd>
                  <div v-if="getUserGroupBadges(user).length" class="UserGroupBadges">
                    <span
                      v-for="group in getUserGroupBadges(user)"
                      :key="`${user.id}-${group.id}-${group.name}-mobile`"
                      class="UserGroupBadge"
                    >
                      <span
                        class="UserGroupBadge-icon"
                        :style="{ backgroundColor: group.color || usersConfig?.groupBadgeFallbackColor || '#7f8c8d' }"
                      >
                        <i v-if="group.icon" :class="group.icon"></i>
                        <span v-else>{{ getGroupFallbackLabel(group) }}</span>
                      </span>
                      <span class="UserGroupBadge-name">{{ group.name }}</span>
                    </span>
                  </div>
                  <span v-else class="UserGroupEmpty">{{ usersCopy?.noGroupsText || '-' }}</span>
                </dd>
              </div>
              <div class="UserMobileCard-metaItem">
                <dt>{{ usersCopy?.mobileIdLabel || 'ID' }}</dt>
                <dd>#{{ user.id }}</dd>
              </div>
              <div class="UserMobileCard-metaItem">
                <dt>{{ usersCopy?.mobileDiscussionLabel || '讨论' }}</dt>
                <dd>{{ user.discussion_count }}</dd>
              </div>
              <div class="UserMobileCard-metaItem">
                <dt>{{ usersCopy?.mobileReplyLabel || '回复' }}</dt>
                <dd>{{ user.comment_count }}</dd>
              </div>
              <div class="UserMobileCard-metaItem UserMobileCard-metaItem--full">
                <dt>{{ usersCopy?.mobileJoinedLabel || '加入时间' }}</dt>
                <dd>{{ formatDate(user.joined_at) || '-' }}</dd>
              </div>
            </dl>
          </article>
        </div>
      </div>

      <AdminPagination
        :page="page"
        :total="total"
        :limit="limit"
        :disabled="loading"
        @change="changePage"
      />
    </div>

    <div v-if="showEditModal" class="Modal" @click.self="closeModal">
      <div class="Modal-content Modal-content--user">
        <div class="Modal-header Modal-header--user">
          <h3>{{ usersCopy?.modalTitle || '编辑用户' }}</h3>
          <button type="button" class="Modal-close" @click="closeModal">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <AdminStateBlock v-if="loadingDetails" class="Modal-loading" tone="subtle">{{ usersCopy?.loadingText || '加载中...' }}</AdminStateBlock>
        <div v-else class="Modal-body Modal-body--user">
          <div class="UserModal-grid UserModal-grid--two">
            <div class="Form-group Form-group--userCompact">
              <label for="user-username" class="Form-labelStrong">{{ usersCopy?.usernameLabel || '用户名' }}</label>
              <input
                id="user-username"
                v-model="formData.username"
                name="user_username"
                type="text"
                class="FormControl"
              />
            </div>

            <div class="Form-group Form-group--userCompact">
              <label for="user-email" class="Form-labelStrong">{{ usersCopy?.emailLabel || '邮箱' }}</label>
              <input
                id="user-email"
                v-model="formData.email"
                name="user_email"
                type="email"
                class="FormControl"
              />
            </div>
          </div>

          <div class="Form-group Form-group--userCompact">
            <label for="user-bio" class="Form-labelStrong">{{ usersCopy?.bioLabel || '个人简介' }}</label>
            <textarea
              id="user-bio"
              v-model="formData.bio"
              name="user_bio"
              class="FormControl"
              rows="3"
              :placeholder="usersCopy?.bioPlaceholder || '管理员后台可直接维护用户简介'"
            ></textarea>
          </div>

          <div class="UserModal-grid UserModal-grid--two">
            <label class="CheckboxField CheckboxField--toggle UserModal-toggleCard">
              <input
                v-model="formData.is_staff"
                name="user_is_staff"
                type="checkbox"
              />
              <span>{{ usersCopy?.staffLabel || '管理员' }}</span>
            </label>
            <label class="CheckboxField CheckboxField--toggle UserModal-toggleCard">
              <input
                v-model="formData.is_email_confirmed"
                name="user_is_email_confirmed"
                type="checkbox"
              />
              <span>{{ usersCopy?.emailConfirmedLabel || '邮箱已验证' }}</span>
            </label>
          </div>

          <div class="Form-group Form-group--userCompact">
            <label class="Form-labelStrong">{{ usersCopy?.groupsLabel || '用户组' }}</label>
            <AdminMultiSelectMenu
              input-id="user-group-select"
              v-model="formData.group_ids"
              :options="userGroupOptions"
              :summary="selectedGroupSummary"
              :placeholder="usersCopy?.groupsPlaceholder || '请选择用户组'"
              :aria-label="usersCopy?.groupsLabel || '用户组'"
            />
          </div>

          <div class="Form-group Form-group--userCompact">
            <label for="user-suspended-until" class="Form-labelStrong">{{ usersCopy?.suspendedUntilLabel || '封禁截止时间' }}</label>
            <input
              id="user-suspended-until"
              v-model="formData.suspended_until"
              name="user_suspended_until"
              type="datetime-local"
              class="FormControl"
            />
            <small class="Form-help">{{ usersCopy?.suspendedUntilHelpText || '留空表示未封禁' }}</small>
          </div>

          <div class="Form-group Form-group--userCompact">
            <label for="user-suspend-reason" class="Form-labelStrong">{{ usersCopy?.suspendReasonLabel || '封禁原因' }}</label>
            <input
              id="user-suspend-reason"
              v-model="formData.suspend_reason"
              name="user_suspend_reason"
              type="text"
              class="FormControl"
              :placeholder="usersCopy?.suspendReasonPlaceholder || '例如：垃圾广告、违规内容'"
            />
          </div>

          <div class="Form-group Form-group--userCompact">
            <label for="user-suspend-message" class="Form-labelStrong">{{ usersCopy?.suspendMessageLabel || '对用户显示的信息' }}</label>
            <textarea
              id="user-suspend-message"
              v-model="formData.suspend_message"
              name="user_suspend_message"
              class="FormControl"
              rows="3"
              :placeholder="usersCopy?.suspendMessagePlaceholder || '显示给被封禁用户的提示'"
            ></textarea>
          </div>

          <div class="UserModal-actions">
            <button
              v-if="canDeleteCurrentUser"
              type="button"
              class="Button Button--danger"
              :disabled="saving || deleting"
              @click="deleteUser"
            >
              {{ deleting ? (usersCopy?.deletingLabel || '删除中...') : (usersCopy?.deleteLabel || '删除用户') }}
            </button>
            <span v-else class="Modal-footerNote">{{ usersCopy?.deleteBlockedText || '当前登录管理员账号不允许删除' }}</span>
            <button type="button" class="Button Button--primary UserModal-saveButton" :disabled="saving || deleting" @click="saveUser">
              {{ saving ? (usersCopy?.savingLabel || '保存中...') : (usersCopy?.saveLabel || '保存') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref } from '@bias/core'
import {
  adminApi,
  AdminMultiSelectMenu,
  AdminPage,
  AdminPagination,
  AdminStateBlock,
  getAdminUsersPageActionMeta,
  getAdminUsersPageConfig,
  getAdminUsersPageCopy,
  useModalStore,
} from '@bias/admin/components'
import { useAuthStore } from '@bias/users'

const authStore = useAuthStore()
const modalStore = useModalStore()
const users = ref([])
const loading = ref(true)
const loadError = ref('')
const searchQuery = ref('')
const page = ref(1)
const limit = ref(20)
const total = ref(0)
const availableGroups = ref([])
const showEditModal = ref(false)
const loadingDetails = ref(false)
const savingDetails = ref(false)
const saving = ref(false)
const deleting = ref(false)
const editingUserId = ref(null)
const originalUserRiskSnapshot = ref(null)

let searchTimeout = null

const formData = ref(getEmptyForm())
const currentAdminId = computed(() => authStore.user?.id ?? null)
const usersCopy = computed(() => getAdminUsersPageCopy())
const usersConfig = computed(() => getAdminUsersPageConfig())
const usersActionMeta = computed(() => getAdminUsersPageActionMeta())
const userGroupOptions = computed(() => (
  availableGroups.value.map(group => ({
    value: group.id,
    label: group.name,
    icon: group.icon,
    color: group.color || '#4d698e',
    fallbackLabel: getGroupFallbackLabel(group),
  }))
))

onMounted(() => {
  limit.value = usersConfig.value?.paginationLimit || 20
  loadGroups()
  loadUsers()
})

async function loadUsers() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await adminApi.get('/admin/users', {
      params: {
        page: page.value,
        limit: limit.value,
        q: searchQuery.value || undefined,
      },
    })
    users.value = data.data
    total.value = data.total
  } catch (error) {
    console.error('加载用户失败:', error)
    loadError.value = error.response?.data?.error || error.message || usersActionMeta.value?.loadUsersFailedMessage || '加载用户失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    page.value = 1
    loadUsers()
  }, usersConfig.value?.searchDebounceMs || 500)
}

function changePage(newPage) {
  page.value = newPage
  loadUsers()
}

async function loadGroups() {
  try {
    availableGroups.value = await adminApi.get('/admin/groups')
  } catch (error) {
    console.error('加载用户组失败:', error)
    await modalStore.alert({
      title: usersActionMeta.value?.loadGroupsFailedTitle || '加载用户组失败',
      message: error.response?.data?.error || error.message || usersActionMeta.value?.loadGroupsFailedMessage || '未知错误',
      tone: 'danger'
    })
  }
}

async function editUser(user) {
  showEditModal.value = true
  loadingDetails.value = true
  editingUserId.value = user.id
  formData.value = getEmptyForm()
  originalUserRiskSnapshot.value = null

  try {
    const detail = await adminApi.get(`/admin/users/${user.id}`)
    formData.value = {
      username: detail.username || '',
      email: detail.email || '',
      display_name: detail.display_name || '',
      bio: detail.bio || '',
      is_staff: Boolean(detail.is_staff),
      is_email_confirmed: Boolean(detail.is_email_confirmed),
      group_ids: (detail.groups || []).map(group => group.id),
      suspended_until: formatDateTimeLocal(detail.suspended_until),
      suspend_reason: detail.suspend_reason || '',
      suspend_message: detail.suspend_message || '',
    }
    originalUserRiskSnapshot.value = createUserRiskSnapshot(formData.value)
  } catch (error) {
    console.error('加载用户详情失败:', error)
    await modalStore.alert({
      title: usersActionMeta.value?.loadDetailFailedTitle || '加载用户详情失败',
      message: error.response?.data?.error || error.message || usersActionMeta.value?.loadDetailFailedMessage || '未知错误',
      tone: 'danger'
    })
    closeModal()
  } finally {
    loadingDetails.value = false
  }
}

async function saveUser() {
  if (!editingUserId.value) return

  const riskChanges = getUserRiskChanges()
  if (riskChanges.length > 0) {
    const confirmed = await modalStore.confirm({
      title: usersActionMeta.value?.saveRiskConfirmTitle || '保存用户变更',
      message: usersActionMeta.value?.saveRiskConfirmMessage?.(riskChanges.join('、')) || `以下变更会立即影响用户权限或账号状态：${riskChanges.join('、')}。确定保存吗？`,
      confirmText: usersActionMeta.value?.saveConfirmText || '保存',
      cancelText: usersActionMeta.value?.saveCancelText || '取消',
      tone: 'warning'
    })
    if (!confirmed) {
      return
    }
  }

  saving.value = true
  savingDetails.value = true
  try {
    await adminApi.put(`/admin/users/${editingUserId.value}`, {
      ...formData.value,
      suspended_until: formData.value.suspended_until || null,
    })
    closeModal()
    await loadUsers()
    await modalStore.alert({
      title: usersActionMeta.value?.saveSuccessTitle || '用户已保存',
      message: usersActionMeta.value?.saveSuccessMessage || '用户资料和状态已更新。',
      tone: 'success'
    })
  } catch (error) {
    console.error('保存用户失败:', error)
    await modalStore.alert({
      title: usersActionMeta.value?.saveFailedTitle || '保存失败',
      message: error.response?.data?.error || error.message || usersActionMeta.value?.saveFailedMessage || '未知错误',
      tone: 'danger'
    })
  } finally {
    saving.value = false
    savingDetails.value = false
  }
}

async function deleteUser() {
  if (!editingUserId.value || !canDeleteCurrentUser.value) return

  const confirmed = await modalStore.confirm({
    title: usersActionMeta.value?.deleteConfirmTitle || '删除用户',
    message: usersActionMeta.value?.deleteConfirmMessage?.(formData.value.username || editingUserId.value) || `确定删除用户“${formData.value.username || editingUserId.value}”吗？该操作不可撤销。`,
    confirmText: usersActionMeta.value?.deleteConfirmText || '删除',
    cancelText: usersActionMeta.value?.deleteCancelText || '取消',
    tone: 'danger'
  })
  if (!confirmed) {
    return
  }

  deleting.value = true
  savingDetails.value = true
  try {
    const deletedUsername = formData.value.username || editingUserId.value
    await adminApi.delete(`/admin/users/${editingUserId.value}`)
    closeModal()
    await loadUsers()
    await modalStore.alert({
      title: usersActionMeta.value?.deleteSuccessTitle || '用户已删除',
      message: usersActionMeta.value?.deleteSuccessMessage?.(deletedUsername) || `用户“${deletedUsername}”已删除。`,
      tone: 'success'
    })
  } catch (error) {
    console.error('删除用户失败:', error)
    await modalStore.alert({
      title: usersActionMeta.value?.deleteFailedTitle || '删除失败',
      message: error.response?.data?.error || error.message || usersActionMeta.value?.deleteFailedMessage || '未知错误',
      tone: 'danger'
    })
  } finally {
    deleting.value = false
    savingDetails.value = false
  }
}

function closeModal() {
  showEditModal.value = false
  loadingDetails.value = false
  saving.value = false
  deleting.value = false
  editingUserId.value = null
  originalUserRiskSnapshot.value = null
  formData.value = getEmptyForm()
}

function getEmptyForm() {
  return {
    username: '',
    email: '',
    display_name: '',
    bio: '',
    is_staff: false,
    is_email_confirmed: false,
    group_ids: [],
    suspended_until: '',
    suspend_reason: '',
    suspend_message: '',
  }
}

function createUserRiskSnapshot(value) {
  return {
    is_staff: Boolean(value.is_staff),
    group_ids: [...(value.group_ids || [])].map(Number).sort((a, b) => a - b).join(','),
    suspended_until: value.suspended_until || '',
    suspend_reason: value.suspend_reason || '',
    suspend_message: value.suspend_message || '',
  }
}

function getUserRiskChanges() {
  const previous = originalUserRiskSnapshot.value
  if (!previous) {
    return []
  }

  const current = createUserRiskSnapshot(formData.value)
  const changes = []
  if (previous.is_staff !== current.is_staff) {
    changes.push(usersCopy.value?.riskAdminLabel || '管理员权限')
  }
  if (previous.group_ids !== current.group_ids) {
    changes.push(usersCopy.value?.riskGroupLabel || '用户组')
  }
  if (
    previous.suspended_until !== current.suspended_until
    || previous.suspend_reason !== current.suspend_reason
    || previous.suspend_message !== current.suspend_message
  ) {
    changes.push(usersCopy.value?.riskSuspensionLabel || '封禁状态')
  }
  return changes
}

function statusLabel(user) {
  if (user.is_suspended) return usersCopy.value?.statusSuspendedLabel || '已封禁'
  if (user.is_email_confirmed) return usersCopy.value?.statusActiveLabel || '已激活'
  return usersCopy.value?.statusPendingLabel || '未激活'
}

function statusClass(user) {
  if (user.is_suspended) return 'UserStatus--suspended'
  if (user.is_email_confirmed) return 'UserStatus--active'
  return 'UserStatus--pending'
}

function getPrimaryGroup(user) {
  return user?.primary_group || null
}

function getUserGroupBadges(user) {
  const badges = []
  const seen = new Set()

  const addGroup = (group) => {
    if (!group) return
    const key = `${group.id}-${group.name}`
    if (seen.has(key)) return
    seen.add(key)
    badges.push(group)
  }

  addGroup(getPrimaryGroup(user))
  for (const group of Array.isArray(user?.groups) ? user.groups : []) {
    addGroup(group)
  }

  return badges
}

function getGroupFallbackLabel(group) {
  return (group?.name || usersConfig.value?.groupFallbackUnknownLabel || '?').slice(0, 1).toUpperCase()
}

function formatDate(dateString) {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString(usersConfig.value?.dateLocale || 'zh-CN')
}

function formatDateTimeLocal(dateString) {
  if (!dateString) return ''
  const date = new Date(dateString)
  if (Number.isNaN(date.getTime())) return ''

  const offset = date.getTimezoneOffset()
  const localDate = new Date(date.getTime() - offset * 60000)
  return localDate.toISOString().slice(0, 16)
}

const canDeleteCurrentUser = computed(() => {
  if (!editingUserId.value) return false
  if (!currentAdminId.value) return true
  return Number(editingUserId.value) !== Number(currentAdminId.value)
})

const selectedGroups = computed(() => {
  const selectedIds = new Set(formData.value.group_ids)
  return availableGroups.value.filter(group => selectedIds.has(group.id))
})

const selectedGroupSummary = computed(() => {
  if (!selectedGroups.value.length) {
    return usersCopy.value?.groupsPlaceholder || '请选择用户组'
  }
  if (selectedGroups.value.length <= 2) {
    return selectedGroups.value.map(group => group.name).join('、')
  }
  return `${selectedGroups.value[0].name}、${selectedGroups.value[1].name} 等 ${selectedGroups.value.length} 个用户组`
})
</script>

<style scoped>
.UsersPage-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.UsersPage-search {
  max-width: 400px;
}

.UsersPage-list {
  min-width: 0;
}

.UserMobileList {
  display: none;
}

.UserTable-wrap {
  width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  border: 1px solid var(--forum-border-color);
  border-radius: 12px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.UserTable-wrap::-webkit-scrollbar {
  height: 10px;
}

.UserTable-wrap::-webkit-scrollbar-thumb {
  background: var(--forum-border-strong);
  border-radius: var(--forum-radius-pill);
}

.UserTable {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
  background: var(--forum-bg-elevated);
}

.UserTable thead th {
  padding: 12px;
  background: var(--forum-bg-subtle);
  border-bottom: 2px solid var(--forum-border-color);
  font-size: var(--forum-font-size-sm);
  font-weight: 600;
  text-align: left;
  color: var(--forum-text-muted);
}

.UserTable tbody td {
  padding: 12px;
  border-bottom: 1px solid var(--forum-border-soft);
  font-size: var(--forum-font-size-md);
  vertical-align: top;
}

.UserTable tbody tr:hover {
  background: var(--forum-bg-elevated-strong);
}

.UserTable-loading,
.UserTable-empty {
  padding: 18px;
}

.UserGroupBadges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.UserGroupBadge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--forum-bg-elevated-strong);
  color: var(--forum-text-color);
  font-size: 13px;
  line-height: 1;
}

.UserGroupBadge-icon {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 10px;
  line-height: 1;
}

.UserGroupBadge-icon i,
.UserGroupBadge-icon span {
  line-height: 1;
}

.UserGroupBadge-name {
  white-space: nowrap;
}

.UserGroupEmpty {
  color: var(--forum-text-soft);
  font-size: 13px;
}

.UserStatus {
  display: inline-block;
  padding: 4px 10px;
  border-radius: var(--forum-radius-sm);
  font-size: var(--forum-font-size-xs);
  font-weight: 600;
}

.UserStatus--active {
  background: color-mix(in srgb, var(--forum-success-color) 18%, white);
  color: #155724;
}

.UserStatus--pending {
  background: var(--forum-warning-bg-strong);
  color: var(--forum-warning-color);
}

.UserStatus--suspended {
  background: color-mix(in srgb, var(--forum-danger-color) 16%, white);
  color: #842029;
}

#admin-app .Modal-content.Modal-content--user {
  width: min(760px, calc(100vw - 24px));
  min-width: min(760px, calc(100vw - 24px));
  background: var(--forum-bg-elevated);
}

#admin-app .Modal-content.Modal-content--user .Modal-header,
#admin-app .Modal-content.Modal-content--user .Modal-body {
  padding: 26px 28px;
}

.Modal-header--user {
  position: relative;
}

.Modal-header--user .Modal-close {
  position: absolute;
  top: 22px;
  right: 22px;
}

.Modal-body--user {
  display: flex;
  flex-direction: column;
  gap: 18px;
  border-top: 1px solid var(--forum-border-color);
}

.Form-group--userCompact {
  margin-bottom: 0;
}

.Form-labelStrong {
  display: inline-block;
  margin-bottom: 10px;
  color: var(--forum-text-color);
  font-size: 14px;
  font-weight: 700;
}

.UserModal-grid {
  display: grid;
  gap: 18px;
}

.UserModal-grid--two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.UserModal-toggleCard {
  justify-content: flex-start;
  gap: 10px;
  min-height: 52px;
  padding: 10px 14px;
  border-radius: 14px;
  background: var(--forum-bg-elevated);
}

.UserModal-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 4px;
}

.UserModal-saveButton {
  min-width: 96px;
  justify-content: center;
}

.FormRow--toggles {
  grid-template-columns: repeat(2, minmax(220px, 1fr));
}

.FormRow--toggles .CheckboxField--toggle {
  justify-content: flex-start;
  gap: 10px;
  min-width: 0;
  min-height: 58px;
  padding: 10px 14px;
}

.FormRow--toggles .CheckboxField--toggle input {
  flex: 0 0 16px;
}

.FormRow--toggles .CheckboxField--toggle span {
  min-width: 0;
  line-height: 1.4;
  white-space: normal;
  overflow-wrap: anywhere;
}

@media (max-width: 768px) {
  .UsersPage-search {
    max-width: none;
  }

  .FormRow--toggles {
    gap: 10px;
    grid-template-columns: 1fr;
  }

  #admin-app .Modal-content.Modal-content--user {
    min-width: 0;
  }

  .UserModal-grid--two {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 680px) {
  .UserTable-wrap {
    display: none;
  }

  .UserMobileList {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .UserMobileState {
    padding: 0;
  }

  .UserMobileCard {
    padding: 14px;
    border: 1px solid var(--forum-border-color);
    border-radius: 16px;
    background: var(--forum-bg-elevated);
    box-shadow: 0 10px 26px rgba(28, 46, 67, 0.06);
  }

  .UserMobileCard-header {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    justify-content: space-between;
  }

  .UserMobileCard-identity {
    min-width: 0;
    flex: 1;
  }

  .UserMobileCard-nameRow {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .UserMobileCard-nameRow strong {
    font-size: 16px;
    color: var(--forum-text-color);
  }

  .UserMobileCard-edit {
    flex: 0 0 auto;
    min-width: 64px;
    min-height: 34px;
  }

  .UserMobileCard-meta {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    margin: 14px 0 0;
  }

  .UserMobileCard-metaItem {
    min-width: 0;
    padding: 10px 12px;
    border-radius: 12px;
    background: var(--forum-bg-elevated-strong);
  }

  .UserMobileCard-metaItem--full {
    grid-column: 1 / -1;
  }

  .UserMobileCard-metaItem dt {
    margin: 0 0 4px;
    color: var(--forum-text-soft);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .UserMobileCard-metaItem dd {
    margin: 0;
    color: var(--forum-text-muted);
    font-size: var(--forum-font-size-sm);
    line-height: 1.5;
    word-break: break-word;
  }

  .UserGroupBadges {
    gap: 6px;
  }
}

@media (max-width: 420px) {
  .UserMobileCard-header {
    flex-direction: column;
    align-items: stretch;
  }

  .UserMobileCard-edit {
    width: 100%;
  }

  .UserMobileCard-meta {
    grid-template-columns: 1fr;
  }
}
</style>
