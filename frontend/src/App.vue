<template>
  <div id="app">
    <Header />
    <main class="main-content">
      <router-view />
    </main>
    <Footer />
    <DiscussionComposer />
    <PostComposer />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import Header from './components/Header.vue'
import Footer from './components/Footer.vue'
import DiscussionComposer from './components/DiscussionComposer.vue'
import PostComposer from './components/PostComposer.vue'
import { useAuthStore } from './stores/auth'
import { useNotificationStore } from './stores/notification'

const authStore = useAuthStore()
const notificationStore = useNotificationStore()

onMounted(() => {
  // 初始化认证状态
  authStore.checkAuth()

  // 如果已登录，连接WebSocket
  if (authStore.isAuthenticated) {
    notificationStore.connect()
  }
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background: #f5f8fa;
  color: #333;
  font-size: 14px;
  line-height: 1.6;
}

:root {
  --forum-primary-color: #4d698e;
  --forum-accent-color: #e74c3c;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1;
}

a {
  color: var(--forum-primary-color);
  text-decoration: none;
}

a:hover {
  text-decoration: underline;
}

button {
  cursor: pointer;
  border: none;
  padding: 8px 16px;
  border-radius: 3px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
  font-family: inherit;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button.primary {
  background: var(--forum-primary-color);
  color: white;
}

button.primary:hover:not(:disabled) {
  filter: brightness(0.92);
}

button.secondary {
  background: #e3e8ed;
  color: #555;
}

button.secondary:hover:not(:disabled) {
  background: #d3d8dd;
}

button.danger {
  background: #e74c3c;
  color: white;
}

button.danger:hover:not(:disabled) {
  background: #c0392b;
}

button.full-width {
  width: 100%;
}

input, textarea, select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 13px;
  font-family: inherit;
}

input:focus, textarea:focus, select:focus {
  outline: none;
  border-color: var(--forum-primary-color);
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}
</style>
