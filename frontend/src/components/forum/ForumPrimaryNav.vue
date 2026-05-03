<template>
  <nav class="forum-primary-nav">
    <router-link
      v-for="item in navItems"
      :key="item.key"
      :to="item.to"
      class="forum-primary-nav__item"
      :class="{ active: activeKey === item.key }"
    >
      <i :class="item.icon"></i>
      {{ item.label }}
    </router-link>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { getForumNavItems } from '@/forum/registry'

const props = defineProps({
  activeKey: {
    type: String,
    default: 'home'
  },
  authStore: {
    type: Object,
    required: true
  },
  showNotifications: {
    type: Boolean,
    default: true
  }
})

const navItems = computed(() => getForumNavItems({
  authStore: props.authStore,
  showNotifications: props.showNotifications,
}))
</script>

<style scoped>
.forum-primary-nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.forum-primary-nav__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: var(--forum-radius-sm);
  color: var(--forum-text-muted);
}

.forum-primary-nav__item:hover,
.forum-primary-nav__item.active {
  background: var(--forum-primary-color);
  color: var(--forum-text-inverse);
  text-decoration: none;
}
</style>
