<template>
  <div class="discussion-create-page">
    <div class="container">
      <div class="create-card">
        <div class="create-card-header">
          <div>
            <h1>发起新讨论</h1>
            <p class="create-subtitle">标题、标签和正文会自动保存为草稿，刷新页面后可以继续编辑。</p>
          </div>
          <div class="draft-actions">
            <span v-if="draftSavedAt" class="draft-status">草稿保存于 {{ formatDraftTime(draftSavedAt) }}</span>
            <button type="button" class="secondary" @click="saveDraft">
              保存草稿
            </button>
            <button type="button" class="secondary" @click="clearDraft" :disabled="!hasDraftContent">
              清除草稿
            </button>
          </div>
        </div>

        <form @submit.prevent="handleSubmit">
          <div v-if="isSuspended" class="suspension-notice">
            {{ suspensionNotice }}
          </div>
          <div v-else-if="draftMessage" class="draft-banner">
            {{ draftMessage }}
          </div>

          <div class="form-group">
            <label>标题 *</label>
            <input
              v-model="form.title"
              type="text"
              placeholder="输入讨论标题..."
              required
              maxlength="200"
            />
            <small>{{ form.title.length }}/200</small>
          </div>

          <div class="form-group">
            <label>标签 *</label>
            <select v-model="form.tag_id" class="tag-select" required>
              <option value="">请选择标签</option>
              <option v-for="tag in tags" :key="tag.id" :value="tag.id">
                {{ tag.name }}
              </option>
            </select>
          </div>

          <div class="form-group">
            <label>内容 *</label>
            <div class="editor-tabs">
              <button
                type="button"
                class="tab"
                :class="{ active: activeTab === 'write' }"
                @click="activeTab = 'write'"
              >
                编辑
              </button>
              <button
                type="button"
                class="tab"
                :class="{ active: activeTab === 'preview' }"
                @click="activeTab = 'preview'"
              >
                预览
              </button>
            </div>

            <textarea
              v-show="activeTab === 'write'"
              v-model="form.content"
              placeholder="输入讨论内容... 支持Markdown语法"
              rows="15"
              required
            ></textarea>

            <div v-show="activeTab === 'preview'" class="preview-content" v-html="previewHtml"></div>

            <div class="editor-help">
              <small>
                支持Markdown语法：**粗体** *斜体* `代码` [链接](url) @用户名
              </small>
            </div>
          </div>

          <div v-if="error" class="error-message">{{ error }}</div>

          <div class="form-actions">
            <button type="submit" class="primary" :disabled="submitting || !canSubmit || isSuspended">
              {{ submitting ? '发布中...' : '发布讨论' }}
            </button>
            <button type="button" class="secondary" @click="handleCancel">
              取消
            </button>
          </div>
        </form>
      </div>

      <aside class="tips-card">
        <h3>发帖指南</h3>
        <ul>
          <li>标题要简洁明了，准确描述问题</li>
          <li>选择合适的标签，方便他人查找</li>
          <li>内容要详细，提供足够的上下文</li>
          <li>使用Markdown格式化文本</li>
          <li>遵守社区规则，友善交流</li>
        </ul>

        <h3>Markdown语法</h3>
        <div class="markdown-examples">
          <code># 标题</code>
          <code>**粗体**</code>
          <code>*斜体*</code>
          <code>`代码`</code>
          <code>[链接](url)</code>
          <code>@用户名</code>
          <code>```代码块```</code>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/api'
import { flattenTags, normalizeTag, unwrapList } from '@/utils/forum'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({
  title: '',
  content: '',
  tag_id: ''
})

const tags = ref([])
const activeTab = ref('write')
const submitting = ref(false)
const error = ref('')
const draftSavedAt = ref('')
const draftMessage = ref('')
const isSuspended = computed(() => Boolean(authStore.user?.is_suspended))
let draftTimer = null

const canSubmit = computed(() => {
  return form.value.title.trim() && form.value.content.trim()
})

const hasDraftContent = computed(() => {
  return Boolean(form.value.title.trim() || form.value.content.trim() || form.value.tag_id)
})

