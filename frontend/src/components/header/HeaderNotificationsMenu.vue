<template>
  <div class="notifications-dropdown" :class="{ 'is-open': showNotifications }">
    <button
      type="button"
      class="header-icon"
      :class="{ 'has-unread': notificationStore.unreadCount > 0 }"
      :aria-expanded="showNotifications"
      @click.stop="$emit('toggle')"
    >
      <i class="fas fa-bell"></i>
      <span v-if="notificationStore.unreadCount > 0" class="badge">
        {{ notificationStore.unreadCount }}
      </span>
    </button>

    <div v-if="showNotifications" class="notifications-menu">
      <div class="notifications-menu-header">
        <span>通知</span>
        <div class="notifications-menu-actions">
          <button
            type="button"
            class="notifications-menu-action"
            title="全部标记为已读"
            :disabled="notificationStore.unreadCount === 0 || notificationStore.loading || markingAllRead || clearingRead"
            @click.stop="$emit('mark-all-read')"
          >
            <i :class="markingAllRead ? 'fas fa-spinner fa-spin' : 'fas fa-check'"></i>
          </button>
          <button
            type="button"
            class="notifications-menu-action"
            title="清除已读通知"
            :disabled="!hasReadNotifications || notificationStore.loading || markingAllRead || clearingRead"
            @click.stop="$emit('clear-read')"
          >
            <i :class="clearingRead ? 'fas fa-spinner fa-spin' : 'fas fa-trash-alt'"></i>
          </button>
        </div>
      </div>

      <div
        v-if="actionMessage"
        class="notifications-menu-feedback"
        :class="`notifications-menu-feedback--${actionTone}`"
      >
        {{ actionMessage }}
      </div>

      <div v-if="notificationTypeSummaries.length" class="notifications-summary-strip">
        <button
          v-for="item in notificationTypeSummaries"
          :key="item.type"
          type="button"
          class="notifications-summary-chip"
          @click="$emit('open-type', item.type)"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.unread > 0 ? `${item.unread} 未读` : item.total }}</strong>
        </button>
      </div>

      <div v-if="notificationStore.loading" class="notifications-menu-state">
        加载中...
      </div>
      <div v-else-if="!notificationItems.length" class="notifications-menu-state notifications-menu-state--empty">
        暂无通知
      </div>
      <div v-else class="notifications-menu-list">
        <section
          v-for="group in notificationGroups"
          :key="group.key"
          class="notification-group"
        >
          <button
            type="button"
            class="notification-group-header"
            @click="$emit('open-group', group)"
          >
            {{ group.title }}
          </button>

          <button
            v-for="notification in group.items"
            :key="notification.id"
            type="button"
            class="notification-entry"
            :class="{ 'is-read': notification.is_read }"
            @click="$emit('notification-click', notification)"
          >
            <span class="notification-entry-icon">
              <img
                v-if="notification.from_user?.avatar_url"
                :src="notification.from_user.avatar_url"
                :alt="notification.from_user.display_name || notification.from_user.username"
              />
              <i v-else :class="getNotificationIconClass(notification.type)"></i>
            </span>
            <span class="notification-entry-main">
              <span class="notification-entry-message" v-html="getNotificationTextHtml(notification)"></span>
              <span class="notification-entry-time">{{ formatRelativeTime(notification.created_at) }}</span>
            </span>
            <span v-if="!notification.is_read" class="notification-entry-unread"></span>
          </button>
        </section>
      </div>

      <div v-if="notificationItems.length" class="notifications-menu-footer">
        <button type="button" class="notifications-footer-link" @click="$emit('open-page')">
          查看全部通知
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  showNotifications: {
    type: Boolean,
    default: false
  },
  notificationStore: {
    type: Object,
    required: true
  },
  notificationItems: {
    type: Array,
    default: () => []
  },
  notificationGroups: {
    type: Array,
    default: () => []
  },
  notificationTypeSummaries: {
    type: Array,
    default: () => []
  },
  hasReadNotifications: {
    type: Boolean,
    default: false
  },
  actionMessage: {
    type: String,
    default: ''
  },
  actionTone: {
    type: String,
    default: 'info'
  },
  markingAllRead: {
    type: Boolean,
    default: false
  },
  clearingRead: {
    type: Boolean,
    default: false
  },
  getNotificationIconClass: {
    type: Function,
    required: true
  },
  getNotificationTextHtml: {
    type: Function,
    required: true
  },
  formatRelativeTime: {
    type: Function,
    required: true
  }
})

