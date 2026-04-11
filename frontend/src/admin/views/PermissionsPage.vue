<template>
  <AdminPage
    className="PermissionsPage"
    icon="fas fa-key"
    title="权限管理"
    description="配置用户组和权限"
  >
    <div class="PermissionsPage-content">
      <!-- 用户组管理 -->
      <div class="PermissionsPage-groups">
        <div class="GroupBar">
          <div
            v-for="group in groups"
            :key="group.id"
            class="GroupBar-item"
            :style="{ backgroundColor: getGroupColor(group) }"
          >
            <span class="GroupBar-name">{{ group.name }}</span>
            <button
              @click="editGroup(group)"
              class="GroupBar-edit"
              title="编辑用户组"
            >
              <i class="fas fa-edit"></i>
            </button>
          </div>
          <button @click="createGroup" class="GroupBar-add">
            <i class="fas fa-plus"></i>
            添加用户组
          </button>
        </div>
      </div>

      <!-- 权限网格 -->
      <div class="PermissionsPage-grid">
        <table class="PermissionGrid">
          <thead>
            <tr>
              <th class="PermissionGrid-permission">权限</th>
              <th
                v-for="group in groups"
                :key="group.id"
                class="PermissionGrid-group"
                :style="{ color: getGroupColor(group) }"
              >
                {{ group.name }}
              </th>
            </tr>
          </thead>
          <tbody>
            <template v-for="section in permissionSections" :key="section.name">
              <tr>
                <td colspan="100%" class="PermissionGrid-section">
                  {{ section.label }}
                </td>
              </tr>
              <tr
                v-for="permission in section.permissions"
                :key="permission.name"
              >
                <td class="PermissionGrid-permission">
                  <i :class="permission.icon"></i>
                  {{ permission.label }}
                </td>
                <td
                  v-for="group in groups"
                  :key="group.id"
                  class="PermissionGrid-cell"
                >
                  <input
                    type="checkbox"
                    :checked="hasPermission(group.id, permission.name)"
                    @change="togglePermission(group.id, permission.name, $event)"
                  />
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <div class="PermissionsPage-actions">
        <button
          @click="savePermissions"
          class="Button Button--primary"
          :disabled="saving"
        >
          {{ saving ? '保存中...' : '保存权限' }}
        </button>
        <span v-if="saveSuccess" class="Form-success">✓ 保存成功</span>
      </div>

      <div v-if="showGroupModal" class="Modal" @click.self="closeGroupModal">
        <div class="Modal-content">
          <div class="Modal-header">
            <h3>{{ editingGroup ? '编辑用户组' : '创建用户组' }}</h3>
            <button @click="closeGroupModal" class="Modal-close">
              <i class="fas fa-times"></i>
            </button>
          </div>

          <div class="Modal-body">
            <div class="Form-group">
              <label>名称</label>
              <input v-model="groupForm.name" type="text" class="FormControl" placeholder="例如：Moderator" />
            </div>

            <div class="FormRow">
              <div class="Form-group">
                <label>单数名称</label>
                <input v-model="groupForm.name_singular" type="text" class="FormControl" />
              </div>
              <div class="Form-group">
                <label>复数名称</label>
                <input v-model="groupForm.name_plural" type="text" class="FormControl" />
              </div>
            </div>

            <div class="FormRow">
              <div class="Form-group">
                <label>颜色</label>
                <div class="ColorField">
                  <input v-model="groupForm.color" type="color" class="ColorField-picker" />
                  <input v-model="groupForm.color" type="text" class="FormControl" placeholder="#4d698e" />
                </div>
              </div>
              <div class="Form-group">
                <label>图标</label>
                <input v-model="groupForm.icon" type="text" class="FormControl" placeholder="例如：fas fa-shield-alt" />
              </div>
            </div>

            <label class="CheckboxField">
              <input v-model="groupForm.is_hidden" type="checkbox" />
              <span>隐藏用户组</span>
            </label>
          </div>

          <div class="Modal-footer">
            <button @click="closeGroupModal" class="Button Button--secondary">
              取消
            </button>
            <button @click="saveGroup" class="Button Button--primary" :disabled="groupSaving">
              {{ groupSaving ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </AdminPage>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import api from '../../api'

const groups = ref([])
const permissions = ref({})
const saving = ref(false)
const saveSuccess = ref(false)
const showGroupModal = ref(false)
const groupSaving = ref(false)
const editingGroup = ref(null)
const groupForm = ref(getEmptyGroupForm())

const permissionSections = [
  {
    name: 'view',
    label: '查看权限',
    permissions: [
      { name: 'viewForum', label: '查看论坛', icon: 'fas fa-eye' },
      { name: 'viewDiscussions', label: '查看讨论', icon: 'fas fa-comments' },
      { name: 'viewUserList', label: '查看用户列表', icon: 'fas fa-users' },
    ],
  },
  {
    name: 'start',
    label: '发起权限',
    permissions: [
      { name: 'startDiscussion', label: '发起讨论', icon: 'fas fa-edit' },
      { name: 'uploadFiles', label: '上传文件', icon: 'fas fa-upload' },
    ],
  },
  {
    name: 'reply',
    label: '回复权限',
    permissions: [
      { name: 'reply', label: '回复讨论', icon: 'fas fa-reply' },
      { name: 'editOwnPosts', label: '编辑自己的帖子', icon: 'fas fa-pencil-alt' },
      { name: 'deleteOwnPosts', label: '删除自己的帖子', icon: 'fas fa-times' },
    ],
  },
  {
    name: 'moderate',
    label: '管理权限',
    permissions: [
      { name: 'editPosts', label: '编辑帖子', icon: 'fas fa-pencil-alt' },
      { name: 'deletePosts', label: '删除帖子', icon: 'fas fa-trash' },
      { name: 'lockDiscussions', label: '锁定讨论', icon: 'fas fa-lock' },
      { name: 'stickyDiscussions', label: '置顶讨论', icon: 'fas fa-thumbtack' },
      { name: 'hideDiscussions', label: '隐藏讨论', icon: 'fas fa-eye-slash' },
      { name: 'viewHiddenGroups', label: '查看隐藏用户组', icon: 'fas fa-users-slash' },
    ],
  },
]

onMounted(async () => {
  await loadGroups()
  await loadPermissions()
})

async function loadGroups() {
  try {
    const data = await api.get('/admin/groups')
    groups.value = data
  } catch (error) {
    console.error('加载用户组失败:', error)
  }
}

async function loadPermissions() {
  try {
    const data = await api.get('/admin/permissions')
    permissions.value = data
  } catch (error) {
    console.error('加载权限失败:', error)
  }
}

function hasPermission(groupId, permissionName) {
  return permissions.value[groupId]?.includes(permissionName) || false
}

function getGroupColor(group) {
  return group?.color || '#6b7c93'
}

function togglePermission(groupId, permissionName, event) {
  if (!permissions.value[groupId]) {
    permissions.value[groupId] = []
  }

  if (event.target.checked) {
    if (!permissions.value[groupId].includes(permissionName)) {
      permissions.value[groupId].push(permissionName)
    }
  } else {
    permissions.value[groupId] = permissions.value[groupId].filter(
      (p) => p !== permissionName
    )
  }
}

async function savePermissions() {
  saving.value = true
  saveSuccess.value = false

  try {
    await api.post('/admin/permissions', permissions.value)
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  } catch (error) {
    console.error('保存权限失败:', error)
  } finally {
    saving.value = false
  }
}

function createGroup() {
  editingGroup.value = null
  groupForm.value = getEmptyGroupForm()
  showGroupModal.value = true
}

function editGroup(group) {
  editingGroup.value = group
  groupForm.value = {
    name: group.name || '',
    name_singular: group.name_singular || '',
    name_plural: group.name_plural || '',
    color: group.color || '#4d698e',
    icon: group.icon || '',
    is_hidden: Boolean(group.is_hidden),
  }
  showGroupModal.value = true
}

async function saveGroup() {
  if (!groupForm.value.name.trim()) {
    alert('请输入用户组名称')
    return
  }

  groupSaving.value = true
  try {
    const payload = {
      ...groupForm.value,
      name: groupForm.value.name.trim(),
      name_singular: (groupForm.value.name_singular || '').trim(),
      name_plural: (groupForm.value.name_plural || '').trim(),
      icon: (groupForm.value.icon || '').trim(),
    }

    if (editingGroup.value) {
      await api.put(`/admin/groups/${editingGroup.value.id}`, payload)
    } else {
      await api.post('/admin/groups', payload)
    }

    closeGroupModal()
    await loadGroups()
  } catch (error) {
    console.error('保存用户组失败:', error)
    alert('保存失败: ' + (error.response?.data?.error || error.message || '未知错误'))
  } finally {
    groupSaving.value = false
  }
}

function closeGroupModal() {
  showGroupModal.value = false
  editingGroup.value = null
  groupSaving.value = false
  groupForm.value = getEmptyGroupForm()
}

function getEmptyGroupForm() {
  return {
    name: '',
    name_singular: '',
    name_plural: '',
    color: '#4d698e',
    icon: '',
    is_hidden: false,
  }
}
</script>

<style scoped>
.PermissionsPage-content {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

/* 用户组栏 */
.GroupBar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 20px;
  background: #f5f8fa;
  border-radius: 3px;
}

.GroupBar-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 3px;
  color: white;
  font-size: 13px;
  font-weight: 500;
}

.GroupBar-name {
  flex: 1;
}

.GroupBar-edit {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  padding: 4px 8px;
  border-radius: 2px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.2s;
}

.GroupBar-edit:hover {
  background: rgba(255, 255, 255, 0.3);
}

.GroupBar-add {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: white;
  border: 1px dashed #ccc;
  border-radius: 3px;
  color: #666;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.GroupBar-add:hover {
  border-color: #4d698e;
  color: #4d698e;
}

/* 权限网格 */
.PermissionGrid {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
}

.PermissionGrid thead th {
  padding: 12px;
  background: #f5f8fa;
  border-bottom: 2px solid #e3e8ed;
  font-size: 13px;
  font-weight: 600;
  text-align: left;
}

.PermissionGrid-permission {
  width: 250px;
}

.PermissionGrid-group {
  text-align: center;
  min-width: 100px;
}

.PermissionGrid-section {
  padding: 12px;
  background: #f9fafb;
  font-weight: 600;
  font-size: 13px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-top: 1px solid #e3e8ed;
}

.PermissionGrid tbody tr:not(:has(.PermissionGrid-section)) {
  border-bottom: 1px solid #f0f0f0;
}

.PermissionGrid tbody tr:not(:has(.PermissionGrid-section)):hover {
  background: #fafbfc;
}

.PermissionGrid tbody td {
  padding: 12px;
}

.PermissionGrid-permission i {
  margin-right: 8px;
  color: #999;
  width: 16px;
  text-align: center;
}

.PermissionGrid-cell {
  text-align: center;
}

.PermissionGrid-cell input[type='checkbox'] {
  cursor: pointer;
  width: 16px;
  height: 16px;
}

.PermissionsPage-actions {
  display: flex;
  align-items: center;
  gap: 15px;
}

.Button {
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s;
}

.Button--primary {
  background: #4d698e;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 3px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.Button--primary:hover:not(:disabled) {
  background: #3d5875;
}

.Button--primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.Form-success {
  color: #27ae60;
  font-size: 14px;
  font-weight: 500;
}

.Button--secondary {
  background: #f5f8fa;
  border: 1px solid #ddd;
  padding: 10px 20px;
}

.Button--secondary:hover {
  background: #e8eef5;
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
  width: min(560px, calc(100vw - 32px));
  max-height: 90vh;
  overflow: auto;
  background: white;
  border-radius: 3px;
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

.Modal-body {
  padding: 20px;
}

.Form-group {
  margin-bottom: 20px;
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

.FormControl {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 14px;
}

.FormControl:focus {
  outline: none;
  border-color: #4d698e;
}

.FormRow {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.ColorField {
  display: flex;
  gap: 10px;
  align-items: center;
}

.ColorField-picker {
  width: 52px;
  height: 40px;
  padding: 0;
  border: 1px solid #ddd;
  border-radius: 3px;
  cursor: pointer;
}

.CheckboxField {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #44515e;
  font-size: 14px;
}

@media (max-width: 768px) {
  .FormRow {
    grid-template-columns: 1fr;
  }
}
</style>
