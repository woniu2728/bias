<template>
  <AdminPage
    class-name="PermissionsPage"
    icon="fas fa-key"
    :title="permissionsCopy?.pageTitle || '权限管理'"
    :description="permissionsCopy?.pageDescription || '配置用户组和权限，并检查权限来源与依赖关系'"
  >
    <div class="PermissionsPage-content">
      <AdminInlineMessage v-if="permissionMetaSummary" tone="neutral">
        {{ permissionsCopy?.metaSummaryText?.(permissionMetaSummary) || `当前共注册 ${permissionMetaSummary.permissionCount} 项权限，来自 ${permissionMetaSummary.moduleCount} 个模块。保存时会自动补齐依赖权限，避免出现“子权限已勾选但前置权限缺失”的配置。` }}
      </AdminInlineMessage>

      <section v-if="permissionScopes.length" class="PermissionScopes">
        <article
          v-for="scope in permissionScopes"
          :key="scope.key"
          class="PermissionScopeCard"
        >
          <div class="PermissionScopeCard-main">
            <div class="PermissionScopeCard-title">
              <i v-if="scope.icon" :class="scope.icon"></i>
              <strong>{{ scope.label }}</strong>
            </div>
            <p v-if="scope.description">{{ scope.description }}</p>
          </div>
          <RouterLink
            v-if="scope.to"
            class="Button Button--secondary PermissionScopeCard-action"
            :to="scope.to"
          >
            {{ scope.actionLabel || '配置' }}
          </RouterLink>
        </article>
      </section>

      <!-- 用户组管理 -->
      <div class="PermissionsPage-groups">
        <div class="GroupBar">
          <div
            v-for="group in groups"
            :key="group.id"
            class="GroupBar-item"
            :class="{ 'is-active': activeGroup?.id === group.id }"
            :style="{ '--group-color': getGroupColor(group) }"
          >
            <button
              type="button"
              class="GroupBar-select"
              @click="setActiveGroup(group.id)"
            >
              <span class="GroupBar-iconWrap">
                <i v-if="group.icon" :class="group.icon" class="GroupBar-icon"></i>
              </span>
              <span class="GroupBar-text">
                <span class="GroupBar-name">{{ group.name }}</span>
                <span class="GroupBar-state">
                  {{ activeGroup?.id === group.id ? (permissionsCopy?.activeGroupLabel || '当前编辑') : (permissionsCopy?.switchGroupLabel || '切换查看') }}
                </span>
              </span>
            </button>
            <button
              type="button"
              class="GroupBar-edit"
              :title="permissionsCopy?.editGroupTitle || '编辑用户组'"
              @click="editGroup(group)"
            >
              <i class="fas fa-edit"></i>
            </button>
          </div>
          <button type="button" class="GroupBar-add" @click="createGroup">
            <i class="fas fa-plus"></i>
            {{ permissionsCopy?.addGroupLabel || '添加用户组' }}
          </button>
        </div>
      </div>

      <!-- 权限网格 -->
      <div class="PermissionsPage-grid">
        <div class="PermissionGrid-wrap">
          <table class="PermissionGrid">
            <thead>
              <tr>
                <th class="PermissionGrid-permission">{{ permissionsCopy?.permissionHeaderLabel || '权限' }}</th>
                <th class="PermissionGrid-group PermissionGrid-group--active">
                  <div v-if="activeGroup" class="PermissionGrid-groupHeader" :style="{ '--group-color': getGroupColor(activeGroup) }">
                    <span class="PermissionGrid-groupBadge">
                      <i v-if="activeGroup.icon" :class="activeGroup.icon"></i>
                    </span>
                    <span class="PermissionGrid-groupName">{{ activeGroup.name }}</span>
                  </div>
                  <span v-else>{{ permissionsCopy?.noGroupSelectedText || '未选择用户组' }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <template v-for="section in permissionSections" :key="section.name">
                <tr>
                  <td colspan="2" class="PermissionGrid-section">
                    {{ section.label }}
                  </td>
                </tr>
                <tr
                  v-for="permission in section.permissions"
                  :key="permission.name"
                  class="PermissionGrid-row"
                >
                  <td class="PermissionGrid-permission">
                    <div class="PermissionCell-main">
                      <div class="PermissionCell-title">
                        <i :class="permission.icon"></i>
                        <span>{{ permission.label }}</span>
                      </div>
                      <p v-if="permission.description" class="PermissionCell-description">{{ permission.description }}</p>
                    </div>
                  </td>
                  <td class="PermissionGrid-cell PermissionGrid-cell--single">
                    <input
                      v-if="activeGroup"
                      type="checkbox"
                      :checked="hasPermission(activeGroup.id, permission.name)"
                      @change="togglePermission(activeGroup.id, permission.name, $event)"
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
              <span>{{ permissionsCopy?.mobilePermissionCountText?.(section.permissions.length) || `${section.permissions.length} 项权限` }}</span>
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
              <p v-if="permission.description" class="PermissionMobileCard-description">{{ permission.description }}</p>

              <div v-if="activeGroup" class="PermissionMobileMatrix">
                <label class="PermissionMobileToggle" :style="{ '--group-color': getGroupColor(activeGroup) }">
                  <span class="PermissionMobileToggle-name">
                    <i v-if="activeGroup.icon" :class="activeGroup.icon"></i>
                    <span>{{ activeGroup.name }}</span>
                  </span>
                  <input
                    type="checkbox"
                    :checked="hasPermission(activeGroup.id, permission.name)"
                    @change="togglePermission(activeGroup.id, permission.name, $event)"
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
          class="Button Button--primary"
          :disabled="saving"
          @click="savePermissions"
        >
          {{ saving ? (permissionsCopy?.savingPermissionsLabel || '保存中...') : (permissionsCopy?.savePermissionsLabel || '保存权限') }}
        </button>
      </div>
      <AdminInlineMessage v-if="saveSuccess" tone="success">{{ permissionsCopy?.saveSuccessText || '保存成功' }}</AdminInlineMessage>
      <AdminInlineMessage v-if="errorMessage" tone="danger">{{ errorMessage }}</AdminInlineMessage>

      <div v-if="showGroupModal" class="Modal" @click.self="closeGroupModal">
        <div class="Modal-content Modal-content--group">
          <div class="Modal-header Modal-header--group">
            <h3>{{ editingGroup ? (permissionsCopy?.updateGroupTitle || '编辑用户组') : (permissionsCopy?.createGroupTitle || '创建用户组') }}</h3>
            <button type="button" class="Modal-close" @click="closeGroupModal">
              <i class="fas fa-times"></i>
            </button>
          </div>

          <div class="Modal-body Modal-body--group">
            <div class="Form-group Form-group--groupCompact">
              <label for="group-name" class="Form-labelStrong">{{ permissionsCopy?.groupNameLabel || '名称' }}</label>
              <input
                id="group-name"
                v-model="groupForm.name"
                name="group_name"
                type="text"
                class="FormControl"
                :placeholder="permissionsCopy?.groupNamePlaceholder || '例如：Moderator'"
              />
            </div>

            <div class="Form-group Form-group--groupCompact">
              <label for="group-color-text" class="Form-labelStrong">{{ permissionsCopy?.groupColorLabel || '颜色' }}</label>
              <AdminColorField
                v-model="groupForm.color"
                input-id="group-color-text"
                picker-id="group-color-picker"
                name="group_color"
                picker-name="group_color_picker"
                :aria-label="permissionsCopy?.groupColorPickerAriaLabel || '用户组颜色选择器'"
                :placeholder="permissionsCopy?.groupColorPlaceholder || '#4d698e'"
              />
            </div>

            <div class="Form-group Form-group--groupCompact">
              <label for="group-icon" class="Form-labelStrong">{{ permissionsCopy?.groupIconLabel || '图标' }}</label>
              <p class="GroupModal-help">
                输入 Font Awesome 图标类名，例如：`fas fa-bolt`
                <a
                  class="GroupModal-helpLink"
                  href="https://fontawesome.com/icons?o=r&m=free"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  查看图标
                </a>
              </p>
              <input
                id="group-icon"
                v-model="groupForm.icon"
                name="group_icon"
                type="text"
                class="FormControl"
                :placeholder="permissionsCopy?.groupIconPlaceholder || '例如：fas fa-shield-alt'"
              />
            </div>

            <div class="GroupModal-toggleRow">
              <label class="CheckboxField GroupHiddenToggle GroupHiddenToggle--switch">
                <input
                  id="group-is-hidden"
                  v-model="groupForm.is_hidden"
                  name="group_is_hidden"
                  type="checkbox"
                />
                <span class="GroupHiddenToggle-switch" aria-hidden="true"></span>
                <span>{{ permissionsCopy?.groupHiddenLabel || '隐藏用户组' }}</span>
              </label>
            </div>
          </div>

          <div class="GroupModal-actions">
            <button
              v-if="editingGroup && canDeleteGroup(editingGroup)"
              type="button"
              class="Button Button--danger"
              :disabled="groupSaving || deletingGroup"
              @click="deleteGroup"
            >
              {{ deletingGroup ? (permissionsCopy?.deletingGroupLabel || '删除中...') : (permissionsCopy?.deleteGroupLabel || '删除用户组') }}
            </button>
            <span v-else-if="editingGroup" class="Modal-footerNote">{{ permissionsCopy?.deleteGroupBlockedText || '系统默认用户组不允许删除' }}</span>
            <button type="button" class="Button Button--primary GroupModal-saveButton" :disabled="groupSaving || deletingGroup" @click="saveGroup">
              {{ groupSaving ? (permissionsCopy?.savingGroupLabel || '保存中...') : (permissionsCopy?.saveGroupLabel || '保存') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import AdminColorField from '../components/AdminColorField.vue'
import AdminInlineMessage from '../components/AdminInlineMessage.vue'
import AdminPage from '../components/AdminPage.vue'
import { useAdminSaveFeedback } from '../composables/useAdminSaveFeedback'
import api from '../../api'
import { useModalStore } from '../../stores/modal'
import {
  getAdminPermissionsPageCopy,
} from '../registry/pageCopies.js'
import {
  getAdminPermissionsPageConfig,
} from '../registry/pageConfigs.js'
import {
  getAdminPermissionsPageActionMeta,
} from '../registry/pageActionMeta.js'
import {
  getAdminPermissionScopes,
} from '../registry/permissionScopes.js'

const groups = ref([])
const activeGroupId = ref(null)
const permissions = ref({})
const permissionSections = ref([])
const permissionModules = ref([])
const saving = ref(false)
const errorMessage = ref('')
const showGroupModal = ref(false)
const groupSaving = ref(false)
const deletingGroup = ref(false)
const editingGroup = ref(null)
const modalStore = useModalStore()
const { saveSuccess, resetSaveFeedback, showSaveSuccess } = useAdminSaveFeedback()
const permissionsCopy = computed(() => getAdminPermissionsPageCopy())
const permissionsConfig = computed(() => getAdminPermissionsPageConfig())
const permissionsActionMeta = computed(() => getAdminPermissionsPageActionMeta())
const permissionScopes = computed(() => getAdminPermissionScopes({
  surface: 'admin-permissions',
  groups: groups.value,
  permissionSections: permissionSections.value,
}))
const groupForm = ref(getEmptyGroupForm())
const activeGroup = computed(() => {
  if (!groups.value.length) {
    return null
  }
  return groups.value.find(group => group.id === activeGroupId.value) || groups.value[0]
})

onMounted(async () => {
  await loadGroups()
  await loadPermissionMeta()
  await loadPermissions()
})

async function loadGroups() {
  try {
    const data = await api.get('/admin/groups')
    groups.value = data
    syncActiveGroup()
    errorMessage.value = ''
  } catch (error) {
    console.error('加载用户组失败:', error)
    errorMessage.value = permissionsActionMeta.value?.loadGroupsFailedMessage || '加载用户组失败'
  }
}

function syncActiveGroup() {
  if (!groups.value.length) {
    activeGroupId.value = null
    return
  }

  const exists = groups.value.some(group => group.id === activeGroupId.value)
  if (!exists) {
    activeGroupId.value = groups.value[0].id
  }
}

function setActiveGroup(groupId) {
  activeGroupId.value = groupId
}

async function loadPermissions() {
  try {
    const data = await api.get('/admin/permissions')
    permissions.value = data
    errorMessage.value = ''
  } catch (error) {
    console.error('加载权限失败:', error)
    errorMessage.value = permissionsActionMeta.value?.loadPermissionsFailedMessage || '加载权限失败'
  }
}

async function loadPermissionMeta() {
  try {
    const data = await api.get('/admin/permissions/meta')
    permissionSections.value = data.sections || []
    permissionModules.value = data.modules || []
    errorMessage.value = ''
  } catch (error) {
    console.error('加载权限定义失败:', error)
    errorMessage.value = permissionsActionMeta.value?.loadPermissionMetaFailedMessage || '加载权限定义失败'
  }
}

const permissionMetaSummary = computed(() => {
  const permissionCount = permissionSections.value.reduce((total, section) => {
    return total + (section.permissions?.length || 0)
  }, 0)
  return {
    permissionCount,
    moduleCount: permissionModules.value.length,
  }
})

const moduleNameMap = computed(() => {
  return Object.fromEntries(permissionModules.value.map(module => [module.id, module.name]))
})

function hasPermission(groupId, permissionName) {
  return permissions.value[groupId]?.includes(permissionName) || false
}

function getGroupColor(group) {
  return group?.color || permissionsConfig.value?.groupColorFallback || '#6b7c93'
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

function resolveModuleName(moduleId) {
  return moduleNameMap.value[moduleId] || moduleId || permissionsCopy.value?.unknownModuleLabel || '未知模块'
}

async function savePermissions() {
  const confirmed = await modalStore.confirm({
    title: permissionsActionMeta.value?.savePermissionsConfirmTitle || '保存权限配置',
    message: permissionsActionMeta.value?.savePermissionsConfirmMessage || '权限变更会立即影响用户操作能力。确定保存当前配置吗？',
    confirmText: permissionsActionMeta.value?.savePermissionsConfirmText || '保存',
    cancelText: permissionsActionMeta.value?.savePermissionsCancelText || '取消',
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
    errorMessage.value = error.response?.data?.error || permissionsActionMeta.value?.savePermissionsFailedMessage || '保存权限失败'
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
    color: group.color || permissionsConfig.value?.groupColorDefault || '#4d698e',
    is_hidden: Boolean(group.is_hidden),
  }
  showGroupModal.value = true
}

async function saveGroup() {
  if (!groupForm.value.name.trim()) {
    await modalStore.alert({
      title: permissionsActionMeta.value?.groupIncompleteTitle || '信息不完整',
      message: permissionsActionMeta.value?.groupIncompleteMessage || '请输入用户组名称',
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
      title: permissionsActionMeta.value?.saveGroupFailedTitle || '保存失败',
      message: error.response?.data?.error || error.message || permissionsActionMeta.value?.saveGroupFailedMessage || '未知错误',
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
    title: permissionsActionMeta.value?.deleteGroupConfirmTitle || '删除用户组',
    message: permissionsActionMeta.value?.deleteGroupConfirmMessage?.(editingGroup.value.name) || `确定删除用户组“${editingGroup.value.name}”吗？现有成员会失去该用户组权限。`,
    confirmText: permissionsActionMeta.value?.deleteGroupConfirmText || '删除',
    cancelText: permissionsActionMeta.value?.deleteGroupCancelText || '取消',
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
      title: permissionsActionMeta.value?.deleteGroupSuccessTitle || '用户组已删除',
      message: permissionsActionMeta.value?.deleteGroupSuccessMessage?.(deletedGroupName) || `用户组“${deletedGroupName}”已删除。`,
      tone: 'success'
    })
  } catch (error) {
    console.error('删除用户组失败:', error)
    await modalStore.alert({
      title: permissionsActionMeta.value?.deleteGroupFailedTitle || '删除失败',
      message: error.response?.data?.error || error.message || permissionsActionMeta.value?.deleteGroupFailedMessage || '未知错误',
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
    color: permissionsConfig.value?.groupColorDefault || '#4d698e',
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
  gap: 12px;
  padding: 20px;
  background: var(--forum-bg-subtle);
  border-radius: var(--forum-radius-md);
}

.GroupBar-item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--group-color) 18%, var(--forum-border-color));
  border-radius: 14px;
  background: var(--forum-bg-elevated);
  color: var(--forum-text-color);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.GroupBar-item.is-active {
  border-color: color-mix(in srgb, var(--group-color) 48%, var(--forum-border-color));
  background: color-mix(in srgb, var(--group-color) 10%, var(--forum-bg-elevated));
  box-shadow: 0 10px 24px color-mix(in srgb, var(--group-color) 16%, transparent);
}

.GroupBar-select {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1 1 auto;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.GroupBar-iconWrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--group-color) 14%, white);
  color: var(--group-color);
  flex: 0 0 auto;
}

.GroupBar-name {
  display: block;
  color: var(--forum-text-color);
  font-size: var(--forum-font-size-sm);
  font-weight: 700;
  line-height: 1.2;
}

.GroupBar-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.GroupBar-state {
  color: var(--forum-text-soft);
  font-size: 12px;
  line-height: 1.2;
}

.GroupBar-icon {
  width: 14px;
  text-align: center;
}

.GroupBar-edit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  background: color-mix(in srgb, var(--group-color) 10%, var(--forum-bg-elevated));
  border: 1px solid color-mix(in srgb, var(--group-color) 20%, var(--forum-border-color));
  color: var(--group-color);
  padding: 0;
  border-radius: 10px;
  cursor: pointer;
  font-size: var(--forum-font-size-xs);
  transition: background 0.2s ease, border-color 0.2s ease;
}

.GroupBar-edit:hover {
  background: color-mix(in srgb, var(--group-color) 16%, var(--forum-bg-elevated));
  border-color: color-mix(in srgb, var(--group-color) 34%, var(--forum-border-color));
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

.PermissionScopes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.PermissionScopeCard {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
  background: var(--forum-bg-elevated);
}

.PermissionScopeCard-main {
  min-width: 0;
}

.PermissionScopeCard-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--forum-text-color);
}

.PermissionScopeCard-title i {
  color: var(--forum-primary-color);
}

.PermissionScopeCard p {
  margin: 6px 0 0;
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
  line-height: 1.5;
}

.PermissionScopeCard-action {
  flex-shrink: 0;
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
  padding: 12px 16px;
  background: var(--forum-bg-subtle);
  border-bottom: 1px solid var(--forum-border-color);
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
  min-width: 164px;
  width: 164px;
}

.PermissionGrid-group--active {
  text-align: center;
}

.PermissionGrid-groupHeader {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--forum-text-color);
}

.PermissionGrid-groupBadge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--group-color) 14%, white);
  color: var(--group-color);
}