const suspensionNotice = computed(() => {
  if (!isSuspended.value) return ''

  const user = authStore.user || {}
  if (user.suspend_message) {
    return user.suspended_until
      ? `账号已被封禁至 ${formatDateTime(user.suspended_until)}。${user.suspend_message}`
      : `账号当前已被封禁。${user.suspend_message}`
  }

  return user.suspended_until
    ? `账号已被封禁至 ${formatDateTime(user.suspended_until)}，暂时无法发布讨论。`
    : '账号当前已被封禁，暂时无法发布讨论。'
})

const previewHtml = computed(() => {
  if (!form.value.content) {
    return '<p class="empty-preview">暂无内容</p>'
  }
  return renderMarkdown(form.value.content)
})

onMounted(async () => {
  await loadTags()
  restoreDraft()
})

onBeforeUnmount(() => {
  if (draftTimer) {
    clearTimeout(draftTimer)
  }
})

watch(
  form,
  () => {
    scheduleDraftSave()
  },
  { deep: true }
)

async function loadTags() {
  try {
    const data = await api.get('/tags', {
      params: {
        include_children: true
      }
    })
    tags.value = flattenTags(unwrapList(data).map(normalizeTag))
  } catch (error) {
    console.error('加载标签失败:', error)
  }
}

async function handleSubmit() {
  if (!canSubmit.value) return
  if (isSuspended.value) {
    error.value = suspensionNotice.value
    return
  }

  submitting.value = true
  error.value = ''

  try {
    const data = await api.post('/discussions/', {
      title: form.value.title,
      content: form.value.content,
      tag_ids: form.value.tag_id ? [parseInt(form.value.tag_id)] : []
    })

    if (data.approval_status === 'pending') {
      alert('讨论已提交审核，管理员通过后会显示在论坛列表中。')
    }

    clearDraftStorage()
    router.push(`/d/${data.id}`)
  } catch (err) {
    console.error('创建失败:', err)
    if (err.response?.data) {
      const data = err.response.data
      if (data.title) {
        error.value = `标题: ${data.title[0]}`
      } else if (data.content) {
        error.value = `内容: ${data.content[0]}`
      } else if (data.error) {
        error.value = data.error
      } else if (data.detail) {
        error.value = data.detail
      } else {
        error.value = JSON.stringify(data)
      }
    } else {
      error.value = err.message || '发布失败，请稍后重试'
    }
  } finally {
    submitting.value = false
  }
}

function handleCancel() {
  if (form.value.title || form.value.content) {
    if (!confirm('确定要放弃当前编辑的内容吗？已保存的草稿会继续保留。')) {
      return
    }
  }
  router.push('/discussions')
}

function getDraftKey() {
  return `pyflarum:create-discussion-draft:${authStore.user?.id || 'guest'}`
}

function restoreDraft() {
  if (typeof window === 'undefined') return

  const raw = window.localStorage.getItem(getDraftKey())
  if (!raw) return

  try {
    const draft = JSON.parse(raw)
    form.value = {
      title: draft.title || '',
      content: draft.content || '',
      tag_id: draft.tag_id || ''
    }
    draftSavedAt.value = draft.updatedAt || ''
    draftMessage.value = draftSavedAt.value
      ? `已恢复你在 ${formatDraftTime(draftSavedAt.value)} 保存的讨论草稿。`
      : '已恢复本地讨论草稿。'
  } catch (error) {
    console.error('恢复讨论草稿失败:', error)
  }
}

function scheduleDraftSave() {
  if (draftTimer) {
    clearTimeout(draftTimer)
  }

  draftTimer = setTimeout(() => {
    saveDraft(false)
  }, 300)
}

function saveDraft(showMessage = true) {
  if (typeof window === 'undefined') return

  if (!hasDraftContent.value) {
    clearDraftStorage(showMessage ? '草稿已清空' : '')
    return
  }

  const updatedAt = new Date().toISOString()
  window.localStorage.setItem(
    getDraftKey(),
    JSON.stringify({
      title: form.value.title,
      content: form.value.content,
      tag_id: form.value.tag_id,
      updatedAt,
    })
  )
  draftSavedAt.value = updatedAt
  draftMessage.value = showMessage ? '讨论草稿已保存。' : ''
}

function clearDraft() {
  form.value = {
    title: '',
    content: '',
    tag_id: ''
  }
  clearDraftStorage('已清除本地草稿。')
}

