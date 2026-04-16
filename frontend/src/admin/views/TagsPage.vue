<template>
  <AdminPage
    className="TagsPage"
    icon="fas fa-tags"
    title="标签管理"
    description="管理讨论标签和分类"
  >
    <div class="TagsPage-content">
      <div class="TagsPage-toolbar">
        <button @click="openCreateModal" class="Button Button--primary">
          <i class="fas fa-plus"></i>
          创建标签
        </button>
      </div>

      <div class="TagsPage-list">
        <table class="TagTable">
          <thead>
            <tr>
              <th style="width: 190px">预览</th>
              <th>标签名称</th>
              <th>别名</th>
              <th>层级</th>
              <th>状态</th>
              <th>讨论数</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="7" class="TagTable-loading">加载中...</td>
            </tr>
            <tr v-else-if="!tagRows.length">
              <td colspan="7" class="TagTable-empty">暂无标签</td>
            </tr>
            <tr v-for="row in tagRows" v-else :key="row.tag.id">
              <td>
                <span class="TagBadgePreview" :style="getTagBadgeStyle(row.tag)">
                  <i v-if="row.tag.icon" :class="row.tag.icon"></i>
                  <span>{{ row.tag.name }}</span>
                </span>
              </td>
              <td>
                <div class="TagNameCell" :style="{ '--tag-depth': row.depth }">
                  <span class="TagNameCell-line" :class="{ 'is-child': row.depth > 0 }"></span>
                  <div class="TagNameCell-main">
                    <strong>{{ row.tag.name }}</strong>
                    <small>排序 {{ row.tag.position }}</small>
                  </div>
                </div>
              </td>
              <td>
                <code class="TagSlug">{{ row.tag.slug }}</code>
              </td>
              <td>
                <div class="TagHierarchy">
                  <span>{{ row.depth > 0 ? '子标签' : '顶级标签' }}</span>
                  <small v-if="row.parentName">隶属 {{ row.parentName }}</small>
                </div>
              </td>
              <td>
                <div class="TagStatusList">
                  <span v-if="row.tag.is_hidden" class="TagStatus TagStatus--muted">隐藏</span>
                  <span v-if="row.tag.is_restricted" class="TagStatus TagStatus--warning">限制发帖</span>
                  <span class="TagStatus">查看: {{ getScopeLabel(row.tag.view_scope) }}</span>
                  <span class="TagStatus">发帖: {{ getScopeLabel(row.tag.start_discussion_scope) }}</span>
                  <span class="TagStatus">回帖: {{ getScopeLabel(row.tag.reply_scope) }}</span>
                  <span v-if="!row.tag.is_hidden && !row.tag.is_restricted" class="TagStatus">公开</span>
                </div>
              </td>
              <td>{{ row.tag.discussion_count }}</td>
              <td>
                <button @click="editTag(row.tag)" class="Button Button--small">
                  编辑
                </button>
                <button @click="deleteTag(row.tag)" class="Button Button--small Button--danger">
                  删除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="showCreateModal || showEditModal" class="Modal" @click.self="closeModal">
      <div class="Modal-content">
        <div class="Modal-header">
          <div>
            <h3>{{ showEditModal ? '编辑标签' : '创建标签' }}</h3>
            <p class="Modal-subtitle">参考 Flarum 的标签编辑流程，并补齐父子层级、排序和显示状态配置。</p>
          </div>
          <button @click="closeModal" class="Modal-close">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="Modal-body">
          <div class="TagPreviewPanel">
            <span class="TagPreviewPanel-label">实时预览</span>
            <div class="TagPreviewPanel-card">
              <div class="TagPreviewPanel-badge">
                <span class="TagBadgePreview TagBadgePreview--large" :style="getTagBadgeStyle(formData)">
                  <i v-if="formData.icon" :class="formData.icon"></i>
                  <span>{{ formData.name || '新标签' }}</span>
                </span>
              </div>
              <div class="TagPreviewPanel-meta">
                <small>
                  {{ formData.parent_id ? '当前会作为子标签显示在父标签下方。' : '当前会作为顶级标签显示在列表中。' }}
                </small>
              </div>
            </div>
          </div>

          <div class="FormRow">
            <div class="Form-group">
              <label>标签名称 *</label>
              <input
                v-model.trim="formData.name"
                type="text"
                class="FormControl"
                placeholder="例如：技术讨论"
              />
            </div>

            <div class="Form-group">
              <label>别名 / Slug</label>
              <input
                v-model.trim="formData.slug"
                type="text"
                class="FormControl"
                placeholder="例如：tech-talk"
              />
              <div class="Form-help">留空时自动生成，建议使用短横线风格。</div>
            </div>
          </div>

          <div class="Form-group">
            <label>描述</label>
            <textarea
              v-model.trim="formData.description"
              class="FormControl"
              rows="3"
              placeholder="标签的简短描述"
            ></textarea>
          </div>

          <div class="FormRow">
            <div class="Form-group">
              <label>父标签</label>
              <select v-model="formData.parent_id" class="FormControl">
                <option :value="null">作为顶级标签</option>
                <option
                  v-for="option in availableParentOptions"
                  :key="option.id"
                  :value="option.id"
                >
                  {{ option.label }}
                </option>
              </select>
              <div class="Form-help">设置后，这个标签会显示在对应父标签下方。</div>
            </div>

            <div class="Form-group">
              <label>排序位置</label>
              <input
                v-model.number="formData.position"
                type="number"
                min="0"
                class="FormControl"
                placeholder="0"
              />
              <div class="Form-help">数字越小越靠前，和 Flarum 的排序思路一致。</div>
            </div>
          </div>

          <div class="Form-group">
            <label>颜色</label>
            <div class="ColorPicker">
              <input
                v-model="formData.color"
                type="color"
                class="ColorPicker-input"
              />
              <input
                v-model="formData.color"
                type="text"
                class="FormControl ColorPicker-text"
                placeholder="#888888"
              />
            </div>
            <div class="ColorPresetList">
              <button
                v-for="color in TAG_COLOR_PRESETS"
                :key="color"
                type="button"
                class="ColorPreset"
                :class="{ active: normalizeColor(formData.color) === color.toLowerCase() }"
                :style="{ '--preset-color': color }"
                @click="formData.color = color"
              ></button>
            </div>
          </div>

          <div class="Form-group">
            <div class="Form-group-header">
              <label>图标</label>
              <button type="button" class="LinkButton" @click="formData.icon = ''">清除图标</button>
            </div>

            <input
              v-model.trim="iconSearch"
              type="text"
              class="FormControl"
              placeholder="搜索图标，例如 code、comments、tag"
            />

            <div class="IconPicker">
              <button
                v-for="icon in filteredIconOptions"
                :key="icon.value"
                type="button"
                class="IconPicker-option"
                :class="{ active: formData.icon === icon.value }"
                @click="formData.icon = icon.value"
              >
                <i :class="icon.value"></i>
                <span>{{ icon.label }}</span>
              </button>
            </div>

            <div v-if="!filteredIconOptions.length" class="IconPicker-empty">
              没有找到匹配的图标
            </div>

            <div class="Form-help">标签仍然保存为 Font Awesome 类名，但现在可以直接搜索和点选。</div>
            <input
              v-model.trim="formData.icon"
              type="text"
              class="FormControl FormControl--subtle"
              placeholder="高级模式：手动输入 Font Awesome 类名"
            />
          </div>

          <div class="Form-group">
            <label>显示与发帖限制</label>
            <div class="CheckboxRow">
              <label class="CheckboxChip">
                <input v-model="formData.is_hidden" type="checkbox" />
                <span>隐藏标签</span>
              </label>

              <label class="CheckboxChip">
                <input v-model="formData.is_restricted" type="checkbox" />
                <span>限制发帖</span>
              </label>
            </div>
          </div>

          <div class="FormRow">
            <div class="Form-group">
              <label>查看权限</label>
              <select v-model="formData.view_scope" class="FormControl">
                <option v-for="option in TAG_SCOPE_OPTIONS" :key="`view-${option.value}`" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>

            <div class="Form-group">
              <label>发帖权限</label>
              <select v-model="formData.start_discussion_scope" class="FormControl">
                <option v-for="option in TAG_SCOPE_OPTIONS" :key="`start-${option.value}`" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
            </div>
          </div>

          <div class="Form-group">
            <label>回帖权限</label>
            <select v-model="formData.reply_scope" class="FormControl">
              <option v-for="option in TAG_SCOPE_OPTIONS" :key="`reply-${option.value}`" :value="option.value">
                {{ option.label }}
              </option>
            </select>
            <div class="Form-help">标签级权限会作用到讨论列表、详情页、发帖和回帖流程。</div>
          </div>
        </div>

        <div class="Modal-footer">
          <button @click="closeModal" class="Button">
            取消
          </button>
          <button @click="saveTag" class="Button Button--primary" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import api from '../../api'