.PermissionGrid-groupName {
  font-weight: 700;
}

.PermissionGrid-section {
  padding: 10px 16px;
  background: color-mix(in srgb, var(--forum-bg-subtle) 82%, white);
  font-weight: 600;
  font-size: 12px;
  color: var(--forum-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  border-top: 1px solid var(--forum-border-color);
}

.PermissionGrid tbody tr:not(:has(.PermissionGrid-section)) {
  border-bottom: 1px solid var(--forum-border-soft);
}

.PermissionGrid tbody tr:not(:has(.PermissionGrid-section)):hover {
  background: color-mix(in srgb, var(--forum-primary-color) 3%, var(--forum-bg-elevated));
}

.PermissionGrid tbody td {
  padding: 14px 16px;
}

.PermissionGrid-permission i {
  color: var(--forum-text-soft);
  width: 15px;
  text-align: center;
}

.PermissionCell-main {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.PermissionCell-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--forum-text-color);
  font-size: 15px;
  font-weight: 600;
}

.PermissionCell-description,
.PermissionCell-dependencies {
  margin: 0;
  color: var(--forum-text-soft);
  font-size: 12px;
  line-height: 1.45;
}

.PermissionGrid-cell {
  text-align: center;
  vertical-align: middle;
}

.PermissionGrid-cell--single {
  width: 164px;
  min-width: 164px;
}

