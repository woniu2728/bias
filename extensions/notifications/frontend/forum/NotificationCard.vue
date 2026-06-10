<template>
  <article
    class="notification-item"
    :class="{ 'is-read': notification.is_read }"
    @click="$emit('click', notification)"
  >
    <div class="notification-avatar" :style="{ backgroundColor: getAvatarColor(notification) }">
      <img
        v-if="notification.from_user?.avatar_url"
        :src="notification.from_user.avatar_url"
        :alt="getDisplayName(notification.from_user)"
      />
      <span v-else>{{ getAvatarInitial(notification) }}</span>
    </div>

    <div class="notification-main">
      <div class="notification-title-row">
        <div class="notification-title">
          <i :class="resolvePresentation(notification).iconClass || getIconClass(notification.type)"></i>
          <span v-html="resolvePresentation(notification).messageHtml || getMessageHtml(notification)"></span>
        </div>
        <span v-if="!notification.is_read" class="notification-unread-dot"></span>
      </div>

      <div class="notification-meta">
        <span>{{ formatDate(notification.created_at) }}</span>
        <span v-if="resolvePresentation(notification).metaText">{{ resolvePresentation(notification).metaText }}</span>
      </div>
    </div>

    <div class="notification-actions">
      <button
        v-if="!notification.is_read"
        type="button"
        class="notification-action"
        :title="markReadTitleText"
        @click.stop="$emit('mark-read', notification.id)"
      >
        <i class="fas fa-check"></i>
      </button>
      <button
        type="button"
        class="notification-action notification-action--danger"
        :title="deleteTitleText"
        @click.stop="$emit('delete', notification.id)"
      >
        <i class="fas fa-xmark"></i>
      </button>
    </div>
  </article>
</template>

<script setup>
import { computed } from '@bias/core'
import { getUiCopy } from '@bias/forum'

const props = defineProps({
  formatDate: {
    type: Function,
    required: true,
  },
  getAvatarColor: {
    type: Function,
    required: true,
  },
  getAvatarInitial: {
    type: Function,
    required: true,
  },
  getDisplayName: {
    type: Function,
    required: true,
  },
  getIconClass: {
    type: Function,
    required: true,
  },
  getMessageHtml: {
    type: Function,
    required: true,
  },
  getPresentation: {
    type: Function,
    default: null,
  },
  notification: {
    type: Object,
    required: true,
  },
})

defineEmits(['click', 'mark-read', 'delete'])

const markReadTitleText = computed(() => getUiCopy({
  surface: 'notification-card-mark-read',
})?.text || '标记为已读')

const deleteTitleText = computed(() => getUiCopy({
  surface: 'notification-card-delete',
})?.text || '删除通知')

function resolvePresentation(notification) {
  if (typeof props.getPresentation === 'function') {
    return props.getPresentation(notification) || {}
  }

  return {
    iconClass: props.getIconClass(notification.type),
    messageHtml: props.getMessageHtml(notification),
    metaText: notification?.data?.discussion_title || '',
  }
}
</script>

<style scoped>
.notification-item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 16px;
  align-items: flex-start;
  padding: 18px 20px;
  background: var(--forum-bg-elevated);
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  box-shadow: var(--forum-shadow-sm);
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}

.notification-item:hover {
  border-color: color-mix(in srgb, var(--forum-primary-color) 24%, white);
  box-shadow: var(--forum-shadow-md);
  transform: translateY(-1px);
}

.notification-item.is-read {
  opacity: 0.74;
  background: color-mix(in srgb, var(--forum-bg-subtle) 68%, white);
}

.notification-avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  overflow: hidden;
  flex-shrink: 0;
}

.notification-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.notification-main {
  min-width: 0;
}

.notification-title-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  justify-content: space-between;
}

.notification-title {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: var(--forum-text-color);
  line-height: 1.6;
  min-width: 0;
  overflow-wrap: anywhere;
}

.notification-title i {
  color: var(--forum-primary-color);
  margin-top: 3px;
  flex-shrink: 0;
}

.notification-title :deep(img.emoji) {
  height: 1.15em;
  width: 1.15em;
  vertical-align: -0.2em;
}

.notification-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  margin-top: 8px;
  color: var(--forum-text-soft);
  font-size: 12px;
  min-width: 0;
  overflow-wrap: anywhere;
}

.notification-unread-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--forum-accent-color);
  flex-shrink: 0;
  margin-top: 7px;
}

.notification-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.notification-action {
  width: 32px;
  height: 32px;
  border: 1px solid var(--forum-border-color);
  border-radius: 50%;
  background: var(--forum-bg-elevated);
  color: var(--forum-text-soft);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.notification-action:hover {
  color: var(--forum-primary-color);
  border-color: color-mix(in srgb, var(--forum-primary-color) 26%, white);
}

.notification-action--danger:hover {
  color: #b03a37;
  border-color: rgba(176, 58, 55, 0.24);
}

@media (max-width: 768px) {
  .notification-item {
    grid-template-columns: auto 1fr;
    gap: 14px 12px;
    padding: 16px;
  }

  .notification-actions {
    grid-column: 2;
    justify-content: flex-end;
  }

  .notification-title-row {
    gap: 8px;
  }
}

@media (max-width: 520px) {
  .notification-item {
    gap: 12px 10px;
    padding: 14px;
  }

  .notification-avatar {
    width: 36px;
    height: 36px;
    font-size: 14px;
  }
}
</style>
