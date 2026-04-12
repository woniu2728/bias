<template>
  <Teleport to="body">
    <div
      v-if="showComposer"
      class="floating-composer"
      :class="{ 'is-minimized': composerStore.isMinimized, 'is-expanded': composerStore.isExpanded }"
      :style="composerInlineStyle"
    >
      <div class="composer-handle" aria-hidden="true" @mousedown.prevent="startResize"></div>
      <div class="composer-header">
        <div class="composer-title">
          <span>{{ composerTitle }}</span>
          <small>
            <router-link :to="discussionLink" class="composer-link" @click="handleHeaderLinkClick">
              {{ composerSubtitle }}
            </router-link>
          </small>
        </div>
        <div class="composer-controls">
          <button
            v-if="!isEditing"
            type="button"
            title="保存草稿"
            :disabled="submitting"
            @click="saveComposerDraft()"
          >
            <i class="far fa-save"></i>
          </button>
          <button
            type="button"
            :title="composerStore.isMinimized ? '展开' : '最小化'"
            @click="toggleComposerMinimized"
          >
            <i :class="composerStore.isMinimized ? 'far fa-window-restore' : 'fas fa-minus minimize'"></i>
          </button>
          <button
            type="button"
            :title="composerStore.isExpanded ? '退出全屏' : '全屏'"
            @click="toggleComposerExpanded"
          >
            <i :class="composerStore.isExpanded ? 'fas fa-compress' : 'fas fa-expand'"></i>
          </button>
          <button type="button" title="关闭" @click="closeComposer">
            <i class="fas fa-times"></i>
          </button>
        </div>
      </div>

      <div v-show="!composerStore.isMinimized" class="composer-body">
        <textarea
          ref="composerTextarea"
          v-model="replyContent"
          placeholder="输入你的回复... 支持 Markdown、@用户名 和代码块"
          rows="7"
        ></textarea>

        <div class="composer-toolbar">
          <button
            type="button"
            class="composer-submit"
            :disabled="submitting || !replyContent.trim()"
            @click="submitReply"
          >
            <i class="fas fa-paper-plane"></i>
            {{ submitting ? '提交中...' : (isEditing ? '更新回复' : '发布回复') }}
          </button>

          <div class="composer-formatting" aria-label="格式化工具栏">
            <button
              v-for="tool in composerTools"
              :key="tool.key"
              type="button"
              :title="tool.title"
              @click="applyComposerTool(tool)"
            >
              <i v-if="tool.icon" :class="tool.icon"></i>
              <span v-else>{{ tool.label }}</span>
            </button>
          </div>

          <button
            v-if="composerDraftSavedAt && !isEditing"
            type="button"
            class="composer-secondary"
            @click="clearComposerDraft"
          >
            清除草稿
          </button>
          <button v-if="isEditing" type="button" class="composer-secondary" @click="cancelEdit">取消编辑</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import api from '@/api'
import { normalizePost } from '@/utils/forum'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()

const replyContent = ref('')
const submitting = ref(false)
const composerTextarea = ref(null)
const composerDraftSavedAt = ref('')
const composerHeight = ref(loadComposerHeight())
const resizing = ref(false)
let resizeStartY = 0
let resizeStartHeight = composerHeight.value

const composerTools = [
  { key: 'upload', title: '附件占位', icon: 'fas fa-file-upload' },
  { key: 'heading', title: '标题', label: 'H', before: '## ', after: '' },
  { key: 'bold', title: '加粗', label: 'B', before: '**', after: '**' },
  { key: 'italic', title: '斜体', label: 'I', before: '*', after: '*' },
  { key: 'strike', title: '删除线', label: 'S', before: '~~', after: '~~' },
  { key: 'quote', title: '引用', icon: 'fas fa-quote-left' },
  { key: 'spoiler', title: '提示/警告', icon: 'fas fa-exclamation-triangle', before: '> **提示：** ', after: '' },
  { key: 'code', title: '代码', icon: 'fas fa-code', before: '`', after: '`' },
  { key: 'link', title: '链接', icon: 'fas fa-link' },
  { key: 'image', title: '图片', icon: 'fas fa-image' },
  { key: 'bullets', title: '无序列表', icon: 'fas fa-list-ul' },
  { key: 'ordered', title: '有序列表', icon: 'fas fa-list-ol' },
  { key: 'mention', title: '@ 提及', icon: 'fas fa-at', before: '@', after: '' },
  { key: 'emoji', title: '表情', icon: 'far fa-smile', before: '😊', after: '' }
]

