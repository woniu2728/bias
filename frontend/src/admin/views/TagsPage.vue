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
              <th style="width: 180px">预览</th>
              <th>标签名称</th>
              <th>别名</th>
              <th>描述</th>
              <th>讨论数</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="6" class="TagTable-loading">加载中...</td>
            </tr>
            <tr v-else-if="tags.length === 0">
              <td colspan="6" class="TagTable-empty">暂无标签</td>
            </tr>
            <tr v-for="tag in tags" v-else :key="tag.id">
              <td>
                <span class="TagBadgePreview" :style="getTagBadgeStyle(tag.color)">
                  <i v-if="tag.icon" :class="tag.icon"></i>
                  <span>{{ tag.name }}</span>
                </span>
              </td>
              <td>
                <strong>{{ tag.name }}</strong>
              </td>
              <td>{{ tag.slug }}</td>
              <td>{{ tag.description || '-' }}</td>
              <td>{{ tag.discussion_count }}</td>
              <td>
                <button @click="editTag(tag)" class="Button Button--small">
                  编辑
                </button>
                <button @click="deleteTag(tag)" class="Button Button--small Button--danger">
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
            <p class="Modal-subtitle">参考 Flarum 的标签编辑流程，提供实时颜色和图标预览。</p>
          </div>
          <button @click="closeModal" class="Modal-close">
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="Modal-body">
          <div class="TagPreviewPanel">
            <span class="TagPreviewPanel-label">实时预览</span>
            <div class="TagPreviewPanel-card">
              <span class="TagBadgePreview TagBadgePreview--large" :style="getTagBadgeStyle(formData.color)">
                <i v-if="formData.icon" :class="formData.icon"></i>
                <span>{{ formData.name || '新标签' }}</span>
              </span>
              <small>{{ formData.description || '这里会显示标签在讨论列表中的视觉效果。' }}</small>
            </div>
          </div>

          <div class="Form-group">
            <label>标签名称 *</label>
            <input
              v-model="formData.name"
              type="text"
              class="FormControl"
              placeholder="例如：技术讨论"
            />
          </div>

          <div class="Form-group">
            <label>描述</label>
            <textarea
              v-model="formData.description"
              class="FormControl"
              rows="3"
              placeholder="标签的简短描述"
            ></textarea>
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
              v-model="formData.icon"
              type="text"
              class="FormControl FormControl--subtle"
              placeholder="高级模式：手动输入 Font Awesome 类名"
            />
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

const formData = ref({
  name: '',
  description: '',
  color: '#888888',
  icon: '',
})

const filteredIconOptions = computed(() => {
  const query = iconSearch.value.trim().toLowerCase()
  if (!query) return TAG_ICON_OPTIONS

  return TAG_ICON_OPTIONS.filter(icon =>
    icon.label.toLowerCase().includes(query) || icon.value.toLowerCase().includes(query)
  )
})

onMounted(() => {
  loadTags()
})

async function loadTags() {
  loading.value = true
  try {
    const data = await api.get('/admin/tags')
    tags.value = data
  } catch (error) {
    console.error('加载标签失败:', error)
  } finally {
    loading.value = false
  }
}

function openCreateModal() {
  iconSearch.value = ''
  showCreateModal.value = true
}

function editTag(tag) {
  editingTag.value = tag
  iconSearch.value = ''
  formData.value = {
    name: tag.name,
    description: tag.description,
    color: tag.color,
    icon: tag.icon,
  }
  showEditModal.value = true
}

async function saveTag() {
  if (!formData.value.name) {
    alert('请输入标签名称')
    return
  }

  saving.value = true
  try {
    if (showEditModal.value) {
      await api.put(`/admin/tags/${editingTag.value.id}`, formData.value)
    } else {
      await api.post('/admin/tags', formData.value)
    }

    closeModal()
    loadTags()
  } catch (error) {
    console.error('保存标签失败:', error)
    const errorMsg = error.response?.data?.error
      || error.response?.data?.detail
      || error.message
      || '未知错误'
    alert('保存失败: ' + errorMsg)
  } finally {
    saving.value = false
  }
}

async function deleteTag(tag) {
  if (!confirm(`确定要删除标签"${tag.name}"吗？这将影响 ${tag.discussion_count} 个讨论。`)) {
    return
  }

  try {
    await api.delete(`/admin/tags/${tag.id}`)
    loadTags()
  } catch (error) {
    alert('删除失败: ' + (error.response?.data?.error || '未知错误'))
  }
}

function closeModal() {
  showCreateModal.value = false
  showEditModal.value = false
  editingTag.value = null
  iconSearch.value = ''
  formData.value = {
    name: '',
    description: '',
    color: '#888888',
    icon: '',
  }
}

function normalizeColor(value) {
  return String(value || '').trim().toLowerCase()
}

function getTagBadgeStyle(color) {
  return {
    '--tag-bg': color || '#888888',
  }
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

.TagBadgePreview i {
  font-size: 12px;
}

.TagBadgePreview--large {
  min-height: 38px;
  padding: 0 14px;
  font-size: 14px;
}

.Modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
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
  overflow: auto;
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
  gap: 10px;
  padding: 16px 18px;
  border: 1px solid #e3e8ed;
  border-radius: 12px;
  background: linear-gradient(180deg, #fbfdff, #f4f7fa);
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

@media (max-width: 768px) {
  .Modal-content {
    width: calc(100vw - 24px);
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
