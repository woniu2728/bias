<template>
  <header class="AdminHeader">
    <div class="container">
      <div class="AdminHeader-logo">
        <router-link to="/admin" class="AdminHeader-logoLink">
          <span class="icon">⚙️</span>
          <span class="text">管理后台</span>
        </router-link>
      </div>

      <div class="AdminHeader-mobileTitle">
        {{ activeMeta.label }}
      </div>

      <a :href="forumUrl" class="AdminHeader-mobileBack Button Button--icon" aria-label="返回论坛">
        <i class="fas fa-angle-left"></i>
      </a>

      <div class="AdminHeader-actions">
        <a :href="forumUrl" class="Button Button--link">
          <i class="fas fa-arrow-left"></i>
          返回论坛
        </a>

        <div class="AdminHeader-user">
          <span>{{ authStore.user?.username }}</span>
          <button @click="handleLogout" class="Button Button--link">登出</button>
        </div>
      </div>

      <div class="AdminHeader-mobileActions">
        <button
          type="button"
          class="Button Button--icon AdminHeader-mobileMenuButton"
          :aria-expanded="mobileNavOpen"
          aria-label="打开后台菜单"
          @click="$emit('toggle-nav')"
        >
          <i class="fas fa-ellipsis-h"></i>
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { getAdminRouteMeta } from '../navigation'

defineProps({
  mobileNavOpen: {
    type: Boolean,
    default: false
  }
})

defineEmits(['toggle-nav', 'close-nav'])

const authStore = useAuthStore()
const route = useRoute()

const forumUrl = computed(() => '/')
const activeMeta = computed(() => getAdminRouteMeta(route.path))

function handleLogout() {
  authStore.logout()
  window.location.href = '/login'
}
</script>

<style scoped>
.AdminHeader {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background: white;
  border-bottom: 1px solid #e3e8ed;
  z-index: 1000;
  height: 56px;
}

.AdminHeader .container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 20px;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.AdminHeader-logo a {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #4d698e;
  text-decoration: none;
}

.AdminHeader-mobileTitle,
.AdminHeader-mobileActions,
.AdminHeader-mobileBack {
  display: none;
}

.AdminHeader-logo .icon {
  font-size: 20px;
}

.AdminHeader-actions {
  display: flex;
  align-items: center;
  gap: 20px;
}

.AdminHeader-user {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #666;
  font-size: 14px;
}

.Button--link {
  background: none;
  border: none;
  color: #4d698e;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.Button--link:hover {
  color: #3d5875;
  text-decoration: none;
}

.Button--icon {
  width: 40px;
  height: 40px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
  color: inherit;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 768px) {
  .AdminHeader {
    height: 56px;
    min-height: 56px;
    background: var(--forum-primary-color, #4d698e);
    border-bottom: 1px solid rgba(15, 23, 42, 0.14);
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.14);
    color: #fff;
  }

  .AdminHeader .container {
    padding: 0 12px;
    align-items: center;
    flex-direction: row;
    gap: 12px;
    justify-content: center;
  }

  .AdminHeader-logo {
    display: none;
  }

  .AdminHeader-mobileTitle {
    display: block;
    max-width: calc(100vw - 120px);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 16px;
    font-weight: 700;
    line-height: 56px;
    text-align: center;
    color: #fff;
    text-shadow: 0 1px 1px rgba(15, 23, 42, 0.16);
  }

  .AdminHeader-mobileBack {
    position: absolute;
    left: 10px;
    top: 8px;
    display: inline-flex;
  }

  .AdminHeader-actions {
    display: none;
  }

  .AdminHeader-mobileActions {
    position: absolute;
    inset: 8px 10px 8px auto;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .AdminHeader-mobileBack.Button--icon,
  .AdminHeader-mobileMenuButton {
    background: rgba(255, 255, 255, 0.16);
    border: 1px solid rgba(255, 255, 255, 0.22);
    color: #fff;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
  }

  .AdminHeader-mobileBack.Button--icon:hover,
  .AdminHeader-mobileMenuButton:hover {
    background: rgba(255, 255, 255, 0.22);
  }
}

@media (max-width: 480px) {
  .AdminHeader-mobileTitle {
    max-width: calc(100vw - 108px);
  }
}
</style>