const TAG_COLOR_PRESETS = [
  '#3c78d8',
  '#4d698e',
  '#0e7490',
  '#0f766e',
  '#2f855a',
  '#65a30d',
  '#ca8a04',
  '#ea580c',
  '#dc2626',
  '#c026d3',
  '#7c3aed',
  '#475569',
]

const TAG_SCOPE_OPTIONS = [
  { value: 'public', label: '所有人' },
  { value: 'members', label: '已登录用户' },
  { value: 'staff', label: '仅管理员' },
]

const TAG_ICON_OPTIONS = [
  { value: 'fas fa-comments', label: '讨论' },
  { value: 'fas fa-comment-dots', label: '对话' },
  { value: 'fas fa-code', label: '代码' },
  { value: 'fas fa-terminal', label: '终端' },
  { value: 'fas fa-bug', label: '问题' },
  { value: 'fas fa-lightbulb', label: '想法' },
  { value: 'fas fa-rocket', label: '发布' },
  { value: 'fas fa-book', label: '文档' },
  { value: 'fas fa-graduation-cap', label: '教程' },
  { value: 'fas fa-wrench', label: '工具' },
  { value: 'fas fa-cubes', label: '框架' },
  { value: 'fas fa-plug', label: '插件' },
  { value: 'fas fa-cloud', label: '云服务' },
  { value: 'fas fa-server', label: '服务端' },
  { value: 'fas fa-database', label: '数据库' },
  { value: 'fas fa-shield-alt', label: '安全' },
  { value: 'fas fa-mobile-alt', label: '移动端' },
  { value: 'fas fa-desktop', label: '桌面端' },
  { value: 'fas fa-image', label: '图片' },
  { value: 'fas fa-video', label: '视频' },
  { value: 'fas fa-music', label: '音频' },
  { value: 'fas fa-gamepad', label: '游戏' },
  { value: 'fas fa-briefcase', label: '工作' },
  { value: 'fas fa-chart-line', label: '增长' },
  { value: 'fas fa-bullhorn', label: '公告' },
  { value: 'fas fa-fire', label: '热门' },
  { value: 'fas fa-star', label: '精选' },
  { value: 'fas fa-heart', label: '喜欢' },
  { value: 'fas fa-users', label: '社区' },
  { value: 'fas fa-user-shield', label: '管理' },
  { value: 'fas fa-tags', label: '标签' },
  { value: 'fas fa-thumbtack', label: '置顶' },
  { value: 'fas fa-lock', label: '锁定' },
  { value: 'fas fa-language', label: '语言' },
  { value: 'fas fa-globe', label: '全球' },
  { value: 'fas fa-seedling', label: '新手' },
]

