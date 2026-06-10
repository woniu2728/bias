<template>
  <div class="auth-page">
    <div class="auth-container">
      <div class="auth-card">
        <h2>{{ pageBindings.title }}</h2>
        <p class="subtitle">{{ pageBindings.subtitle }}</p>

        <div class="status-box" :class="pageBindings.statusClass">
          {{ pageBindings.statusText }}
        </div>

        <div class="actions">
          <router-link to="/login" class="primary action-link">{{ pageBindings.loginActionText }}</router-link>
          <router-link to="/profile" class="secondary action-link">{{ pageBindings.profileActionText }}</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useAuthStore } from '@bias/users'
import { useRoute } from '@bias/core'

import { useVerifyEmailViewModel } from './useVerifyEmailViewModel'

const route = useRoute()
const authStore = useAuthStore()
const { pageBindings } = useVerifyEmailViewModel({
  authStore,
  route,
})
</script>

<style scoped>
.auth-page {
  min-height: calc(100vh - 200px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  background: linear-gradient(135deg, #d7e6f5 0%, #f4f8fb 100%);
}

.auth-container {
  width: 100%;
  max-width: 520px;
}

.auth-card {
  background: white;
  padding: 40px;
  border-radius: 12px;
  box-shadow: 0 16px 42px rgba(47, 60, 77, 0.12);
}

.auth-card h2 {
  margin-bottom: 10px;
  color: #24313f;
  font-size: 28px;
}

.subtitle {
  color: #667684;
  margin-bottom: 24px;
  line-height: 1.6;
}

.status-box {
  padding: 16px 18px;
  border-radius: 10px;
  background: #f5f8fa;
  color: #556270;
  line-height: 1.7;
}

.status-success {
  background: #edf8f1;
  color: #1f7a45;
}

.status-error {
  background: #fdf0f0;
  color: #b03a37;
}

.actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.action-link {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
}

.action-link:hover {
  text-decoration: none;
}
</style>