function clearDraftStorage(message = '') {
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(getDraftKey())
  }
  draftSavedAt.value = ''
  draftMessage.value = message
}

function formatDraftTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '刚刚'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function formatDateTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知时间'
  return date.toLocaleString('zh-CN')
}

function renderMarkdown(text) {
  let html = text
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    .replace(/@(\w+)/g, '<span class="mention">@$1</span>')
    .replace(/\n/g, '<br>')

  return html
}
</script>

<style scoped>
.discussion-create-page {
  padding: 30px 0;
  background: #f5f5f5;
  min-height: calc(100vh - 200px);
}

.container {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 30px;
}

.create-card {
  background: white;
  padding: 40px;
  border-radius: 8px;
}

.create-card-header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 30px;
}

.create-card h1 {
  font-size: 28px;
  margin-bottom: 8px;
  color: #333;
}

.create-subtitle {
  color: #6d7b88;
  line-height: 1.6;
}

.draft-actions {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.draft-status {
  color: #7a8895;
  font-size: 12px;
  padding-top: 8px;
}

.draft-banner {
  margin-bottom: 20px;
  padding: 14px 16px;
  border-radius: 8px;
  background: #edf4fb;
  color: #325b88;
  line-height: 1.6;
}

.form-group {
  margin-bottom: 25px;
}

.form-group label {
  display: block;
  margin-bottom: 10px;
  color: #333;
  font-weight: 500;
  font-size: 15px;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 16px;
  transition: border-color 0.2s;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #667eea;
}

.tag-select {
  background: white;
  cursor: pointer;
}

.editor-tabs {
  display: flex;
  gap: 5px;
  margin-bottom: 10px;
}

.tab {
  padding: 8px 20px;
  background: #f5f5f5;
  border: none;
  border-radius: 6px 6px 0 0;
  cursor: pointer;
  transition: all 0.2s;
  color: #666;
}

.tab:hover {
  background: #e0e0e0;
}

.tab.active {
  background: white;
  color: #667eea;
  font-weight: 500;
}

.form-group textarea {
  width: 100%;
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 15px;
  font-family: inherit;
  resize: vertical;
  line-height: 1.6;
}

.form-group textarea:focus {
  outline: none;
  border-color: #667eea;
}

.preview-content {
  min-height: 400px;
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: #fafafa;
  line-height: 1.6;
}

.preview-content :deep(h1) {
  font-size: 24px;
  margin: 15px 0;
}

.preview-content :deep(h2) {
  font-size: 20px;
  margin: 12px 0;
}

.preview-content :deep(h3) {
  font-size: 18px;
  margin: 10px 0;
}

.preview-content :deep(code) {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
}

.preview-content :deep(.mention) {
  color: #667eea;
  font-weight: 500;
}

.preview-content :deep(a) {
  color: #667eea;
  text-decoration: underline;
}

.empty-preview {
  color: #999;
  text-align: center;
  padding: 40px;
}

.editor-help {
  margin-top: 10px;
}

.editor-help small {
  color: #999;
}

.error-message {
  background: #fee;
  color: #c33;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 20px;
  font-size: 14px;
}

.suspension-notice {
  margin-bottom: 20px;
  padding: 14px 16px;
  border-radius: 8px;
  background: #fff3cd;
  color: #856404;
  line-height: 1.6;
}

.form-actions {
  display: flex;
  gap: 15px;
}

.tips-card {
  background: white;
  padding: 25px;
  border-radius: 8px;
  height: fit-content;
  position: sticky;
  top: 20px;
}

.tips-card h3 {
  font-size: 16px;
  margin-bottom: 15px;
  color: #333;
}

.tips-card ul {
  list-style: none;
  padding: 0;
  margin: 0 0 25px 0;
}

.tips-card li {
  padding: 8px 0;
  color: #666;
  font-size: 14px;
  line-height: 1.5;
}

.tips-card li:before {
  content: "• ";
  color: #667eea;
  font-weight: bold;
  margin-right: 8px;
}

.markdown-examples {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.markdown-examples code {
  display: block;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 13px;
  color: #666;
}

@media (max-width: 768px) {
  .container {
    grid-template-columns: 1fr;
  }

  .create-card-header {
    flex-direction: column;
  }

  .draft-actions {
    justify-content: flex-start;
  }

  .tips-card {
    position: static;
  }
}
</style>
