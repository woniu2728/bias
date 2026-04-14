<template>
  <div class="notification-page">
    <div class="container">
      <div class="notification-card">
        <div class="header">
          <h1>通知</h1>
          <button
            v-if="notifications.length > 0"
            @click="markAllAsRead"
            class="secondary"
            :disabled="marking"
          >
            全部标记为已读
          </button>
        </div>

        <section class="preferences-panel">
          <div class="preferences-panel-header">
            <div>
              <h2>通知偏好</h2>
              <p>控制自动关注和关注讨论的新回复通知。</p>
            </div>
            <button @click="savePreferences" class="secondary" :disabled="loadingPreferences || savingPreferences">
              {{ savingPreferences ? '保存中...' : '保存设置' }}
            </button>
          </div>

          <div v-if="loadingPreferences" class="preferences-loading">加载偏好中...</div>
          <div v-else class="preferences-list">
            <label class="preference-item">
              <span class="preference-copy">
                <strong>回复后自动关注</strong>
                <small>参与讨论后，自动把该讨论加入关注列表。</small>
              </span>
              <input v-model="preferences.follow_after_reply" type="checkbox">
            </label>

            <label class="preference-item">
              <span class="preference-copy">
                <strong>发起讨论后自动关注</strong>
                <small>你创建的新讨论会默认出现在关注中。</small>
              </span>
              <input v-model="preferences.follow_after_create" type="checkbox">
            </label>

            <label class="preference-item">
              <span class="preference-copy">
                <strong>关注讨论有新回复时通知我</strong>
                <small>关闭后，仍会保留关注状态，但不再接收新回复通知。</small>
              </span>
              <input v-model="preferences.notify_new_post" type="checkbox">
            </label>
          </div>
        </section>

        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="notifications.length === 0" class="empty">
          <div class="empty-icon">🔔</div>
          <p>暂无通知</p>
        </div>
        <div v-else class="notification-list">
          <div
            v-for="notification in notifications"
            :key="notification.id"
            class="notification-item"
            :class="{ 'is-read': notification.is_read }"
            @click="handleNotificationClick(notification)"
          >
            <div class="notification-icon">
              {{ getNotificationIcon(notification.type) }}
            </div>

            <div class="notification-content">
              <div class="notification-message">
                {{ getNotificationMessage(notification) }}
              </div>
              <div class="notification-time">
                {{ formatDate(notification.created_at) }}
              </div>
            </div>

            <div class="notification-actions">
              <button
                v-if="!notification.is_read"
                @click.stop="markAsRead(notification.id)"
                class="mark-read-btn"
                title="标记为已读"
              >
                ✓
              </button>
              <button
                @click.stop="deleteNotification(notification.id)"
                class="delete-btn"
                title="删除"
              >
                ×
              </button>
            </div>
          </div>
        </div>

        <!-- 分页 -->
        <div v-if="totalPages > 1" class="pagination">
          <button
            @click="changePage(currentPage - 1)"
            :disabled="currentPage === 1"
            class="secondary"
          >
            上一页
          </button>
          <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页</span>
          <button
            @click="changePage(currentPage + 1)"
            :disabled="currentPage === totalPages"
            class="secondary"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'
import api from '@/api'
import { buildDiscussionPath, formatRelativeTime, unwrapList } from '@/utils/forum'

const router = useRouter()
const authStore = useAuthStore()
const notificationStore = useNotificationStore()

const notifications = ref([])
const loading = ref(true)
const marking = ref(false)
const currentPage = ref(1)
const totalPages = ref(1)
const loadingPreferences = ref(true)
const savingPreferences = ref(false)
const preferences = reactive({
  follow_after_reply: false,
  follow_after_create: false,
  notify_new_post: true
})

onMounted(async () => {
  await Promise.all([loadNotifications(), loadPreferences()])
})

async function loadNotifications() {
  loading.value = true
  try {
    const data = await api.get('/notifications', {
      params: { page: currentPage.value }
    })
    notifications.value = unwrapList(data)
    totalPages.value = Math.max(1, Math.ceil((data.total || notifications.value.length) / (data.limit || 20)))
    notificationStore.unreadCount = data.unread_count || 0
  } catch (error) {
    console.error('加载通知失败:', error)
  } finally {
    loading.value = false
  }
}

async function markAsRead(notificationId) {
  try {
    await api.post(`/notifications/${notificationId}/read`)
    const notification = notifications.value.find(n => n.id === notificationId)
    if (notification) {
      notification.is_read = true
      notificationStore.unreadCount = Math.max(0, notificationStore.unreadCount - 1)
    }
  } catch (error) {
    console.error('标记失败:', error)
  }
}

async function markAllAsRead() {
  marking.value = true
  try {
    await api.post('/notifications/read-all')
    notifications.value.forEach(n => {
      n.is_read = true
    })
    notificationStore.unreadCount = 0
  } catch (error) {
    console.error('标记失败:', error)
  } finally {
    marking.value = false
  }
}

async function deleteNotification(notificationId) {
  if (!confirm('确定要删除这条通知吗？')) return

  try {
    const notification = notifications.value.find(n => n.id === notificationId)
    await api.delete(`/notifications/${notificationId}`)
    notifications.value = notifications.value.filter(n => n.id !== notificationId)
    if (notification && !notification.is_read) {
      notificationStore.unreadCount = Math.max(0, notificationStore.unreadCount - 1)
    }
  } catch (error) {
    console.error('删除失败:', error)
  }
}