defineEmits([
  'toggle',
  'mark-all-read',
  'clear-read',
  'open-group',
  'open-type',
  'notification-click',
  'open-page'
])
</script>

<style scoped>
.header-icon {
  position: relative;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.header-icon:hover {
  background: #f5f8fa;
  color: #333;
}

.header-icon.has-unread {
  color: var(--forum-primary-color);
}

.badge {
  position: absolute;
  top: 6px;
  right: 6px;
  background: #e74c3c;
  color: white;
  border-radius: 10px;
  padding: 2px 5px;
  font-size: 10px;
  font-weight: 600;
  min-width: 16px;
  text-align: center;
  line-height: 1;
}

.notifications-dropdown {
  position: relative;
}

.notifications-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 420px;
  max-height: min(70vh, 640px);
  background: white;
  border: 1px solid #dbe2ea;
  border-radius: 6px;
  box-shadow: 0 14px 36px rgba(35, 45, 56, 0.18);
  overflow: hidden;
  z-index: 1000;
}

.notifications-menu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #e6ebf1;
  color: #5b6f86;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.notifications-menu-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.notifications-menu-action {
  border: 0;
  background: transparent;
  color: #73859a;
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  padding: 0;
}

.notifications-menu-action:hover:not(:disabled) {
  background: #f3f6f9;
  color: #44576d;
}

.notifications-menu-action:disabled {
  opacity: 0.42;
  cursor: not-allowed;
}

.notifications-menu-feedback {
  padding: 10px 16px;
  border-bottom: 1px solid #e6ebf1;
  font-size: 12px;
  line-height: 1.5;
}

.notifications-menu-feedback--info {
  background: #f6f9fc;
  color: #5c7188;
}

.notifications-menu-feedback--success {
  background: #eef8f1;
  color: #2f6b43;
}

.notifications-menu-feedback--danger {
  background: #fdf1f0;
  color: #b24b47;
}

.notifications-summary-strip {
  display: flex;
  gap: 8px;
  padding: 10px 12px 0;
  overflow-x: auto;
}

.notifications-summary-chip {
  border: 1px solid #dbe5ee;
  background: #f8fbfd;
  color: #42576c;
  border-radius: 999px;
  padding: 7px 10px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.notifications-summary-chip strong {
  font-size: 12px;
  color: #1f3d5c;
}

.notifications-menu-state {
  padding: 32px 18px;
  color: #73859a;
  font-size: 14px;
  text-align: center;
}

.notifications-menu-state--empty {
  min-height: 156px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.notifications-menu-list {
  max-height: min(70vh, 560px);
  overflow-y: auto;
}

.notification-group {
  border-top: 1px solid #e8edf2;
  margin-top: -1px;
}

.notification-group-header {
  width: 100%;
  border: 0;
  background: transparent;
  color: #1f2d3d;
  text-align: left;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.notification-group-header:hover {
  background: #f7fafc;
}

.notification-entry {
  width: 100%;
  border: 0;
  background: white;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #eef2f6;
  position: relative;
}

.notification-entry:last-child {
  border-bottom: 0;
}

.notification-entry:hover {
  background: #f7fafc;
}

.notification-entry.is-read {
  color: #7f8d9b;
}

.notification-entry-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #edf2f7;
  color: #62758a;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.notification-entry-icon img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.notification-entry-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.notification-entry-message {
  color: #2e3e50;
  font-size: 13px;
  line-height: 1.45;
}

.notification-entry.is-read .notification-entry-message {
  color: #677889;
}

.notification-entry-time {
  color: #8593a0;
  font-size: 12px;
}

.notification-entry-unread {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e36f2d;
  margin-top: 5px;
  flex-shrink: 0;
}

.notifications-menu-footer {
  border-top: 1px solid #e6ebf1;
  padding: 10px 16px 12px;
}

.notifications-footer-link {
  width: 100%;
  border: 0;
  background: transparent;
  color: #4d698e;
  font-size: 13px;
  font-weight: 600;
  padding: 0;
  text-align: center;
}

.notifications-footer-link:hover {
  color: #3f5876;
}
</style>
