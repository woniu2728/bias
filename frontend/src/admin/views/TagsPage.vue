<template>
  <AdminPage
    className="TagsPage"
    icon="fas fa-tags"
    title="标签管理"
    description="管理讨论标签和分类"
  >
    <div class="TagsPage-content">
      <AdminToolbar align="end">
        <button @click="openCreateModal" class="Button Button--primary">
          <i class="fas fa-plus"></i>
          创建标签
        </button>
        <button @click="refreshTagStats" class="Button" :disabled="refreshingStats">
          <i class="fas fa-sync-alt" :class="{ 'fa-spin': refreshingStats }"></i>
          {{ refreshingStats ? '刷新中...' : '刷新统计' }}
        </button>
      </AdminToolbar>

      <div class="TagSummaryGrid">
        <article class="TagSummaryCard">
          <small>标签总数</small>
          <strong>{{ tagSummary.total }}</strong>
        </article>
        <article class="TagSummaryCard">
          <small>顶级 / 子标签</small>
          <strong>{{ tagSummary.root }} / {{ tagSummary.child }}</strong>
        </article>
        <article class="TagSummaryCard">
          <small>隐藏标签</small>
          <strong>{{ tagSummary.hidden }}</strong>
        </article>
        <article class="TagSummaryCard">
          <small>限制发帖</small>
          <strong>{{ tagSummary.restricted }}</strong>
        </article>
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
              <td colspan="7" class="TagTable-loading">
                <AdminStateBlock tone="subtle">加载中...</AdminStateBlock>
              </td>
            </tr>
            <tr v-else-if="!tagRows.length">
              <td colspan="7" class="TagTable-empty">
                <AdminStateBlock>暂无标签</AdminStateBlock>
              </td>
            </tr>
            <tr v-for="row in tagRows" v-else :key="row.tag.id">
              <td data-label="预览">
                <span class="TagBadgePreview" :style="getTagBadgeStyle(row.tag)">
                  <i v-if="row.tag.icon" :class="row.tag.icon"></i>
                  <span>{{ row.tag.name }}</span>
                </span>
              </td>
              <td data-label="标签名称">
                <div class="TagNameCell" :style="{ '--tag-depth': row.depth }">
                  <span class="TagNameCell-line" :class="{ 'is-child': row.depth > 0 }"></span>
                  <div class="TagNameCell-main">
                    <strong>{{ row.tag.name }}</strong>
                    <small>排序 {{ row.tag.position }}</small>
                  </div>
                </div>
              </td>
              <td data-label="别名">
                <code class="TagSlug">{{ row.tag.slug }}</code>
              </td>
              <td data-label="层级">
                <div class="TagHierarchy">
                  <span>{{ row.depth > 0 ? '子标签' : '顶级标签' }}</span>
                  <small v-if="row.parentName">隶属 {{ row.parentName }}</small>
                </div>
              </td>
              <td data-label="状态">
                <div class="TagStatusList">
                  <span v-if="row.tag.is_hidden" class="TagStatus TagStatus--muted">隐藏</span>
                  <span v-if="row.tag.is_restricted" class="TagStatus TagStatus--warning">限制发帖</span>
                  <span class="TagStatus">查看: {{ getScopeLabel(row.tag.view_scope) }}</span>
                  <span class="TagStatus">发帖: {{ getScopeLabel(row.tag.start_discussion_scope) }}</span>
                  <span class="TagStatus">回帖: {{ getScopeLabel(row.tag.reply_scope) }}</span>
                  <span v-if="!row.tag.is_hidden && !row.tag.is_restricted" class="TagStatus">公开</span>
                </div>
              </td>
              <td data-label="讨论数">{{ row.tag.discussion_count }}</td>
              <td data-label="操作">
                <button @click="editTag(row.tag)" class="Button Button--small">
                  编辑
                </button>
                <button
                  @click="moveTag(row.tag, 'up')"
                  class="Button Button--small"
                  :disabled="!canMoveTag(row.tag, 'up') || movingTagId === row.tag.id"
                >
                  上移
                </button>
                <button
                  @click="moveTag(row.tag, 'down')"
                  class="Button Button--small"
                  :disabled="!canMoveTag(row.tag, 'down') || movingTagId === row.tag.id"
                >
                  下移
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

          <div class="TagConfigSummary">
            <article class="TagConfigCard">
              <small>层级</small>
              <strong>{{ hierarchySummary }}</strong>
            </article>
            <article class="TagConfigCard">
              <small>排序</small>
              <strong>{{ positionSummary }}</strong>
            </article>
            <article class="TagConfigCard">
              <small>查看范围</small>
              <strong>{{ visibilitySummary }}</strong>
            </article>
            <article class="TagConfigCard">
              <small>发帖 / 回帖</small>
              <strong>{{ postingSummary }}</strong>
            </article>
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
              <select v-model="formData.parent_id" class="FormControl" :disabled="editingTagHasChildren">
                <option :value="null">作为顶级标签</option>
                <option
                  v-for="option in availableParentOptions"
                  :key="option.id"
                  :value="option.id"
                >
                  {{ option.label }}
                </option>
              </select>
              <div class="Form-help">
                {{ editingTagHasChildren
                  ? '当前标签下已有子标签，不能再把它设为次标签。'
                  : '只能选择顶级标签作为父标签；设置后，这个标签会显示在对应父标签下方。' }}
              </div>
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
              <div class="Form-help">{{ positionHelpText }}</div>
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
                <option v-for="option in availableStartScopeOptions" :key="`start-${option.value}`" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
              <div class="Form-help">发帖权限不能比查看权限更宽松。</div>
            </div>
          </div>

          <div class="Form-group">
            <label>回帖权限</label>
            <select v-model="formData.reply_scope" class="FormControl">
              <option v-for="option in availableReplyScopeOptions" :key="`reply-${option.value}`" :value="option.value">
                {{ option.label }}
              </option>
            </select>
            <div class="Form-help">
              {{ formData.is_restricted
                ? '“限制发帖”开启后，普通用户无法在该标签下发起讨论；回帖权限仍按这里的配置生效。'
                : '标签级权限会作用到讨论列表、详情页、发帖和回帖流程。' }}
            </div>
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
import { computed, onMounted, ref, watch } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import AdminToolbar from '../components/AdminToolbar.vue'
import api from '../../api'
import { useModalStore } from '../../stores/modal'

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
const movingTagId = ref(null)
const refreshingStats = ref(false)
const editingTag = ref(null)
const iconSearch = ref('')
const modalStore = useModalStore()

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
const tagSummary = computed(() => ({
  total: tags.value.length,
  root: tags.value.filter(tag => !tag.parent_id).length,
  child: tags.value.filter(tag => Boolean(tag.parent_id)).length,
  hidden: tags.value.filter(tag => tag.is_hidden).length,
  restricted: tags.value.filter(tag => tag.is_restricted).length,
}))
const editingTagHasChildren = computed(() => {
  if (!editingTag.value) return false
  return tags.value.some(tag => tag.parent_id === editingTag.value.id)
})
const availableParentOptions = computed(() => {
  const editingId = editingTag.value?.id || null
  const blockedIds = editingId ? new Set([editingId, ...collectDescendantIds(tags.value, editingId)]) : new Set()

  return tagRows.value
    .filter(row => row.depth === 0 && !blockedIds.has(row.tag.id))
    .map(row => ({
      id: row.tag.id,
      label: row.tag.name
    }))
})
const availableStartScopeOptions = computed(() => {
  const minimumLevel = getScopeLevel(formData.value.view_scope)
  return TAG_SCOPE_OPTIONS.filter(option => getScopeLevel(option.value) >= minimumLevel)
})
const availableReplyScopeOptions = computed(() => {
  const minimumLevel = getScopeLevel(formData.value.view_scope)
  return TAG_SCOPE_OPTIONS.filter(option => getScopeLevel(option.value) >= minimumLevel)
})
const hierarchySummary = computed(() => {
  if (!formData.value.parent_id) {
    return '顶级标签'
  }

  const parentTag = tags.value.find(tag => tag.id === formData.value.parent_id)
  return parentTag ? `子标签 · 归属 ${parentTag.name}` : '子标签'
})
const positionSummary = computed(() => {
  const siblingCount = getSiblingCount(formData.value.parent_id, editingTag.value?.id)
  const rank = getPreviewRank(formData.value.parent_id, formData.value.position, editingTag.value?.id)
  return `第 ${rank} 位 / 共 ${siblingCount + 1} 个同级标签`
})
const visibilitySummary = computed(() => {
  const baseText = `查看: ${getScopeLabel(formData.value.view_scope)}`
  return formData.value.is_hidden ? `${baseText} · 前台隐藏` : `${baseText} · 正常显示`
})
const postingSummary = computed(() => {
  if (formData.value.is_restricted) {
    return `发帖: 仅管理员 · 回帖: ${getScopeLabel(formData.value.reply_scope)}`
  }
  return `发帖: ${getScopeLabel(formData.value.start_discussion_scope)} · 回帖: ${getScopeLabel(formData.value.reply_scope)}`
})
const positionHelpText = computed(() => {
  const parentText = formData.value.parent_id ? '当前父标签下' : '顶级标签层'
  return `${parentText}数字越小越靠前；${positionSummary.value}。`
})