const showComposer = computed(() => {
  return composerStore.isOpen && ['reply', 'edit'].includes(composerStore.current.type) && authStore.isAuthenticated
})
const isEditing = computed(() => composerStore.current.type === 'edit')
const discussionId = computed(() => Number(composerStore.current.discussionId || 0))
const discussionLink = computed(() => {
  if (!discussionId.value) return '/'
  if (composerStore.current.postNumber) {
    return `/d/${discussionId.value}?near=${composerStore.current.postNumber}`
  }
  return `/d/${discussionId.value}`
})
const composerTitle = computed(() => {
  if (isEditing.value) return `编辑 #${composerStore.current.postNumber || ''}`.trim()
  if (composerStore.current.postNumber) return `回复 #${composerStore.current.postNumber}`
  return `回复：${composerStore.current.discussionTitle || '讨论'}`
})
const composerSubtitle = computed(() => {
  if (isEditing.value) {
    return `${composerStore.current.discussionTitle || '讨论'} · 编辑后会直接更新原帖`
  }
  if (composerDraftSavedAt.value) return `草稿已保存于 ${formatDraftTime(composerDraftSavedAt.value)}`
  if (composerStore.current.username) {
    return `${composerStore.current.discussionTitle || '讨论'} · @${composerStore.current.username}`
  }
  return composerStore.current.discussionTitle || '讨论'
})
const composerInlineStyle = computed(() => {
  if (composerStore.isMinimized || composerStore.isExpanded) return {}
  return { height: `${composerHeight.value}px` }
})

watch(
  () => composerStore.current.requestId,
  async () => {
    if (!showComposer.value) return

    if (isEditing.value) {
      composerDraftSavedAt.value = ''
      replyContent.value = composerStore.current.initialContent || ''
    } else if (composerStore.current.initialContent?.trim()) {
      composerDraftSavedAt.value = ''
      replyContent.value = composerStore.current.initialContent
    } else {
      restoreComposerDraft()
    }

    await nextTick()
    if (!composerStore.isMinimized) {
      composerTextarea.value?.focus()
    }
  }
)

watch(
  () => authStore.isAuthenticated,
  value => {
    if (!value) {
      resetComposerState()
    }
  }
)

onMounted(() => {
  window.addEventListener('mousemove', handleResizeMove)
  window.addEventListener('mouseup', stopResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', handleResizeMove)
  window.removeEventListener('mouseup', stopResize)
})

function handleHeaderLinkClick() {
  if (composerStore.isExpanded) {
    composerStore.toggleExpanded()
    composerStore.showComposer()
  }
}

function startResize(event) {
  if (composerStore.isExpanded || composerStore.isMinimized || window.innerWidth <= 768) return

  resizing.value = true
  resizeStartY = event.clientY
  resizeStartHeight = composerHeight.value
}

function handleResizeMove(event) {
  if (!resizing.value) return

  const delta = resizeStartY - event.clientY
  composerHeight.value = clampComposerHeight(resizeStartHeight + delta)
}

function stopResize() {
  if (!resizing.value) return
  resizing.value = false
  persistComposerHeight(composerHeight.value)
}

function toggleComposerMinimized() {
  composerStore.toggleMinimized()
  if (!composerStore.isMinimized) {
    nextTick(() => composerTextarea.value?.focus())
  }
}

function toggleComposerExpanded() {
  composerStore.toggleExpanded()
  nextTick(() => composerTextarea.value?.focus())
}

function closeComposer(force = false) {
  if (!force && replyContent.value.trim() && !confirm('确定要关闭回复框吗？当前草稿会被清空。')) {
    return
  }

  resetComposerState()
}

function cancelEdit() {
  closeComposer(true)
}

function resetComposerState() {
  composerStore.closeComposer()
  composerDraftSavedAt.value = ''
  replyContent.value = ''
}

function getComposerDraftKey() {
  if (!discussionId.value || isEditing.value) return null
  return `pyflarum:discussion:${discussionId.value}:draft:${authStore.user?.id || 'guest'}`
}

function restoreComposerDraft() {
  if (typeof window === 'undefined') return false

  composerDraftSavedAt.value = ''
  const key = getComposerDraftKey()
  if (!key) return false

  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) {
      replyContent.value = ''
      return false
    }

    const draft = JSON.parse(raw)
    if (!draft?.content?.trim()) {
      replyContent.value = ''
      return false
    }

    replyContent.value = draft.content
    composerDraftSavedAt.value = draft.updatedAt || ''
    return true
  } catch (error) {
    console.error('恢复草稿失败:', error)
    replyContent.value = ''
    return false
  }
}

