<template>
  <div class="mobile-drawer-userCard">
    <img
      v-if="authStore.user?.avatar_url"
      :src="authStore.user.avatar_url"
      :alt="authStore.user?.username"
      class="avatar avatar-image"
    />
    <div v-else class="avatar" :style="{ backgroundColor: getUserAvatarColor(authStore.user) }">
      {{ getUserInitial(authStore.user) }}
    </div>
    <div class="mobile-drawer-userMeta">
      <strong>{{ authStore.user?.display_name || authStore.user?.username }}</strong>
      <span>@{{ authStore.user?.username }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  authStore: {
    type: Object,
    required: true
  },
  getUserAvatarColor: {
    type: Function,
    required: true
  },
  getUserInitial: {
    type: Function,
    required: true
  }
})
</script>

<style scoped>
.mobile-drawer-userCard {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: var(--forum-primary-color);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  font-size: 16px;
  font-weight: 700;
}

.avatar-image {
  object-fit: cover;
}

.mobile-drawer-userMeta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mobile-drawer-userMeta strong {
  overflow: hidden;
  color: #233c59;
  font-size: 15px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-drawer-userMeta span {
  overflow: hidden;
  color: #7c8fa4;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
