<template>
  <div class="auth-page">
    <div class="auth-container">
      <div class="auth-card">
        <h2>{{ pageBindings.title }}</h2>
        <p class="subtitle">{{ pageBindings.subtitle }}</p>

        <form @submit.prevent="pageEvents.submit">
          <div class="form-group">
            <label for="reset-password-token">{{ pageBindings.tokenLabelText }}</label>
            <input
              id="reset-password-token"
              v-model="pageBindings.form.token"
              name="token"
              type="text"
              :placeholder="pageBindings.tokenPlaceholderText"
              autocomplete="one-time-code"
              required
            />
          </div>

          <div class="form-group">
            <label for="reset-password-new">{{ pageBindings.newPasswordLabelText }}</label>
            <input
              id="reset-password-new"
              v-model="pageBindings.form.password"
              name="password"
              type="password"
              :placeholder="pageBindings.newPasswordPlaceholderText"
              autocomplete="new-password"
              minlength="6"
              required
            />
          </div>

          <div class="form-group">
            <label for="reset-password-confirm">{{ pageBindings.confirmPasswordLabelText }}</label>
            <input
              id="reset-password-confirm"
              v-model="pageBindings.form.passwordConfirm"
              name="password_confirm"
              type="password"
              :placeholder="pageBindings.confirmPasswordPlaceholderText"
              autocomplete="new-password"
              minlength="6"
              required
            />
          </div>

          <div v-if="pageBindings.error" class="error-message">{{ pageBindings.error }}</div>
          <div v-if="pageBindings.success" class="success-message">{{ pageBindings.success }}</div>

          <button type="submit" class="primary full-width" :disabled="pageBindings.loading">
            {{ pageBindings.submitButtonText }}
          </button>
        </form>

        <div class="auth-footer">
          <router-link to="/login" class="link">{{ pageBindings.backToLoginText }}</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>

import { useRoute, useRouter } from '@bias/core'
import { useResetPasswordViewModel } from './useResetPasswordViewModel'

const route = useRoute()
const router = useRouter()
const {
  pageBindings,
  pageEvents,
} = useResetPasswordViewModel({
  route,
  router,
})
</script>

<style scoped>
.auth-page {
  min-height: calc(100vh - 200px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.auth-container {
  width: 100%;
  max-width: 450px;
}

.auth-card {
  background: white;
  padding: 40px;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.auth-card h2 {
  margin-bottom: 10px;
  color: #333;
  font-size: 28px;
}

.subtitle {
  color: #666;
  margin-bottom: 30px;
  line-height: 1.6;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  color: #333;
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.form-group input:focus {
  outline: none;
  border-color: #667eea;
}

.error-message {
  background: #fee;
  color: #c33;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 20px;
  font-size: 14px;
}

.success-message {
  background: #efe;
  color: #2f7a36;
  padding: 12px;
  border-radius: 6px;
  margin-bottom: 20px;
  font-size: 14px;
}

.full-width {
  width: 100%;
}

.auth-footer {
  text-align: center;
  margin-top: 20px;
}

.link {
  color: #667eea;
}

.link:hover {
  text-decoration: underline;
}
</style>