onMounted(() => {
  loadTags()
})

watch(
  () => formData.value.view_scope,
  viewScope => {
    if (getScopeLevel(formData.value.start_discussion_scope) < getScopeLevel(viewScope)) {
      formData.value.start_discussion_scope = viewScope
    }
    if (getScopeLevel(formData.value.reply_scope) < getScopeLevel(viewScope)) {
      formData.value.reply_scope = viewScope
    }
  }
)

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
    await modalStore.alert({
      title: '信息不完整',
      message: '请输入标签名称',
      tone: 'warning'
    })
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
    await modalStore.alert({
      title: '保存失败',
      message: errorMsg,
      tone: 'danger'
    })
  } finally {
    saving.value = false
  }
}

async function deleteTag(tag) {
  const confirmed = await modalStore.confirm({
    title: '删除标签',
    message: `确定要删除标签“${tag.name}”吗？`,
    confirmText: '删除',
    cancelText: '取消',
    tone: 'danger'
  })
  if (!confirmed) {
    return
  }

  try {
    await api.delete(`/admin/tags/${tag.id}`)
    await loadTags()
    await modalStore.alert({
      title: '标签已删除',
      message: `标签“${tag.name}”已删除。`,
      tone: 'success'
    })
  } catch (error) {
    await modalStore.alert({
      title: '删除失败',
      message: error.response?.data?.error || '未知错误',
      tone: 'danger'
    })
  }
}

