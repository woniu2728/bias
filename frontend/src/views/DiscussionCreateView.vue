<template>
  <div class="discussion-create-page">
    <div class="container">
      <div class="create-card">
        <h1>发起新讨论</h1>

        <form @submit.prevent="handleSubmit">
          <div v-if="isSuspended" class="suspension-notice">
            {{ suspensionNotice }}
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

            <div v-show="activeTab === 'preview'" class="preview-content" v-html="previewHtml">
            </div>

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

      <!-- 侧边栏提示 -->
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
import { ref, computed, onMounted } from 'vue'
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
const isSuspended = computed(() => Boolean(authStore.user?.is_suspended))

const canSubmit = computed(() => {
  return form.value.title.trim() && form.value.content.trim()
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
  // 简单的Markdown预览（实际应该调用后端API）
  return renderMarkdown(form.value.content)
})

onMounted(async () => {
  await loadTags()
})

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
    console.log('提交数据:', {
      title: form.value.title,
      content: form.value.content,
      tag_ids: form.value.tag_id ? [parseInt(form.value.tag_id)] : []
    })

    const data = await api.post('/discussions/', {
      title: form.value.title,
      content: form.value.content,
      tag_ids: form.value.tag_id ? [parseInt(form.value.tag_id)] : []
    })

    console.log('创建成功:', data)
    // 跳转到新创建的讨论
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
    if (!confirm('确定要放弃当前编辑的内容吗？')) {
      return
    }
  }
  router.push('/discussions')
}

function formatDateTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知时间'
  return date.toLocaleString('zh-CN')
}

// 简单的Markdown渲染（实际应该使用专业库）
function renderMarkdown(text) {
  let html = text
    // 标题
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    // 粗体
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    // 斜体
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // 代码
    .replace(/`(.*?)`/g, '<code>$1</code>')
    // 链接
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    // @提及
    .replace(/@(\w+)/g, '<span class="mention">@$1</span>')
    // 换行
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

.create-card h1 {
  font-size: 28px;
  margin-bottom: 30px;
  color: #333;
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

  .tips-card {
    position: static;
  }
}
</style>