const tags = ref([])
const loading = ref(true)
const showCreateModal = ref(false)
const showEditModal = ref(false)
const saving = ref(false)
const editingTag = ref(null)
const iconSearch = ref('')

const formData = ref(getEmptyForm())

const filteredIconOptions = computed(() => {
  const query = iconSearch.value.trim().toLowerCase()
  if (!query) return TAG_ICON_OPTIONS

  return TAG_ICON_OPTIONS.filter(icon =>
    icon.label.toLowerCase().includes(query) || icon.value.toLowerCase().includes(query)
  )
})

const tagTree = computed(() => buildTagTree(tags.value))
const tagRows = computed(() => flattenTagTree(tagTree.value))
const availableParentOptions = computed(() => {
  const editingId = editingTag.value?.id || null
  const blockedIds = editingId ? new Set([editingId, ...collectDescendantIds(tags.value, editingId)]) : new Set()

  return tagRows.value
    .filter(row => !blockedIds.has(row.tag.id))
    .map(row => ({
      id: row.tag.id,
      label: `${'— '.repeat(row.depth)}${row.tag.name}`
    }))
})

onMounted(() => {
  loadTags()
})

async function loadTags() {
  loading.value = true
  try {
    const data = await api.get('/admin/tags')
    tags.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error('加载标签失败:', error)
  } finally {
    loading.value = false
  }
}