async function refreshTagStats() {
  const confirmed = await modalStore.confirm({
    title: '刷新标签统计',
    message: '确定刷新全部标签的讨论数和最后发帖信息吗？数据量较大时建议在低峰期执行。',
    confirmText: '刷新',
    cancelText: '取消',
    tone: 'warning'
  })
  if (!confirmed) {
    return
  }

  refreshingStats.value = true
  try {
    await api.post('/admin/tags/stats/refresh')
    await loadTags()
  } catch (error) {
    await modalStore.alert({
      title: '刷新标签统计失败',
      message: error.response?.data?.error || error.message || '未知错误',
      tone: 'danger'
    })
  } finally {
    refreshingStats.value = false
  }
}

async function moveTag(tag, direction) {
  if (!canMoveTag(tag, direction)) return

  movingTagId.value = tag.id
  try {
    const response = await api.post(`/admin/tags/${tag.id}/move`, { direction })
    tags.value = Array.isArray(response.data) ? response.data : tags.value
  } catch (error) {
    const errorMsg = error.response?.data?.error
      || error.response?.data?.detail
      || error.message
      || '未知错误'
    await modalStore.alert({
      title: '调整排序失败',
      message: errorMsg,
      tone: 'danger'
    })
  } finally {
    movingTagId.value = null
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

function getScopeLevel(scope) {
  const levels = {
    public: 0,
    members: 1,
    staff: 2,
  }
  return levels[scope] ?? 0
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

function getSiblingRows(tag) {
  return tagRows.value.filter(row => (row.tag.parent_id ?? null) === (tag.parent_id ?? null))
}

function canMoveTag(tag, direction) {
  const siblings = getSiblingRows(tag)
  const currentIndex = siblings.findIndex(row => row.tag.id === tag.id)
  if (currentIndex < 0) return false
  if (direction === 'up') return currentIndex > 0
  if (direction === 'down') return currentIndex < siblings.length - 1
  return false
}

function getSiblingCount(parentId, excludeTagId = null) {
  return tags.value.filter(tag => {
    if ((tag.parent_id ?? null) !== (parentId ?? null)) return false
    if (excludeTagId && tag.id === excludeTagId) return false
    return true
  }).length
}

function getPreviewRank(parentId, position, excludeTagId = null) {
  const numericPosition = Number(position || 0)
  const siblings = tags.value
    .filter(tag => {
      if ((tag.parent_id ?? null) !== (parentId ?? null)) return false
      if (excludeTagId && tag.id === excludeTagId) return false
      return true
    })
    .map(tag => Number(tag.position || 0))

  const beforeCount = siblings.filter(value => value < numericPosition).length
  return beforeCount + 1
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

.TagsPage-list {
  min-width: 0;
}

.TagSummaryGrid,
.TagConfigSummary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.TagSummaryCard,
.TagConfigCard {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 18px;
  border: 1px solid var(--forum-border-color);
  border-radius: 12px;
  background: linear-gradient(180deg, var(--forum-bg-elevated), #f6f9fc);
  box-shadow: var(--forum-shadow-sm);
}

.TagSummaryCard small,
.TagConfigCard small {
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-xs);
  font-weight: 600;
}

.TagSummaryCard strong,
.TagConfigCard strong {
  color: var(--forum-text-muted);
  font-size: 16px;
  line-height: 1.5;
}

.Button--small {
  padding: 4px 10px;
  font-size: var(--forum-font-size-xs);
}

.TagTable {
  width: 100%;
  border-collapse: collapse;
  background: var(--forum-bg-elevated);
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
  box-shadow: var(--forum-shadow-sm);
}

.TagTable thead th {
  padding: 12px;
  background: var(--forum-bg-subtle);
  border-bottom: 2px solid var(--forum-border-color);
  font-size: var(--forum-font-size-sm);
  font-weight: 600;
  text-align: left;
  color: var(--forum-text-muted);
}

.TagTable tbody td {
  padding: 12px;
  border-bottom: 1px solid var(--forum-border-soft);
  font-size: var(--forum-font-size-md);
  vertical-align: middle;
}

.TagTable tbody tr:hover {
  background: var(--forum-bg-elevated-strong);
}

.TagTable-loading,
.TagTable-empty {
  padding: 18px;
}

.TagBadgePreview {
  --tag-bg: #888888;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 30px;
  max-width: 100%;
  padding: 0 12px;
  border-radius: var(--forum-radius-pill);
  background: var(--tag-bg);
  color: var(--forum-text-inverse);
  font-size: var(--forum-font-size-sm);
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
  color: var(--forum-text-soft);
}

.TagSlug {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: var(--forum-radius-pill);
  background: #f5f8fb;
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-xs);
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
  border-radius: var(--forum-radius-pill);
  background: var(--forum-bg-subtle);
  color: #506274;
  font-size: var(--forum-font-size-xs);
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

.Modal-content {
  width: 90%;
  max-width: 760px;
  max-height: calc(100vh - 32px);
}

.Modal-subtitle {
  margin: 6px 0 0;
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
}

.TagPreviewPanel {
  margin-bottom: 20px;
}

.TagPreviewPanel-label {
  display: block;
  margin-bottom: 8px;
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
  font-weight: 600;
}

.TagPreviewPanel-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  padding: 16px 18px;
  border: 1px solid var(--forum-border-color);
  border-radius: 12px;
  background: linear-gradient(180deg, #fbfdff, #f4f7fa);
  box-shadow: var(--forum-shadow-sm);
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
  color: var(--forum-text-soft);
  line-height: 1.6;
}

.TagConfigSummary {
  margin-bottom: 20px;
}

.Form-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.FormControl--subtle {
  margin-top: 10px;
  background: #f8fafc;
}

.Form-help {
  margin-top: 10px;
}

.ColorPicker {
  display: flex;
  gap: 10px;
  align-items: center;
}

.ColorPicker-input {
  width: 60px;
  height: 40px;
  border: 1px solid var(--forum-border-strong);
  border-radius: var(--forum-radius-sm);
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
  border-radius: var(--forum-radius-pill);
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
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  background: var(--forum-bg-elevated);
  color: var(--forum-text-muted);
}

.IconPicker-option:hover {
  border-color: var(--forum-primary-color);
  background: #f7fafe;
}

.IconPicker-option.active {
  border-color: var(--forum-primary-color);
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
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
}

.LinkButton {
  border: 0;
  background: transparent;
  color: var(--forum-primary-color);
  padding: 0;
  font-size: var(--forum-font-size-sm);
  font-weight: 600;
}

.LinkButton:hover {
  color: var(--forum-primary-strong);
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
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-pill);
  background: #fbfdff;
  color: var(--forum-text-muted);
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
    width: 100%;
    max-width: none;
    max-height: calc(100vh - 56px);
  }

  .TagSummaryGrid,
  .TagConfigSummary {
    grid-template-columns: 1fr 1fr;
  }

  .ColorPicker {
    flex-direction: column;
    align-items: stretch;
  }

  .IconPicker {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .Modal-footer {
    flex-direction: column-reverse;
  }

  .Modal-footer .Button {
    width: 100%;
    justify-content: center;
  }
}

@media (max-width: 680px) {
  .TagTable {
    border: 0;
    background: transparent;
  }

  .TagTable thead {
    display: none;
  }

  .TagTable tbody,
  .TagTable tr,
  .TagTable td {
    display: block;
    width: 100%;
  }

  .TagTable tbody tr {
    margin-bottom: 12px;
    padding: 14px;
    border: 1px solid var(--forum-border-color);
    border-radius: 14px;
    background: var(--forum-bg-elevated);
    box-shadow: 0 10px 26px rgba(28, 46, 67, 0.06);
  }

  .TagTable tbody td {
    padding: 8px 0;
    border-bottom: 1px solid #eef2f6;
  }

  .TagTable tbody td:last-child {
    border-bottom: 0;
    padding-bottom: 0;
  }

  .TagTable tbody td::before {
    content: attr(data-label);
    display: block;
    margin-bottom: 6px;
    color: var(--forum-text-soft);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .TagTable-loading,
  .TagTable-empty {
    display: block;
    padding: 0;
  }

  .TagNameCell {
    padding-left: 0;
  }

  .TagStatusList {
    gap: 6px;
  }

  .TagTable tbody td[data-label='操作'] {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .TagTable tbody td[data-label='操作']::before {
    width: 100%;
  }

  .TagTable tbody td[data-label='操作'] .Button {
    flex: 1 1 calc(50% - 8px);
    justify-content: center;
  }
}

@media (max-width: 560px) {
  .TagSummaryGrid,
  .TagConfigSummary {
    grid-template-columns: 1fr;
  }
}
</style>
