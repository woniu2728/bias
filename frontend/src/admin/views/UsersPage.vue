<template>
  <AdminPage
    className="UsersPage"
    icon="fas fa-users"
    title="用户管理"
    description="管理论坛用户"
  >
    <div class="UsersPage-content">
      <!-- 搜索栏 -->
      <div class="UsersPage-search">
        <input
          v-model="searchQuery"
          type="text"
          class="FormControl"
          placeholder="搜索用户名或邮箱..."
          @input="handleSearch"
        />
      </div>

      <!-- 用户列表 -->
      <div class="UsersPage-list">
        <div class="UserTable-wrap">
          <table class="UserTable">
            <thead>
              <tr>
                <th>ID</th>
                <th>用户名</th>
                <th>邮箱</th>
                <th>显示名称</th>
                <th>讨论</th>
                <th>回复</th>
                <th>加入时间</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="9" class="UserTable-loading">加载中...</td>
              </tr>
              <tr v-else-if="users.length === 0">
                <td colspan="9" class="UserTable-empty">暂无用户</td>
              </tr>
              <tr v-else v-for="user in users" :key="user.id">
                <td data-label="ID">{{ user.id }}</td>
                <td data-label="用户名">
                  <strong>{{ user.username }}</strong>
                  <div v-if="getUserGroupBadges(user).length" class="UserGroups">
                    <span
                      v-for="group in getUserGroupBadges(user)"
                      :key="`${user.id}-${group.id}-${group.name}`"
                      class="UserGroupIcon"
                      :style="{ backgroundColor: group.color || '#7f8c8d' }"
                      :title="group.name"
                    >
                      <i v-if="group.icon" :class="group.icon"></i>
                      <span v-else>{{ getGroupFallbackLabel(group) }}</span>
                    </span>
                  </div>
                </td>
                <td data-label="邮箱">{{ user.email }}</td>
                <td data-label="显示名称">{{ user.display_name }}</td>
                <td data-label="讨论">{{ user.discussion_count }}</td>
                <td data-label="回复">{{ user.comment_count }}</td>
                <td data-label="加入时间">{{ formatDate(user.joined_at) }}</td>
                <td data-label="状态">
                  <span
                    class="UserStatus"
                    :class="statusClass(user)"
                  >
                    {{ statusLabel(user) }}
                  </span>
                </td>
                <td data-label="操作">
                  <button @click="editUser(user)" class="Button Button--small" :disabled="savingDetails">
                    编辑
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="total > limit" class="UsersPage-pagination">
        <button
          @click="changePage(page - 1)"
          :disabled="page === 1"
          class="Button"
        >
          上一页
        </button>
        <span class="Pagination-info">
          第 {{ page }} 页，共 {{ Math.ceil(total / limit) }} 页
        </span>
        <button
          @click="changePage(page + 1)"
          :disabled="page >= Math.ceil(total / limit)"
          class="Button"
        >
          下一页
        </button>
      </div>
    </div>

    <div v-if="showEditModal" class="Modal" @click.self="closeModal">
      <div class="Modal-content Modal-content--user">
        <div class="Modal-header">
          <h3>编辑用户</h3>
          <button @click="closeModal" class="Modal-close">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div v-if="loadingDetails" class="Modal-loading">加载中...</div>
        <div v-else class="Modal-body">
          <div class="Form-group">
            <label>用户名</label>
            <input v-model="formData.username" type="text" class="FormControl" />
          </div>

          <div class="FormRow">
            <div class="Form-group">
              <label>邮箱</label>
              <input v-model="formData.email" type="email" class="FormControl" />
            </div>
            <div class="Form-group">
              <label>显示名称</label>
              <input v-model="formData.display_name" type="text" class="FormControl" />
            </div>
          </div>

          <div class="Form-group">
            <label>个人简介</label>
            <textarea
              v-model="formData.bio"
              class="FormControl"
              rows="3"
              placeholder="管理员后台可直接维护用户简介"
            ></textarea>
          </div>

          <div class="FormRow">
            <label class="CheckboxField">
              <input v-model="formData.is_staff" type="checkbox" />
              <span>管理员</span>
            </label>
            <label class="CheckboxField">
              <input v-model="formData.is_email_confirmed" type="checkbox" />
              <span>邮箱已验证</span>
            </label>
          </div>

          <div class="Form-group">
            <label>用户组</label>
            <div class="GroupChecklist">
              <label v-for="group in availableGroups" :key="group.id" class="CheckboxField CheckboxField--card">
                <input
                  :checked="formData.group_ids.includes(group.id)"
                  type="checkbox"
                  @change="toggleGroup(group.id, $event)"
                />
                <span :style="{ color: group.color || '#4d698e' }">{{ group.name }}</span>
              </label>
            </div>
          </div>

          <div class="Form-group">
            <label>封禁截止时间</label>
            <input
              v-model="formData.suspended_until"
              type="datetime-local"
              class="FormControl"
            />
            <small class="Form-help">留空表示未封禁</small>
          </div>

          <div class="Form-group">
            <label>封禁原因</label>
            <input
              v-model="formData.suspend_reason"
              type="text"
              class="FormControl"
              placeholder="例如：垃圾广告、违规内容"
            />
          </div>

          <div class="Form-group">
            <label>对用户显示的信息</label>
            <textarea
              v-model="formData.suspend_message"
              class="FormControl"
              rows="3"
              placeholder="显示给被封禁用户的提示"
            ></textarea>
          </div>
        </div>

        <div class="Modal-footer Modal-footer--split">
          <button
            v-if="canDeleteCurrentUser"
            @click="deleteUser"
            class="Button Button--danger"
            :disabled="saving || deleting"
          >
            {{ deleting ? '删除中...' : '删除用户' }}
          </button>
          <span v-else class="Modal-footerNote">当前登录管理员账号不允许删除</span>
          <div class="Modal-footerActions">
            <button @click="closeModal" class="Button">
              取消
            </button>
            <button @click="saveUser" class="Button Button--primary" :disabled="saving || deleting">
              {{ saving ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import api from '../../api'
import { useAuthStore } from '../../stores/auth'

const authStore = useAuthStore()
const users = ref([])
const loading = ref(true)
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

let searchTimeout = null

const formData = ref(getEmptyForm())
const currentAdminId = computed(() => authStore.user?.id ?? null)

onMounted(() => {
  loadGroups()
  loadUsers()
})

async function loadUsers() {
  loading.value = true
  try {
    const data = await api.get('/admin/users', {
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
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    page.value = 1
    loadUsers()
  }, 500)
}

function changePage(newPage) {
  page.value = newPage
  loadUsers()
}

async function loadGroups() {
  try {
    availableGroups.value = await api.get('/admin/groups')
  } catch (error) {
    console.error('加载用户组失败:', error)
  }
}

async function editUser(user) {
  showEditModal.value = true
  loadingDetails.value = true
  editingUserId.value = user.id
  formData.value = getEmptyForm()

  try {
    const detail = await api.get(`/admin/users/${user.id}`)
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
  } catch (error) {
    console.error('加载用户详情失败:', error)
    alert('加载用户详情失败: ' + (error.response?.data?.error || error.message || '未知错误'))
    closeModal()
  } finally {
    loadingDetails.value = false
  }
}

function toggleGroup(groupId, event) {
  if (event.target.checked) {
    if (!formData.value.group_ids.includes(groupId)) {
      formData.value.group_ids.push(groupId)
    }
  } else {
    formData.value.group_ids = formData.value.group_ids.filter(id => id !== groupId)
  }
}

async function saveUser() {
  if (!editingUserId.value) return

  saving.value = true
  savingDetails.value = true
  try {
    await api.put(`/admin/users/${editingUserId.value}`, {
      ...formData.value,
      suspended_until: formData.value.suspended_until || null,
    })
    closeModal()
    await loadUsers()
  } catch (error) {
    console.error('保存用户失败:', error)
    alert('保存失败: ' + (error.response?.data?.error || error.message || '未知错误'))
  } finally {
    saving.value = false
    savingDetails.value = false
  }
}

async function deleteUser() {
  if (!editingUserId.value || !canDeleteCurrentUser.value) return

  if (!window.confirm(`确定删除用户“${formData.value.username || editingUserId.value}”吗？该操作不可撤销。`)) {
    return
  }

  deleting.value = true
  savingDetails.value = true
  try {
    await api.delete(`/admin/users/${editingUserId.value}`)
    closeModal()
    await loadUsers()
  } catch (error) {
    console.error('删除用户失败:', error)
    alert('删除失败: ' + (error.response?.data?.error || error.message || '未知错误'))
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

function statusLabel(user) {
  if (user.is_suspended) return '已封禁'
  if (user.is_email_confirmed) return '已激活'
  return '未激活'
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
  return (group?.name || '?').slice(0, 1).toUpperCase()
}

function formatDate(dateString) {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN')
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

.UserTable-wrap {
  width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  border: 1px solid #e3e8ed;
  border-radius: 12px;
  background: white;
}

.UserTable-wrap::-webkit-scrollbar {
  height: 10px;
}

.UserTable-wrap::-webkit-scrollbar-thumb {
  background: #c8d2dc;
  border-radius: 999px;
}

.FormControl {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 14px;
  box-sizing: border-box;
}

.FormControl:focus {
  outline: none;
  border-color: #4d698e;
}

.UserTable {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
  background: white;
}

.UserTable thead th {
  padding: 12px;
  background: #f5f8fa;
  border-bottom: 2px solid #e3e8ed;
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  color: #666;
}

.UserTable tbody td {
  padding: 12px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
  vertical-align: top;
}

.UserTable tbody tr:hover {
  background: #fafbfc;
}

.UserTable-loading,
.UserTable-empty {
  text-align: center;
  padding: 40px;
  color: #999;
}

.UserGroups {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.UserGroupIcon {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  color: white;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.22);
  font-size: 11px;
}

.UserGroupIcon i,
.UserGroupIcon span {
  line-height: 1;
}

.UserStatus {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 3px;
  font-size: 12px;
  font-weight: 500;
}

.UserStatus--active {
  background: #d4edda;
  color: #155724;
}

.UserStatus--pending {
  background: #fff3cd;
  color: #856404;
}

.UserStatus--suspended {
  background: #f8d7da;
  color: #842029;
}

.Button {
  background: #f5f8fa;
  border: 1px solid #ddd;
  padding: 6px 12px;
  border-radius: 3px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.Button:hover:not(:disabled) {
  background: #e8eef5;
  border-color: #4d698e;
}

.Button--primary {
  background: #4d698e;
  border-color: #4d698e;
  color: white;
}

.Button--primary:hover:not(:disabled) {
  background: #3d5875;
  border-color: #3d5875;
}

.Button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.Button--small {
  padding: 4px 10px;
  font-size: 12px;
}

.Button--danger {
  background: #fff1f0;
  border-color: #f0c5c0;
  color: #c0392b;
}

.Button--danger:hover:not(:disabled) {
  background: #fde2de;
  border-color: #e39a91;
}

.UsersPage-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
  padding: 20px 0;
}

.Pagination-info {
  font-size: 14px;
  color: #666;
}

.Modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.Modal-content {
  width: min(860px, calc(100vw - 24px));
  max-height: calc(100vh - 32px);
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 14px;
  box-shadow: 0 24px 64px rgba(19, 32, 51, 0.18);
  overflow: hidden;
}

.Modal-content--user {
  min-width: min(860px, calc(100vw - 24px));
}

.Modal-header,
.Modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px;
}

.Modal-header {
  border-bottom: 1px solid #e3e8ed;
}

.Modal-footer {
  justify-content: flex-end;
  border-top: 1px solid #e3e8ed;
}

.Modal-footer--split {
  justify-content: space-between;
}

.Modal-footerActions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.Modal-footerNote {
  color: #7f8c8d;
  font-size: 13px;
}

.Modal-header h3 {
  margin: 0;
  font-size: 18px;
}

.Modal-close {
  background: none;
  border: none;
  color: #999;
  font-size: 20px;
  cursor: pointer;
}

.Modal-close:hover {
  color: #333;
}

.Modal-body,
.Modal-loading {
  padding: 20px;
}

.Modal-body {
  overflow-y: auto;
  overflow-x: hidden;
  min-width: 0;
}

.Modal-loading {
  text-align: center;
  color: #999;
}

.Form-group {
  margin-bottom: 20px;
  min-width: 0;
}

.Form-group:last-child {
  margin-bottom: 0;
}

.Form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #333;
}

.FormRow {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.FormRow > * {
  min-width: 0;
}

.CheckboxField {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #44515e;
}

.CheckboxField--card {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #dbe2ea;
  border-radius: 8px;
  background: #fafbfc;
}

.GroupChecklist {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.Form-help {
  display: block;
  margin-top: 6px;
  color: #7f8c8d;
  font-size: 12px;
}

@media (max-width: 768px) {
  .UsersPage-search {
    max-width: none;
  }

  .UsersPage-pagination {
    flex-wrap: wrap;
    gap: 10px;
  }

  .FormRow {
    grid-template-columns: 1fr;
  }

  .Modal-content--user {
    min-width: 0;
  }

  .Modal-header,
  .Modal-footer,
  .Modal-body,
  .Modal-loading {
    padding: 16px;
  }

  .Modal-footer--split {
    flex-direction: column;
    align-items: stretch;
  }

  .Modal-footerActions {
    width: 100%;
    justify-content: flex-end;
  }
}

@media (max-width: 680px) {
  .UserTable {
    min-width: 0;
    border: 0;
    background: transparent;
  }

  .UserTable thead {
    display: none;
  }

  .UserTable tbody,
  .UserTable tr,
  .UserTable td {
    display: block;
    width: 100%;
  }

  .UserTable tbody tr {
    margin-bottom: 12px;
    padding: 14px;
    border-bottom: 0;
    border-radius: 14px;
    background: #fff;
    box-shadow: 0 10px 26px rgba(28, 46, 67, 0.06);
  }

  .UserTable tbody td {
    padding: 8px 0;
    border-bottom: 1px solid #eef2f6;
  }

  .UserTable tbody td:last-child {
    border-bottom: 0;
    padding-bottom: 0;
  }

  .UserTable tbody td::before {
    content: attr(data-label);
    display: block;
    margin-bottom: 6px;
    color: #7b8996;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .UserTable-loading,
  .UserTable-empty {
    display: block;
    padding: 28px 16px;
  }

  .UserTable tbody td[data-label='操作'] .Button {
    width: 100%;
    justify-content: center;
  }
}
</style>