.PermissionGrid-cell input[type='checkbox'] {
  cursor: pointer;
  width: 18px;
  height: 18px;
}

.PermissionsPage-actions {
  display: flex;
  align-items: center;
  gap: 15px;
}

#admin-app .Modal-content.Modal-content--group {
  width: min(470px, calc(100vw - 24px));
  min-width: min(470px, calc(100vw - 24px));
  max-height: calc(100dvh - 40px);
  background: #eef3fa;
  border-radius: 8px;
  box-shadow: 0 22px 54px rgba(15, 23, 42, 0.22);
}

#admin-app .Modal-content.Modal-content--group .Modal-header,
#admin-app .Modal-content.Modal-content--group .Modal-body {
  padding: 26px 38px;
}

#admin-app .Modal-content.Modal-content--group .Modal-body {
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.Form-group--groupCompact {
  margin-bottom: 0;
}

.Form-labelStrong {
  display: inline-block;
  margin-bottom: 10px;
  color: var(--forum-text-color);
  font-size: 14px;
  font-weight: 700;
}

.Modal-header--group h3 {
  font-size: 16px;
  font-weight: 500;
}

.Modal-header--group {
  position: relative;
  justify-content: center;
}

.Modal-header--group .Modal-close {
  position: absolute;
  top: 22px;
  right: 24px;
  width: 28px;
  height: 28px;
  font-size: 16px;
}

