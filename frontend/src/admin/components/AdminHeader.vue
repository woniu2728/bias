<template>
  <header class="AdminHeader">
    <div class="container">
      <div class="AdminHeader-logo">
        <router-link to="/admin">
          <span class="icon">⚙️</span>
          <span class="text">管理后台</span>
        </router-link>
      </div>

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
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../../stores/auth'

const authStore = useAuthStore()

const forumUrl = computed(() => '/')

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

@media (max-width: 768px) {
  .AdminHeader {
    height: 56px;
    min-height: 56px;
  }

  .AdminHeader .container {
    padding: 0 12px;
    align-items: center;
    flex-direction: row;
    gap: 12px;
  }

  .AdminHeader-actions {
    margin-left: auto;
    width: auto;
    justify-content: flex-end;
    gap: 12px;
  }

  .AdminHeader-user {
    min-width: 0;
    justify-content: flex-end;
    gap: 6px;
  }

  .AdminHeader-user span {
    max-width: 92px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .Button--link {
    min-height: 34px;
    padding: 6px 10px;
    border-radius: 999px;
    background: #f4f7fa;
  }
}

@media (max-width: 480px) {
  .AdminHeader-logo a {
    font-size: 15px;
  }

  .AdminHeader-logo .text {
    display: none;
  }

  .AdminHeader-user {
    font-size: 12px;
  }

  .AdminHeader-user span {
    display: none;
  }

  .Button--link {
    padding: 6px 9px;
    font-size: 12px;
  }
}
</style>