function saveComposerDraft() {
  if (typeof window === 'undefined' || isEditing.value) return

  const key = getComposerDraftKey()
  if (!key) return

  const content = replyContent.value.trim()
  if (!content) {
    window.localStorage.removeItem(key)
    composerDraftSavedAt.value = ''
    return
  }

  const updatedAt = new Date().toISOString()
  window.localStorage.setItem(
    key,
    JSON.stringify({
      content: replyContent.value,
      updatedAt
    })
  )
  composerDraftSavedAt.value = updatedAt
}

function clearComposerDraft() {
  if (typeof window === 'undefined') return

  const key = getComposerDraftKey()
  if (!key) return

  window.localStorage.removeItem(key)
  composerDraftSavedAt.value = ''
}

async function applyComposerTool(tool) {
  composerStore.showComposer()
  await nextTick()

  const textarea = composerTextarea.value
  if (!textarea) return

  const start = textarea.selectionStart ?? replyContent.value.length
  const end = textarea.selectionEnd ?? replyContent.value.length
  const selected = replyContent.value.slice(start, end)
  const replacement = buildComposerToolReplacement(tool, selected)

  replyContent.value = `${replyContent.value.slice(0, start)}${replacement}${replyContent.value.slice(end)}`

  await nextTick()
  textarea.focus()
  const cursor = selected
    ? start + replacement.length
    : start + defaultToolCursorOffset(tool)
  textarea.setSelectionRange(cursor, cursor)
}

function buildComposerToolReplacement(tool, selected) {
  if (tool.key === 'link') {
    return selected ? `[${selected}](https://)` : '[链接文字](https://)'
  }
  if (tool.key === 'image') {
    return selected ? `![图片描述](${selected})` : '![图片描述](https://)'
  }
  if (tool.key === 'upload') {
    return selected ? `[附件说明](${selected})` : '[附件说明](上传后的附件地址)'
  }
  if (tool.key === 'quote') {
    return prefixLines(selected || '引用内容', '> ')
  }
  if (tool.key === 'bullets') {
    return prefixLines(selected || '列表项', '- ')
  }
  if (tool.key === 'ordered') {
    return prefixOrderedLines(selected || '列表项')
  }

  const before = tool.before || ''
  const after = tool.after || ''
  return `${before}${selected || defaultToolText(tool)}${after}`
}

function defaultToolCursorOffset(tool) {
  const replacement = buildComposerToolReplacement(tool, '')
  if (tool.key === 'image') return replacement.indexOf('https://') + 'https://'.length
  if (tool.key === 'upload') return replacement.indexOf('上传后的附件地址')
  if (tool.key === 'link') return replacement.indexOf('链接文字') + '链接文字'.length
  if (tool.key === 'emoji') return replacement.length
  return replacement.length
}

function prefixLines(content, prefix) {
  return content
    .split('\n')
    .map(line => `${prefix}${line || '内容'}`)
    .join('\n')
}

function prefixOrderedLines(content) {
  return content
    .split('\n')
    .map((line, index) => `${index + 1}. ${line || '内容'}`)
    .join('\n')
}

function defaultToolText(tool) {
  if (tool.key === 'link') return '链接文字'
  if (tool.key === 'code') return 'code'
  if (tool.key === 'heading') return '标题'
  if (tool.key === 'upload') return '附件'
  if (tool.key === 'image') return 'https://'
  if (tool.key === 'emoji') return ''
  return '文本'
}

async function submitReply() {
  if (!replyContent.value.trim() || !discussionId.value) return

  submitting.value = true
  try {
    if (isEditing.value) {
      const data = await api.patch(`/posts/${composerStore.current.postId}`, {
        content: replyContent.value
      })
      const post = normalizePost(data)
      window.dispatchEvent(new CustomEvent('pyflarum:post-updated', {
        detail: {
          discussionId: discussionId.value,
          post
        }
      }))

      if (!isViewingCurrentDiscussion()) {
        await router.push(`/d/${discussionId.value}?near=${post.number || composerStore.current.postNumber || 1}`)
      }
    } else {
      const data = await api.post(`/discussions/${discussionId.value}/posts`, {
        content: replyContent.value
      })
      const post = normalizePost(data)
      window.dispatchEvent(new CustomEvent('pyflarum:reply-created', {
        detail: {
          discussionId: discussionId.value,
          post
        }
      }))

      if (post.approval_status === 'pending') {
        alert('回复已提交审核，管理员通过后会向其他用户显示。')
      }

      if (!isViewingCurrentDiscussion()) {
        await router.push(`/d/${discussionId.value}?near=${post.number || 1}`)
      }

      clearComposerDraft()
    }

    resetComposerState()
  } catch (error) {
    console.error('提交失败:', error)
    alert('提交失败: ' + (error.response?.data?.error || error.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

function isViewingCurrentDiscussion() {
  return route.name === 'discussion-detail' && Number(route.params.id) === discussionId.value
}

function formatDraftTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '刚刚'

  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit'
  })
}

function loadComposerHeight() {
  if (typeof window === 'undefined') return 420
  const value = Number(window.localStorage.getItem('pyflarum:composer-height:post') || 420)
  return clampComposerHeight(value)
}

function persistComposerHeight(value) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem('pyflarum:composer-height:post', String(clampComposerHeight(value)))
}

