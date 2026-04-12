<template>
  <div class="home">
    <!-- Flarum风格：直接重定向到讨论列表 -->
    <div class="flarum-container">
      <div class="welcome-banner">
        <h1>PyFlarum</h1>
        <p>基于Django和Vue 3的现代化论坛</p>
      </div>

      <div class="quick-actions">
        <router-link to="/discussions" class="action-btn primary">
          <span class="icon">💬</span>
          <span>浏览讨论</span>
        </router-link>
        <button v-if="authStore.isAuthenticated" type="button" class="action-btn" @click="handleStartDiscussion">
          <span class="icon">✏️</span>
          <span>发起讨论</span>
        </button>
        <router-link to="/register" v-else class="action-btn">
          <span class="icon">👤</span>
          <span>注册账号</span>
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'

const authStore = useAuthStore()
const composerStore = useComposerStore()

function handleStartDiscussion() {
  composerStore.openDiscussionComposer({
    source: 'home'
  })
}
</script>

<style scoped>
.home {
  min-height: calc(100vh - 200px);
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f8fa;
}

.flarum-container {
  text-align: center;
  max-width: 600px;
  padding: 40px;
}

.welcome-banner {
  margin-bottom: 40px;
}

.welcome-banner h1 {
  font-size: 48px;
  color: #333;
  margin-bottom: 10px;
  font-weight: 300;
}

.welcome-banner p {
  font-size: 18px;
  color: #666;
}

.quick-actions {
  display: flex;
  gap: 15px;
  justify-content: center;
  flex-wrap: wrap;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px 30px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  color: #333;
  font-size: 16px;
  transition: all 0.2s;
  text-decoration: none;
}

.action-btn:hover {
  border-color: #aaa;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  text-decoration: none;
}

.action-btn.primary {
  background: #4d698e;
  color: white;
  border-color: #4d698e;
}

.action-btn.primary:hover {
  background: #3d5875;
  border-color: #3d5875;
}

.icon {
  font-size: 20px;
}
</style>