function handleNotificationClick(notification) {
  // 标记为已读
  if (!notification.is_read) {
    markAsRead(notification.id)
  }

  // 跳转到相关页面
  if (notification.data?.discussion_id && notification.data?.post_number) {
    router.push(`/d/${notification.data.discussion_id}?near=${notification.data.post_number}`)
  } else if (notification.data?.discussion_id) {
    router.push(buildDiscussionPath(notification.data.discussion_id))
  } else if (notification.data?.post_id) {
    router.push(buildDiscussionPath(notification.data.discussion_id || ''))
  }
}

async function loadPreferences() {
  loadingPreferences.value = true
  try {
    const data = await api.get('/users/me/preferences')
    preferences.follow_after_reply = Boolean(data.follow_after_reply)
    preferences.follow_after_create = Boolean(data.follow_after_create)
    preferences.notify_new_post = Boolean(data.notify_new_post)
    if (authStore.user) {
      authStore.user.preferences = { ...data }
    }
  } catch (error) {
    console.error('加载通知偏好失败:', error)
  } finally {
    loadingPreferences.value = false
  }
}

async function savePreferences() {
  savingPreferences.value = true
  try {
    const data = await api.patch('/users/me/preferences', {
      follow_after_reply: preferences.follow_after_reply,
      follow_after_create: preferences.follow_after_create,
      notify_new_post: preferences.notify_new_post
    })
    if (authStore.user) {
      authStore.user.preferences = { ...data }
    }
  } catch (error) {
    console.error('保存通知偏好失败:', error)
    alert('保存失败，请稍后重试')
  } finally {
    savingPreferences.value = false
  }
}

function changePage(page) {
  currentPage.value = page
  loadNotifications()
  window.scrollTo(0, 0)
}

function getNotificationIcon(type) {
  const icons = {
    discussionReply: '💬',
    postLiked: '❤️',
    userMentioned: '@',
    postReply: '↩️',
    discussionCreated: '📝',
    postCreated: '💭',
    default: '🔔'
  }
  return icons[type] || icons.default
}

function getNotificationMessage(notification) {
  const { type, data, from_user: fromUser } = notification

  switch (type) {
    case 'discussionReply':
      return `${fromUser?.username || '有人'} 回复了你的讨论 "${data?.discussion_title || ''}"`
    case 'postLiked':
      return `${fromUser?.username || '有人'} 点赞了你的回复`
    case 'userMentioned':
      return `${fromUser?.username || '有人'} 在回复中提到了你`
    case 'postReply':
      return `${fromUser?.username || '有人'} 回复了你的帖子`
    case 'discussionCreated':
      return `${fromUser?.username || '有人'} 发起了新讨论 "${data?.discussion_title || ''}"`
    case 'postCreated':
      return `${fromUser?.username || '有人'} 发表了新回复`
    default:
      return notification.message || '你有新通知'
  }
}

function formatDate(dateString) {
  return formatRelativeTime(dateString)
}
</script>

<style scoped>
.notification-page {
  padding: 30px 0;
  background: #f5f5f5;
  min-height: calc(100vh - 200px);
}

.notification-card {
  background: white;
  padding: 30px;
  border-radius: 8px;
  max-width: 800px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 25px;
  padding-bottom: 20px;
  border-bottom: 2px solid #f0f0f0;
}

.header h1 {
  font-size: 28px;
  color: #333;
}

.notification-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preferences-panel {
  margin-bottom: 24px;
  padding: 22px 24px;
  border: 1px solid #e5ebf0;
  border-radius: 10px;
  background: #fafcfd;
}

.preferences-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}

.preferences-panel-header h2 {
  font-size: 18px;
  color: #24313f;
  margin-bottom: 6px;
}

.preferences-panel-header p,
.preferences-loading {
  color: #6d7c89;
}

.preferences-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preference-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 8px;
  background: white;
  border: 1px solid #e7edf2;
}

.preference-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: #324150;
}

.preference-copy small {
  color: #7d8b97;
}

.preference-item input {
  width: 18px;
  height: 18px;
  accent-color: #4d698e;
  flex-shrink: 0;
}

.notification-item {
  display: flex;
  align-items: flex-start;
  gap: 15px;
  padding: 18px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  background: white;
}

.notification-item:hover {
  border-color: #667eea;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.1);
}

.notification-item.is-read {
  background: #fafafa;
  opacity: 0.7;
}

.notification-icon {
  font-size: 24px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0ff;
  border-radius: 50%;
  flex-shrink: 0;
}

.notification-content {
  flex: 1;
}

.notification-message {
  color: #333;
  line-height: 1.6;
  margin-bottom: 6px;
}

.notification-time {
  font-size: 13px;
  color: #999;
}

.notification-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.mark-read-btn,
.delete-btn {
  width: 28px;
  height: 28px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all 0.2s;
}

.mark-read-btn:hover {
  border-color: #667eea;
  color: #667eea;
  background: #f0f0ff;
}

.delete-btn:hover {
  border-color: #e74c3c;
  color: #e74c3c;
  background: #fee;
}

.loading, .empty {
  text-align: center;
  padding: 60px 20px;
  color: #666;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
  opacity: 0.3;
}

.empty p {
  font-size: 16px;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 20px;
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid #f0f0f0;
}

.page-info {
  color: #666;
}

@media (max-width: 768px) {
  .notification-card {
    padding: 20px;
  }

  .header {
    flex-direction: column;
    align-items: flex-start;
    gap: 15px;
  }

  .notification-item {
    padding: 15px;
  }

  .notification-icon {
    width: 36px;
    height: 36px;
    font-size: 20px;
  }

  .preferences-panel-header,
  .preference-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