function clampComposerHeight(value) {
  const min = 280
  const max = typeof window === 'undefined' ? 680 : Math.max(320, window.innerHeight - 72)
  return Math.max(min, Math.min(value, max))
}
</script>

<style scoped>
.floating-composer {
  position: fixed;
  left: 50%;
  bottom: 18px;
  transform: translateX(-50%);
  width: min(760px, calc(100vw - 32px));
  background: #f7f9fb;
  border: 1px solid #dbe2ea;
  border-radius: 10px 10px 0 0;
  box-shadow: 0 2px 8px rgba(31, 45, 61, 0.18);
  z-index: 900;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.floating-composer.is-minimized {
  width: min(540px, calc(100vw - 32px));
}

.floating-composer.is-expanded {
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  transform: none;
  width: auto;
  border-radius: 0;
  box-shadow: none;
}

.composer-handle {
  height: 14px;
  cursor: row-resize;
}

.composer-handle::before {
  content: '';
  display: block;
  width: 64px;
  height: 4px;
  border-radius: 999px;
  background: #d7dee6;
  margin: 6px auto 0;
}

.composer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 20px 10px;
  color: #4a5665;
}

.composer-title {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-weight: 400;
}

.composer-title span,
.composer-title small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.composer-title span {
  font-size: 14px;
  color: #445161;
}

.composer-title small {
  color: #7b8794;
  font-size: 12px;
  font-weight: 400;
}

.composer-link {
  color: inherit;
}

.composer-link:hover {
  text-decoration: none;
}

.composer-controls {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.composer-controls button {
  border: 0;
  background: transparent;
  color: #6c7a89;
  border-radius: 4px;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.composer-controls button:hover {
  background: #e8edf3;
  color: #3f4b59;
}

.composer-controls button i {
  font-size: 13px;
}

.composer-controls button:disabled {
  cursor: default;
  opacity: 0.45;
}

.composer-body {
  padding: 0 20px 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.composer-body textarea {
  width: 100%;
  padding: 4px 0 12px;
  border: 0;
  border-radius: 0;
  background: transparent;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.7;
  resize: none;
  min-height: 120px;
  max-height: none;
  flex: 1;
}

.floating-composer.is-expanded .composer-body textarea {
  min-height: calc(100vh - 170px);
  max-height: none;
}

.composer-body textarea:focus {
  outline: none;
  border: 0;
  box-shadow: none;
}

.composer-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 -20px;
  padding: 10px 20px;
  border-top: 1px solid #dbe2ea;
  flex-wrap: nowrap;
}

.composer-submit,
.composer-secondary {
  border: 0;
  border-radius: 4px;
  padding: 8px 14px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.composer-submit {
  background: #4d698e;
  color: white;
  display: flex;
  align-items: center;
  gap: 8px;
}

.composer-submit:disabled {
  cursor: default;
  opacity: 0.6;
}

.composer-submit i {
  font-size: 13px;
}

.composer-formatting {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  white-space: nowrap;
}

.composer-formatting button {
  border: 0;
  background: transparent;
  color: #5b6776;
  border-radius: 4px;
  min-width: 28px;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}

.composer-formatting button:hover {
  background: #e8edf3;
  color: #354152;
}

.composer-formatting button i {
  font-size: 14px;
}

.composer-formatting button span {
  font-weight: 700;
  font-size: 14px;
  line-height: 1;
  white-space: nowrap;
}

.composer-secondary {
  background: transparent;
  color: #6b7786;
}

.composer-secondary:hover {
  background: #e8edf3;
  color: #425062;
}

@media (max-width: 768px) {
  .floating-composer {
    bottom: 0;
    width: 100vw;
    border-radius: 10px 10px 0 0;
  }

  .floating-composer.is-expanded {
    width: 100vw;
  }

  .composer-toolbar {
    align-items: stretch;
    flex-wrap: wrap;
  }

  .composer-submit,
  .composer-secondary {
    justify-content: center;
  }

  .composer-formatting {
    order: 3;
    flex: 0 0 100%;
    padding-bottom: 2px;
  }
}
</style>