.Modal-body--group {
  display: flex;
  flex-direction: column;
  gap: 26px;
  border-top: 1px solid #d6deea;
}

.GroupModal-help {
  margin: 0 0 10px;
  color: var(--forum-text-soft);
  font-size: 12px;
  line-height: 1.5;
}

.GroupModal-helpLink {
  display: inline;
  margin-left: 6px;
  color: var(--forum-primary-color);
  font-size: 12px;
  text-decoration: none;
}

.GroupModal-helpLink:hover {
  text-decoration: underline;
}

.GroupModal-toggleRow {
  margin-top: -2px;
}

.GroupHiddenToggle {
  width: fit-content;
  min-height: 38px;
  padding: 0;
  border: none;
  background: transparent;
  justify-content: flex-start;
  color: var(--forum-text-color);
  font-size: 14px;
  font-weight: 600;
}

.GroupHiddenToggle input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.GroupHiddenToggle--switch {
  gap: 12px;
}

.GroupHiddenToggle-switch {
  position: relative;
  width: 52px;
  height: 32px;
  border-radius: 999px;
  background: #b8bcc2;
  transition: background 0.2s ease;
}

.GroupHiddenToggle-switch::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 26px;
  height: 26px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.25);
  transition: transform 0.2s ease;
}

.GroupHiddenToggle input:checked + .GroupHiddenToggle-switch {
  background: #90959c;
}

