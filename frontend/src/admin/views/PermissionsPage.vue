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
            <i v-if="group.icon" :class="group.icon" class="GroupBar-icon"></i>
            <span class="GroupBar-name">{{ group.name }}</span>
            <button
              type="button"
              @click="editGroup(group)"
              class="GroupBar-edit"
              title="编辑用户组"
            >
              <i class="fas fa-edit"></i>
            </button>
          </div>
          <button type="button" @click="createGroup" class="GroupBar-add">
            <i class="fas fa-plus"></i>
            添加用户组
          </button>
        </div>
      </div>

      <!-- 权限网格 -->
      <div class="PermissionsPage-grid">
        <div class="PermissionGrid-wrap">
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

        <div class="PermissionMobileList">
          <section v-for="section in permissionSections" :key="`${section.name}-mobile`" class="PermissionMobileSection">
            <header class="PermissionMobileSection-header">
              <h4>{{ section.label }}</h4>
              <span>{{ section.permissions.length }} 项权限</span>
            </header>

            <article
              v-for="permission in section.permissions"
              :key="`${section.name}-${permission.name}-mobile`"
              class="PermissionMobileCard"
            >
              <div class="PermissionMobileCard-header">
                <div class="PermissionMobileCard-title">
                  <i :class="permission.icon"></i>
                  <strong>{{ permission.label }}</strong>
                </div>
              </div>

              <div class="PermissionMobileMatrix">
                <label
                  v-for="group in groups"
                  :key="`${permission.name}-${group.id}`"
                  class="PermissionMobileToggle"
                  :style="{ '--group-color': getGroupColor(group) }"
                >
                  <span class="PermissionMobileToggle-name">
                    <i v-if="group.icon" :class="group.icon"></i>
                    <span>{{ group.name }}</span>
                  </span>
                  <input
                    type="checkbox"
                    :checked="hasPermission(group.id, permission.name)"
                    @change="togglePermission(group.id, permission.name, $event)"
                  />
                </label>
              </div>
            </article>
          </section>
        </div>
      </div>

      <div class="PermissionsPage-actions">
        <button
          type="button"
          @click="savePermissions"
          class="Button Button--primary"
          :disabled="saving"
        >
          {{ saving ? '保存中...' : '保存权限' }}
        </button>
      </div>
      <AdminInlineMessage v-if="saveSuccess" tone="success">保存成功</AdminInlineMessage>
      <AdminInlineMessage v-if="errorMessage" tone="danger">{{ errorMessage }}</AdminInlineMessage>

      <div v-if="showGroupModal" class="Modal" @click.self="closeGroupModal">
        <div class="Modal-content Modal-content--group">
          <div class="Modal-header">
            <h3>{{ editingGroup ? '编辑用户组' : '创建用户组' }}</h3>
            <button type="button" @click="closeGroupModal" class="Modal-close">
              <i class="fas fa-times"></i>
            </button>
          </div>

          <div class="Modal-body">
            <div class="Form-group Form-group--groupName">
              <label for="group-name">名称</label>
              <input
                id="group-name"
                v-model="groupForm.name"
                name="group_name"
                type="text"
                class="FormControl"
                placeholder="例如：Moderator"
              />
            </div>

            <div class="FormRow">
              <div class="Form-group">
                <label for="group-icon">图标</label>
                <input
                  id="group-icon"
                  v-model="groupForm.icon"
                  name="group_icon"
                  type="text"
                  class="FormControl"
                  placeholder="例如：fas fa-shield-alt"
                />
              </div>
              <div class="Form-group">
                <label for="group-color-text">颜色</label>
                <div class="ColorField">
                  <input
                    id="group-color-picker"
                    v-model="groupForm.color"
                    name="group_color_picker"
                    type="color"
                    class="ColorField-picker"
                    aria-label="用户组颜色选择器"
                  />
                  <input
                    id="group-color-text"
                    v-model="groupForm.color"
                    name="group_color"
                    type="text"
                    class="FormControl"
                    placeholder="#4d698e"
                  />
                </div>
              </div>
            </div>

            <label class="CheckboxField CheckboxField--toggle GroupHiddenToggle">
              <input
                v-model="groupForm.is_hidden"
                name="group_is_hidden"
                type="checkbox"
              />
              <span>隐藏用户组</span>
            </label>
          </div>

          <div class="Modal-footer Modal-footer--split">
            <button
              type="button"
              v-if="editingGroup && canDeleteGroup(editingGroup)"
              @click="deleteGroup"
              class="Button Button--danger"
              :disabled="groupSaving || deletingGroup"
            >
              {{ deletingGroup ? '删除中...' : '删除用户组' }}
            </button>
            <span v-else-if="editingGroup" class="Modal-footerNote">系统默认用户组不允许删除</span>
            <span v-else class="Modal-footerNote"></span>
            <div class="Modal-footerActions">
              <button type="button" @click="closeGroupModal" class="Button Button--secondary">
                取消
              </button>
              <button type="button" @click="saveGroup" class="Button Button--primary" :disabled="groupSaving || deletingGroup">
                {{ groupSaving ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AdminPage>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AdminInlineMessage from '../components/AdminInlineMessage.vue'
import AdminPage from '../components/AdminPage.vue'
import { useAdminSaveFeedback } from '../composables/useAdminSaveFeedback'
import api from '../../api'
import { useModalStore } from '../../stores/modal'

const groups = ref([])
const permissions = ref({})
const saving = ref(false)
const errorMessage = ref('')
const showGroupModal = ref(false)
const groupSaving = ref(false)
const deletingGroup = ref(false)
const editingGroup = ref(null)
const groupForm = ref(getEmptyGroupForm())
const modalStore = useModalStore()
const { saveSuccess, resetSaveFeedback, showSaveSuccess } = useAdminSaveFeedback()

const permissionSections = [
  {
    name: 'view',
    label: '查看权限',
    permissions: [
      { name: 'viewForum', label: '查看论坛', icon: 'fas fa-eye' },
      { name: 'viewUserList', label: '查看用户列表', icon: 'fas fa-users' },
      { name: 'searchUsers', label: '搜索用户', icon: 'fas fa-search' },
    ],
  },
  {
    name: 'start',
    label: '发帖权限',
    permissions: [
      { name: 'startDiscussion', label: '发起讨论', icon: 'fas fa-edit' },
      { name: 'startDiscussionWithoutApproval', label: '发起讨论免审核', icon: 'fas fa-user-check' },
    ],
  },
  {
    name: 'reply',
    label: '回复权限',
    permissions: [
      { name: 'discussion.reply', label: '回复讨论', icon: 'fas fa-reply' },
      { name: 'replyWithoutApproval', label: '回复免审核', icon: 'fas fa-user-check' },
      { name: 'discussion.editOwn', label: '编辑自己的帖子', icon: 'fas fa-pencil-alt' },
      { name: 'discussion.deleteOwn', label: '删除自己的帖子', icon: 'fas fa-times' },
    ],
  },
  {
    name: 'moderate',
    label: '内容管理',
    permissions: [
      { name: 'discussion.edit', label: '编辑任意帖子', icon: 'fas fa-pencil-alt' },
      { name: 'discussion.delete', label: '删除任意帖子', icon: 'fas fa-trash' },
      { name: 'discussion.hide', label: '隐藏内容', icon: 'fas fa-eye-slash' },
      { name: 'discussion.rename', label: '重命名讨论', icon: 'fas fa-heading' },
      { name: 'discussion.lock', label: '锁定讨论', icon: 'fas fa-lock' },
      { name: 'discussion.sticky', label: '置顶讨论', icon: 'fas fa-thumbtack' },
    ],
  },
  {
    name: 'user',
    label: '用户管理',
    permissions: [
      { name: 'user.edit', label: '编辑用户资料', icon: 'fas fa-user-edit' },
      { name: 'user.suspend', label: '封禁用户', icon: 'fas fa-user-slash' },
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
    errorMessage.value = ''
  } catch (error) {
    console.error('加载用户组失败:', error)
    errorMessage.value = '加载用户组失败'
  }
}

async function loadPermissions() {
  try {
    const data = await api.get('/admin/permissions')
    permissions.value = data
    errorMessage.value = ''
  } catch (error) {
    console.error('加载权限失败:', error)
    errorMessage.value = '加载权限失败'
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
  const confirmed = await modalStore.confirm({
    title: '保存权限配置',
    message: '权限变更会立即影响用户操作能力。确定保存当前配置吗？',
    confirmText: '保存',
    cancelText: '取消',
    tone: 'warning'
  })
  if (!confirmed) {
    return
  }

  saving.value = true
  resetSaveFeedback()
  errorMessage.value = ''

  try {
    await api.post('/admin/permissions', permissions.value)
    showSaveSuccess()
  } catch (error) {
    console.error('保存权限失败:', error)
    errorMessage.value = error.response?.data?.error || '保存权限失败'
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
    icon: group.icon || '',
    color: group.color || '#4d698e',
    is_hidden: Boolean(group.is_hidden),
  }
  showGroupModal.value = true
}

async function saveGroup() {
  if (!groupForm.value.name.trim()) {
    await modalStore.alert({
      title: '信息不完整',
      message: '请输入用户组名称',
      tone: 'warning'
    })
    return
  }

  groupSaving.value = true
  try {
    const payload = {
      ...groupForm.value,
      name: groupForm.value.name.trim(),
    }

    if (editingGroup.value) {
      await api.put(`/admin/groups/${editingGroup.value.id}`, payload)
    } else {
      await api.post('/admin/groups', payload)
    }

    closeGroupModal()
    await loadGroups()
    await loadPermissions()
  } catch (error) {
    console.error('保存用户组失败:', error)
    await modalStore.alert({
      title: '保存失败',
      message: error.response?.data?.error || error.message || '未知错误',
      tone: 'danger'
    })
  } finally {
    groupSaving.value = false
  }
}

function canDeleteGroup(group) {
  return group && !group.is_system
}

async function deleteGroup() {
  if (!editingGroup.value || !canDeleteGroup(editingGroup.value)) {
    return
  }

  const confirmed = await modalStore.confirm({
    title: '删除用户组',
    message: `确定删除用户组“${editingGroup.value.name}”吗？现有成员会失去该用户组权限。`,
    confirmText: '删除',
    cancelText: '取消',
    tone: 'danger'
  })
  if (!confirmed) {
    return
  }

  deletingGroup.value = true
  try {
    const deletedGroupName = editingGroup.value.name
    await api.delete(`/admin/groups/${editingGroup.value.id}`)
    closeGroupModal()
    await loadGroups()
    await loadPermissions()
    await modalStore.alert({
      title: '用户组已删除',
      message: `用户组“${deletedGroupName}”已删除。`,
      tone: 'success'
    })
  } catch (error) {
    console.error('删除用户组失败:', error)
    await modalStore.alert({
      title: '删除失败',
      message: error.response?.data?.error || error.message || '未知错误',
      tone: 'danger'
    })
  } finally {
    deletingGroup.value = false
  }
}

function closeGroupModal() {
  showGroupModal.value = false
  editingGroup.value = null
  groupSaving.value = false
  deletingGroup.value = false
  groupForm.value = getEmptyGroupForm()
}

function getEmptyGroupForm() {
  return {
    name: '',
    icon: '',
    color: '#4d698e',
    is_hidden: false,
  }
}
</script>

<style scoped>
.PermissionsPage-content {
  display: flex;
  flex-direction: column;
  gap: 30px;
  min-width: 0;
}

.GroupBar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 20px;
  background: var(--forum-bg-subtle);
  border-radius: var(--forum-radius-md);
}

.GroupBar-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--forum-radius-sm);
  color: var(--forum-text-inverse);
  font-size: var(--forum-font-size-sm);
  font-weight: 600;
}

.GroupBar-name {
  flex: 1;
}

.GroupBar-icon {
  width: 14px;
  text-align: center;
}

.GroupBar-edit {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: var(--forum-text-inverse);
  padding: 4px 8px;
  border-radius: 2px;
  cursor: pointer;
  font-size: var(--forum-font-size-xs);
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
  background: var(--forum-bg-elevated);
  border: 1px dashed var(--forum-border-strong);
  border-radius: var(--forum-radius-sm);
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
  cursor: pointer;
  transition: all 0.2s;
}

.GroupBar-add:hover {
  border-color: var(--forum-primary-color);
  color: var(--forum-primary-color);
}

.PermissionsPage-grid {
  min-width: 0;
}

.PermissionMobileList {
  display: none;
}

.PermissionGrid-wrap {
  width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  border: 1px solid var(--forum-border-color);
  border-radius: 12px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.PermissionGrid-wrap::-webkit-scrollbar {
  height: 10px;
}

.PermissionGrid-wrap::-webkit-scrollbar-thumb {
  background: var(--forum-border-strong);
  border-radius: var(--forum-radius-pill);
}

.PermissionGrid {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
  background: var(--forum-bg-elevated);
}

.PermissionGrid thead th {
  padding: 12px;
  background: var(--forum-bg-subtle);
  border-bottom: 2px solid var(--forum-border-color);
  font-size: var(--forum-font-size-sm);
  font-weight: 600;
  text-align: left;
  color: var(--forum-text-muted);
}

.PermissionGrid-permission {
  width: 260px;
  min-width: 260px;
}

.PermissionGrid-group {
  text-align: center;
  min-width: 100px;
}

.PermissionGrid-section {
  padding: 12px;
  background: var(--forum-bg-elevated-strong);
  font-weight: 600;
  font-size: var(--forum-font-size-sm);
  color: var(--forum-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-top: 1px solid var(--forum-border-color);
}

.PermissionGrid tbody tr:not(:has(.PermissionGrid-section)) {
  border-bottom: 1px solid var(--forum-border-soft);
}

.PermissionGrid tbody tr:not(:has(.PermissionGrid-section)):hover {
  background: var(--forum-bg-elevated-strong);
}

.PermissionGrid tbody td {
  padding: 12px;
}

.PermissionGrid-permission i {
  margin-right: 8px;
  color: var(--forum-text-soft);
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

.Modal-content--group {
  width: min(680px, calc(100vw - 24px));
  min-width: min(680px, calc(100vw - 24px));
}

.Form-group--groupName {
  max-width: 360px;
}

.ColorField {
  display: flex;
  gap: 10px;
  align-items: center;
  min-width: 0;
}

.ColorField-picker {
  flex: 0 0 52px;
  width: 52px;
  height: 40px;
  padding: 0;
  border: 1px solid var(--forum-border-strong);
  border-radius: var(--forum-radius-sm);
  cursor: pointer;
}

.ColorField .FormControl {
  flex: 1 1 auto;
  min-width: 0;
}

.GroupHiddenToggle {
  width: fit-content;
  min-width: 160px;
  justify-content: flex-start;
}

.GroupHiddenToggle span {
  white-space: nowrap;
}

@media (max-width: 768px) {
  .GroupBar {
    padding: 14px;
    border-radius: 16px;
  }

  .GroupBar-item,
  .GroupBar-add {
    width: 100%;
    justify-content: space-between;
    min-height: 44px;
    border-radius: 12px;
  }

  .Form-group--groupName {
    max-width: none;
  }

  .Modal-content--group {
    min-width: 0;
  }

  .GroupHiddenToggle {
    width: 100%;
  }

  .PermissionGrid-wrap {
    display: none;
  }

  .PermissionMobileList {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .PermissionMobileSection {
    padding: 14px;
    border: 1px solid var(--forum-border-color);
    border-radius: 16px;
    background: var(--forum-bg-elevated);
    box-shadow: var(--forum-shadow-sm);
  }

  .PermissionMobileSection-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }

  .PermissionMobileSection-header h4 {
    margin: 0;
    font-size: 15px;
    color: var(--forum-text-color);
  }

  .PermissionMobileSection-header span {
    color: var(--forum-text-soft);
    font-size: var(--forum-font-size-xs);
  }

  .PermissionMobileCard {
    padding: 12px;
    border-radius: 14px;
    background: var(--forum-bg-elevated-strong);
  }

  .PermissionMobileCard + .PermissionMobileCard {
    margin-top: 10px;
  }

  .PermissionMobileCard-header {
    margin-bottom: 10px;
  }

  .PermissionMobileCard-title {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--forum-text-muted);
  }

  .PermissionMobileCard-title i {
    width: 16px;
    color: var(--forum-text-soft);
    text-align: center;
  }

  .PermissionMobileMatrix {
    display: grid;
    gap: 8px;
  }

  .PermissionMobileToggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    min-height: 44px;
    padding: 0 12px;
    border: 1px solid color-mix(in srgb, var(--group-color) 18%, #d8e1ea);
    border-radius: 12px;
    background: var(--forum-bg-elevated);
  }

  .PermissionMobileToggle-name {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    color: var(--forum-text-muted);
    font-size: var(--forum-font-size-sm);
    font-weight: 600;
  }

  .PermissionMobileToggle-name i {
    color: var(--group-color);
  }

  .PermissionMobileToggle input[type='checkbox'] {
    width: 18px;
    height: 18px;
    margin: 0;
  }

  .PermissionsPage-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .PermissionsPage-actions .Button--primary {
    width: 100%;
    justify-content: center;
  }
}
</style>
