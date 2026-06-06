<template>
  <div class="notification-list">
    <NotificationCard
      v-for="notification in notifications"
      :key="notification.id"
      :notification="notification"
      :format-date="formatDate"
      :get-avatar-color="getAvatarColor"
      :get-avatar-initial="getAvatarInitial"
      :get-display-name="getDisplayName"
      :get-icon-class="getIconClass"
      :get-message-html="getMessageHtml"
      :get-presentation="getPresentation"
      @click="$emit('click', notification)"
      @mark-read="$emit('mark-read', $event)"
      @delete="$emit('delete', $event)"
    />
  </div>
</template>

<script setup>
import NotificationCard from './NotificationCard.vue'

defineProps({
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
  notifications: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['click', 'mark-read', 'delete'])
</script>

<style scoped>
.notification-list {
  display: grid;
  gap: 14px;
}
</style>
