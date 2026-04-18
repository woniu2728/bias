<template>
  <div class="notification-page">
    <div class="container">
      <div class="notification-card">
        <div class="header">
          <h1>通知</h1>
          <div class="header-actions">
            <button
              v-if="notifications.length > 0"
              @click="markAllAsRead"
              class="secondary"
              :disabled="marking"
            >
              全部标记为已读
            </button>
            <router-link to="/profile" class="preferences-link">
              通知偏好请前往个人设置
            </router-link>
          </div>
        </div>

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
              <div class="notification-message" v-html="getNotificationMessageHtml(notification)"></div>
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useModalStore } from '@/stores/modal'
import { useNotificationStore } from '@/stores/notification'
import api from '@/api'
import { buildDiscussionPath, formatRelativeTime, unwrapList } from '@/utils/forum'
import { renderTwemojiText } from '@/utils/twemoji'

const router = useRouter()
const authStore = useAuthStore()
const modalStore = useModalStore()
const notificationStore = useNotificationStore()

const notifications = ref([])
const loading = ref(true)
const marking = ref(false)
const currentPage = ref(1)
const totalPages = ref(1)

onMounted(async () => {
  await loadNotifications()
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
    await notificationStore.markAsRead(notificationId)
    const notification = notifications.value.find(n => n.id === notificationId)
    if (notification) {
      notification.is_read = true
    }
  } catch (error) {
    console.error('标记失败:', error)
  }
}

async function markAllAsRead() {
  marking.value = true
  try {
    await notificationStore.markAllAsRead()
    notifications.value.forEach(n => {
      n.is_read = true
    })
  } catch (error) {
    console.error('标记失败:', error)
  } finally {
    marking.value = false
  }
}

async function deleteNotification(notificationId) {
  const confirmed = await modalStore.confirm({
    title: '删除通知',
    message: '确定要删除这条通知吗？',
    confirmText: '删除',
    cancelText: '取消',
    tone: 'danger'
  })
  if (!confirmed) return

  try {
    await notificationStore.deleteNotification(notificationId)
    notifications.value = notifications.value.filter(n => n.id !== notificationId)
  } catch (error) {
    console.error('删除失败:', error)
    await modalStore.alert({
      title: '删除失败',
      message: error.response?.data?.error || error.message || '请稍后重试',
      tone: 'danger'
    })
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
  } else if (notification.type === 'userSuspended' || notification.type === 'userUnsuspended') {
    router.push('/profile')
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
    discussionApproved: '✅',
    discussionRejected: '⛔',
    postApproved: '✅',
    postRejected: '⛔',
    userSuspended: '🚫',
    userUnsuspended: '🟢',
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
    case 'discussionApproved':
      return `${fromUser?.username || '管理员'} 通过了你的讨论 "${data?.discussion_title || ''}"`
    case 'discussionRejected':
      return `${fromUser?.username || '管理员'} 拒绝了你的讨论 "${data?.discussion_title || ''}"${data?.approval_note ? `：${data.approval_note}` : ''}`
    case 'postApproved':
      return `${fromUser?.username || '管理员'} 通过了你在 "${data?.discussion_title || ''}" 中的回复`
    case 'postRejected':
      return `${fromUser?.username || '管理员'} 拒绝了你在 "${data?.discussion_title || ''}" 中的回复${data?.approval_note ? `：${data.approval_note}` : ''}`
    case 'userSuspended':
      return `${fromUser?.username || '管理员'} 已封禁你的账号${data?.suspend_message ? `：${data.suspend_message}` : ''}`
    case 'userUnsuspended':
      return `${fromUser?.username || '管理员'} 已解除你的账号封禁`
    case 'discussionCreated':
      return `${fromUser?.username || '有人'} 发起了新讨论 "${data?.discussion_title || ''}"`
    case 'postCreated':
      return `${fromUser?.username || '有人'} 发表了新回复`
    default:
      return notification.message || '你有新通知'
  }
}

function getNotificationMessageHtml(notification) {
  return renderTwemojiText(getNotificationMessage(notification))
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.preferences-link {
  color: #6f7f8f;
  font-size: 13px;
}

.preferences-link:hover {
  color: #4d698e;
  text-decoration: none;
}

.notification-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
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

  .header-actions {
    width: 100%;
    flex-direction: column;
    align-items: flex-start;
  }

  .notification-item {
    padding: 15px;
  }

  .notification-icon {
    width: 36px;
    height: 36px;
    font-size: 20px;
  }
}
</style>