function openCreateModal() {
  editingTag.value = null
  iconSearch.value = ''
  formData.value = getEmptyForm({
    position: getNextPosition(tags.value, null),
  })
  showCreateModal.value = true
}

function editTag(tag) {
  editingTag.value = tag
  iconSearch.value = ''
  formData.value = getEmptyForm({
    name: tag.name,
    slug: tag.slug,
    description: tag.description,
    color: tag.color,
    icon: tag.icon,
    position: tag.position,
    parent_id: tag.parent_id ?? null,
    is_hidden: Boolean(tag.is_hidden),
    is_restricted: Boolean(tag.is_restricted),
    view_scope: tag.view_scope || 'public',
    start_discussion_scope: tag.start_discussion_scope || 'members',
    reply_scope: tag.reply_scope || 'members',
  })
  showEditModal.value = true
}

async function saveTag() {
  if (!formData.value.name) {
    alert('请输入标签名称')
    return
  }

  saving.value = true
  try {
    const payload = {
      ...formData.value,
      name: formData.value.name.trim(),
      slug: (formData.value.slug || '').trim(),
      description: (formData.value.description || '').trim(),
      color: formData.value.color || '#888888',
      icon: (formData.value.icon || '').trim(),
      position: Number(formData.value.position || 0),
      parent_id: formData.value.parent_id ?? null,
      is_hidden: Boolean(formData.value.is_hidden),
      is_restricted: Boolean(formData.value.is_restricted),
      view_scope: formData.value.view_scope || 'public',
      start_discussion_scope: formData.value.start_discussion_scope || 'members',
      reply_scope: formData.value.reply_scope || 'members',
    }

    if (showEditModal.value) {
      await api.put(`/admin/tags/${editingTag.value.id}`, payload)
    } else {
      await api.post('/admin/tags', payload)
    }

    closeModal()
    await loadTags()
  } catch (error) {
    console.error('保存标签失败:', error)
    const errorMsg = error.response?.data?.error
      || error.response?.data?.detail
      || error.message
      || '未知错误'
    alert(`保存失败: ${errorMsg}`)
  } finally {
    saving.value = false
  }
}

async function deleteTag(tag) {
  if (!confirm(`确定要删除标签“${tag.name}”吗？`)) {
    return
  }

  try {
    await api.delete(`/admin/tags/${tag.id}`)
    await loadTags()
  } catch (error) {
    alert('删除失败: ' + (error.response?.data?.error || '未知错误'))
  }
}

function closeModal() {
  showCreateModal.value = false
  showEditModal.value = false
  editingTag.value = null
  iconSearch.value = ''
  formData.value = getEmptyForm()
}

function getEmptyForm(overrides = {}) {
  return {
    name: '',
    slug: '',
    description: '',
    color: '#888888',
    icon: '',
    position: 0,
    parent_id: null,
    is_hidden: false,
    is_restricted: false,
    view_scope: 'public',
    start_discussion_scope: 'members',
    reply_scope: 'members',
    ...overrides,
  }
}

function normalizeColor(value) {
  return String(value || '').trim().toLowerCase()
}

function getScopeLabel(scope) {
  return TAG_SCOPE_OPTIONS.find(option => option.value === scope)?.label || '未知'
}

function getTagBadgeStyle(tag) {
  const color = tag.color || '#888888'
  return {
    '--tag-bg': color,
    opacity: tag.is_hidden ? 0.55 : 1,
  }
}

