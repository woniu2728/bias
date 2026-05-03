<template>
  <div class="auth-page">
    <div class="auth-container">
      <div class="auth-card">
        <h2>重置密码</h2>
        <p class="subtitle">输入新的密码以完成重置。如果你是通过邮件打开页面，令牌会自动填入。</p>

        <form @submit.prevent="handleSubmit">
          <div class="form-group">
            <label for="reset-password-token">重置令牌</label>
            <input
              id="reset-password-token"
              v-model="form.token"
              name="token"
              type="text"
              placeholder="请输入邮件中的重置令牌"
              autocomplete="one-time-code"
              required
            />
          </div>

          <div class="form-group">
            <label for="reset-password-new">新密码</label>
            <input
              id="reset-password-new"
              v-model="form.password"
              name="password"
              type="password"
              placeholder="请输入新密码"
              autocomplete="new-password"
              minlength="6"
              required
            />
          </div>

          <div class="form-group">
            <label for="reset-password-confirm">确认新密码</label>
            <input
              id="reset-password-confirm"
              v-model="form.passwordConfirm"
              name="password_confirm"
              type="password"
              placeholder="请再次输入新密码"
              autocomplete="new-password"
              minlength="6"
              required
            />
          </div>

          <div v-if="error" class="error-message">{{ error }}</div>
          <div v-if="success" class="success-message">{{ success }}</div>

          <button type="submit" class="primary full-width" :disabled="loading">
            {{ loading ? '提交中...' : '重置密码' }}
          </button>
        </form>

        <div class="auth-footer">
          <router-link to="/login" class="link">返回登录</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/api'

const route = useRoute()
const router = useRouter()

const form = reactive({
  token: route.query.token?.toString() || '',
  password: '',
  passwordConfirm: ''
})

const loading = ref(false)
const error = ref('')
const success = ref('')

watch(
  () => route.query.token,
  (value) => {
    form.token = value?.toString() || ''
  }
)

async function handleSubmit() {
  error.value = ''
  success.value = ''

  if (form.password !== form.passwordConfirm) {
    error.value = '两次输入的新密码不一致'
    return
  }

  loading.value = true
  try {
    await api.post('/users/reset-password', {
      token: form.token,
      password: form.password
    })

    success.value = '密码已重置，正在返回登录页...'
    setTimeout(() => {
      router.push('/login')
    }, 1500)
  } catch (err) {
    error.value = err.response?.data?.error || '重置失败，请检查令牌或稍后重试'
  } finally {
    loading.value = false
  }
}
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
