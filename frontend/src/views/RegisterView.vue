<template>
  <div class="auth-page">
    <div class="auth-container">
      <div class="auth-card">
        <h2>注册</h2>
        <p class="subtitle">加入我们的社区，并通过邮件完成邮箱验证</p>

        <form @submit.prevent="handleRegister">
          <div class="form-group">
            <label>用户名</label>
            <input
              v-model="form.username"
              type="text"
              placeholder="请输入用户名"
              required
              minlength="3"
              maxlength="30"
            />
            <small>3-30个字符</small>
          </div>

          <div class="form-group">
            <label>邮箱</label>
            <input
              v-model="form.email"
              type="email"
              placeholder="请输入邮箱"
              required
            />
          </div>

          <div class="form-group">
            <label>密码</label>
            <input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              required
              minlength="6"
            />
            <small>至少6个字符</small>
          </div>

          <div class="form-group">
            <label>确认密码</label>
            <input
              v-model="form.password_confirm"
              type="password"
              placeholder="请再次输入密码"
              required
            />
          </div>

          <div v-if="error" class="error-message">{{ error }}</div>
          <div v-if="success" class="success-message">{{ success }}</div>

          <button type="submit" class="primary full-width" :disabled="loading">
            {{ loading ? '注册中...' : '注册' }}
          </button>
        </form>

        <div class="auth-footer">
          已有账号？
          <router-link to="/login" class="link">立即登录</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({
  username: '',
  email: '',
  password: '',
  password_confirm: ''
})

const loading = ref(false)
const error = ref('')
const success = ref('')

async function handleRegister() {
  loading.value = true
  error.value = ''
  success.value = ''

  // 验证密码
  if (form.value.password !== form.value.password_confirm) {
    error.value = '两次输入的密码不一致'
    loading.value = false
    return
  }

  try {
    const result = await authStore.register(
      form.value.username,
      form.value.email,
      form.value.password
    )

    if (!result.success) {
      error.value = result.error || '注册失败，请稍后重试'
      return
    }

    success.value = '注册成功！请检查邮箱完成验证，正在跳转到登录页...'

    // 2秒后跳转到登录页
    setTimeout(() => {
      router.push('/login')
    }, 2000)
  } catch (err) {
    if (err.response?.data) {
      const data = err.response.data
      if (data.username) {
        error.value = `用户名: ${data.username[0]}`
      } else if (data.email) {
        error.value = `邮箱: ${data.email[0]}`
      } else if (data.password) {
        error.value = `密码: ${data.password[0]}`
      } else {
        error.value = data.detail || '注册失败，请稍后重试'
      }
    } else {
      error.value = '注册失败，请稍后重试'
    }
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
  box-shadow: 0 10px 40px rgba(0,0,0,0.2);
}

.auth-card h2 {
  margin-bottom: 10px;
  color: #333;
  font-size: 28px;
}

.subtitle {
  color: #666;
  margin-bottom: 30px;
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

.form-group small {
  display: block;
  margin-top: 5px;
  color: #999;
  font-size: 12px;
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
  color: #3c3;
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
  color: #666;
  font-size: 14px;
}

.link {
  color: #667eea;
}

.link:hover {
  text-decoration: underline;
}
</style>