.GroupHiddenToggle input:checked + .GroupHiddenToggle-switch::after {
  transform: translateX(20px);
}

.GroupHiddenToggle span {
  white-space: nowrap;
}

.GroupModal-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-shrink: 0;
  padding: 22px 38px 26px;
  border-top: 1px solid #d6deea;
  background: #eef3fa;
}

.GroupModal-actions .Modal-footerNote {
  margin-right: auto;
}

.GroupModal-saveButton {
  min-width: 112px;
  min-height: 40px;
  justify-content: center;
}

@media (max-width: 768px) {
  .GroupBar {
    padding: 14px;
    border-radius: 16px;
  }

  .GroupBar-item,
  .GroupBar-add {
    width: 100%;
    min-height: 44px;
    border-radius: 12px;
  }

  .GroupBar-select {
    min-width: 0;
  }

  .Form-group--groupName {
    max-width: none;
  }

  #admin-app .Modal-content.Modal-content--group {
    min-width: 0;
    max-height: calc(100dvh - 8px);
  }

  #admin-app .Modal-content.Modal-content--group .Modal-header,
  #admin-app .Modal-content.Modal-content--group .Modal-body {
    padding: 22px;
  }

  .GroupModal-actions {
    justify-content: flex-end;
    padding: 18px 22px 22px;
  }

  .GroupModal-saveButton {
    width: auto;
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

  .PermissionMobileCard-description,
  .PermissionMobileCard-dependencies {
    margin: 0 0 8px;
    color: var(--forum-text-soft);
    font-size: 12px;
    line-height: 1.5;
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