function buildTagTree(sourceTags) {
  const records = sourceTags.map(tag => ({
    ...tag,
    children: [],
  }))
  const byId = new Map(records.map(tag => [tag.id, tag]))
  const roots = []

  for (const tag of records) {
    const parent = tag.parent_id ? byId.get(tag.parent_id) : null
    if (parent) {
      parent.children.push(tag)
    } else {
      roots.push(tag)
    }
  }

  sortTagNodes(roots)
  return roots
}

function sortTagNodes(nodes) {
  nodes.sort((left, right) => {
    const leftPosition = Number(left.position ?? 0)
    const rightPosition = Number(right.position ?? 0)
    if (leftPosition !== rightPosition) return leftPosition - rightPosition
    return String(left.name || '').localeCompare(String(right.name || ''), 'zh-CN')
  })

  for (const node of nodes) {
    sortTagNodes(node.children)
  }
}

function flattenTagTree(nodes, depth = 0, parentName = null) {
  return nodes.flatMap(node => [
    { tag: node, depth, parentName },
    ...flattenTagTree(node.children, depth + 1, node.name)
  ])
}

function collectDescendantIds(sourceTags, tagId) {
  const children = sourceTags.filter(tag => tag.parent_id === tagId)
  return children.flatMap(child => [child.id, ...collectDescendantIds(sourceTags, child.id)])
}

function getNextPosition(sourceTags, parentId) {
  const siblingPositions = sourceTags
    .filter(tag => (tag.parent_id ?? null) === (parentId ?? null))
    .map(tag => Number(tag.position || 0))

  return siblingPositions.length ? Math.max(...siblingPositions) + 1 : 0
}
</script>

<style scoped>
.TagsPage-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.TagsPage-toolbar {
  display: flex;
  justify-content: flex-end;
}

.Button {
  background: #f5f8fa;
  border: 1px solid #ddd;
  padding: 8px 16px;
  border-radius: 3px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.Button:hover:not(:disabled) {
  background: #e8eef5;
  border-color: #4d698e;
}

.Button--primary {
  background: #4d698e;
  color: white;
  border-color: #4d698e;
}

.Button--primary:hover:not(:disabled) {
  background: #3d5875;
}

.Button--small {
  padding: 4px 10px;
  font-size: 12px;
}

.Button--danger {
  color: #e74c3c;
}

.Button--danger:hover:not(:disabled) {
  background: #fee;
  border-color: #e74c3c;
}

.Button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.TagTable {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
}

.TagTable thead th {
  padding: 12px;
  background: #f5f8fa;
  border-bottom: 2px solid #e3e8ed;
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  color: #666;
}

.TagTable tbody td {
  padding: 12px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
  vertical-align: middle;
}

.TagTable tbody tr:hover {
  background: #fafbfc;
}

.TagTable-loading,
.TagTable-empty {
  text-align: center;
  padding: 40px;
  color: #999;
}

.TagBadgePreview {
  --tag-bg: #888888;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 30px;
  max-width: 100%;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--tag-bg);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.08);
}

.TagBadgePreview span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.TagBadgePreview i {
  font-size: 12px;
}

.TagBadgePreview--large {
  min-height: 38px;
  max-width: min(320px, 100%);
  padding: 0 14px;
  font-size: 14px;
}

.TagNameCell {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-left: calc(var(--tag-depth, 0) * 16px);
}

.TagNameCell-line {
  width: 10px;
  height: 1px;
  background: transparent;
  flex-shrink: 0;
}

.TagNameCell-line.is-child {
  background: rgba(120, 132, 146, 0.42);
}

.TagNameCell-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.TagNameCell-main small,
.TagHierarchy small {
  color: #8694a1;
}

.TagSlug {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f5f8fb;
  color: #4b5d6e;
  font-size: 12px;
}

.TagHierarchy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.TagStatusList {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.TagStatus {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  background: #eef3f7;
  color: #506274;
  font-size: 12px;
  font-weight: 600;
}

.TagStatus--muted {
  background: #f1f3f5;
  color: #788591;
}

.TagStatus--warning {
  background: #fff1dc;
  color: #b56a18;
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
  background: white;
  border-radius: 10px;
  width: 90%;
  max-width: 760px;
  max-height: 90vh;
  overflow-y: auto;
  overflow-x: hidden;
}

.Modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  padding: 20px 24px;
  border-bottom: 1px solid #e3e8ed;
}

.Modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.Modal-subtitle {
  margin: 6px 0 0;
  color: #7a8794;
  font-size: 13px;
}

.Modal-close {
  background: none;
  border: none;
  font-size: 20px;
  color: #999;
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
}

.Modal-close:hover {
  background: #f5f8fa;
  color: #333;
}

.Modal-body {
  padding: 24px;
}

.Modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 20px 24px;
  border-top: 1px solid #e3e8ed;
}

.TagPreviewPanel {
  margin-bottom: 20px;
}

.TagPreviewPanel-label {
  display: block;
  margin-bottom: 8px;
  color: #617282;
  font-size: 13px;
  font-weight: 600;
}

.TagPreviewPanel-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  padding: 16px 18px;
  border: 1px solid #e3e8ed;
  border-radius: 12px;
  background: linear-gradient(180deg, #fbfdff, #f4f7fa);
}

.TagPreviewPanel-badge {
  min-width: 0;
  max-width: 100%;
}

.TagPreviewPanel-meta {
  min-width: 0;
  width: 100%;
}

.TagPreviewPanel-card small {
  color: #768594;
  line-height: 1.6;
}

.Form-group {
  margin-bottom: 20px;
}

.Form-group:last-child {
  margin-bottom: 0;
}

.Form-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.Form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #333;
  font-size: 14px;
}

.FormControl {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 14px;
  font-family: inherit;
  transition: border-color 0.2s;
}

.FormControl:focus {
  outline: none;
  border-color: #4d698e;
}

.FormControl--subtle {
  margin-top: 10px;
  background: #f8fafc;
}

.Form-help {
  margin-top: 10px;
  color: #7a8794;
  font-size: 13px;
}

.FormRow {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.FormRow > * {
  min-width: 0;
}

.ColorPicker {
  display: flex;
  gap: 10px;
  align-items: center;
}

.ColorPicker-input {
  width: 60px;
  height: 40px;
  border: 1px solid #ddd;
  border-radius: 3px;
  cursor: pointer;
}

.ColorPicker-text {
  flex: 1;
}

.ColorPresetList {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.ColorPreset {
  --preset-color: #888888;
  width: 26px;
  height: 26px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: var(--preset-color);
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.12);
}

.ColorPreset.active {
  box-shadow:
    inset 0 0 0 2px rgba(255, 255, 255, 0.9),
    0 0 0 3px color-mix(in srgb, var(--preset-color) 26%, white);
}

.IconPicker {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.IconPicker-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  min-height: 84px;
  padding: 12px 10px;
  border: 1px solid #dce4ec;
  border-radius: 10px;
  background: #fff;
  color: #4a5d70;
}

.IconPicker-option:hover {
  border-color: #4d698e;
  background: #f7fafe;
}

.IconPicker-option.active {
  border-color: #4d698e;
  background: #edf3f9;
  color: #35506f;
}

.IconPicker-option i {
  font-size: 18px;
}

.IconPicker-option span {
  font-size: 12px;
  line-height: 1.4;
  text-align: center;
}

.IconPicker-empty {
  margin-top: 12px;
  color: #8a97a3;
  font-size: 13px;
}

.LinkButton {
  border: 0;
  background: transparent;
  color: #4d698e;
  padding: 0;
  font-size: 13px;
  font-weight: 600;
}

.LinkButton:hover {
  color: #3d5875;
  text-decoration: underline;
}

.CheckboxRow {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: flex-start;
}

.CheckboxChip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid #dce4ec;
  border-radius: 999px;
  background: #fbfdff;
  color: #44515e;
  line-height: 1;
  margin-bottom: 0;
  font-weight: 500;
  width: auto;
}

.CheckboxChip input {
  margin: 0;
  flex-shrink: 0;
  width: 14px;
  height: 14px;
  align-self: center;
  transform: translateY(-0.5px);
}

.CheckboxChip span {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  line-height: 1;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .Modal-content {
    width: calc(100vw - 24px);
  }

  .FormRow {
    grid-template-columns: 1fr;
  }

  .ColorPicker {
    flex-direction: column;
    align-items: stretch;
  }

  .IconPicker {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
