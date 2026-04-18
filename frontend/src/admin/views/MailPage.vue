<template>
  <AdminPage
    className="MailPage"
    icon="fas fa-envelope"
    title="邮件设置"
    description="配置SMTP服务器和邮件模板"
  >
    <form @submit.prevent="handleSubmit" class="Form">
      <div class="Form-section">
        <h3 class="Section-title">SMTP配置</h3>

        <div class="Form-group">
          <label>邮件驱动</label>
          <select v-model="settings.mail_driver" class="FormControl">
            <option value="smtp">SMTP</option>
            <option value="sendmail">Sendmail</option>
            <option value="mailgun">Mailgun</option>
          </select>
        </div>

        <div class="Form-group">
          <label>SMTP主机</label>
          <input
            v-model="settings.mail_host"
            type="text"
            class="FormControl"
            placeholder="smtp.example.com"
          />
        </div>

        <div class="Form-group">
          <label>SMTP端口</label>
          <input
            v-model="settings.mail_port"
            type="number"
            class="FormControl"
            placeholder="587"
          />
        </div>

        <div class="Form-group">
          <label>加密方式</label>
          <select v-model="settings.mail_encryption" class="FormControl">
            <option value="">无</option>
            <option value="tls">TLS</option>
            <option value="ssl">SSL</option>
          </select>
        </div>

        <div class="Form-group">
          <label>用户名</label>
          <input
            v-model="settings.mail_username"
            type="text"
            class="FormControl"
            placeholder="user@example.com"
          />
        </div>

        <div class="Form-group">
          <label>密码</label>
          <input
            v-model="settings.mail_password"
            type="password"
            class="FormControl"
            placeholder="••••••••"
          />
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">发件人信息</h3>

        <div class="Form-group">
          <label>发件人邮箱</label>
          <input
            v-model="settings.mail_from_address"
            type="email"
            class="FormControl"
            placeholder="noreply@example.com"
          />
        </div>

        <div class="Form-group">
          <label>发件人名称</label>
          <input
            v-model="settings.mail_from_name"
            type="text"
            class="FormControl"
            placeholder="Bias"
          />
        </div>
      </div>

      <div class="Form-actions">
        <button
          type="submit"
          class="Button Button--primary"
          :disabled="saving"
        >
          {{ saving ? '保存中...' : '保存设置' }}
        </button>
        <button
          type="button"
          @click="sendTestEmail"
          class="Button"
          :disabled="testing"
        >
          {{ testing ? '发送中...' : '发送测试邮件' }}
        </button>
        <span v-if="saveSuccess" class="Form-success">✓ 保存成功</span>
        <span v-if="saveError" class="Form-error">保存失败，请重试</span>
      </div>
    </form>
  </AdminPage>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import api from '../../api'

const settings = ref({
  mail_driver: 'smtp',
  mail_host: '',
  mail_port: 587,
  mail_encryption: 'tls',
  mail_username: '',
  mail_password: '',
  mail_from_address: '',
  mail_from_name: '',
})

const saving = ref(false)
const testing = ref(false)
const saveSuccess = ref(false)
const saveError = ref(false)

onMounted(async () => {
  try {
    const data = await api.get('/admin/mail')
    settings.value = { ...settings.value, ...data }
  } catch (error) {
    console.error('加载邮件设置失败:', error)
  }
})

async function handleSubmit() {
  saving.value = true
  saveSuccess.value = false
  saveError.value = false

  try {
    await api.post('/admin/mail', settings.value)
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  } catch (error) {
    console.error('保存邮件设置失败:', error)
    saveError.value = true
  } finally {
    saving.value = false
  }
}

async function sendTestEmail() {
  testing.value = true
  try {
    await api.post('/admin/mail/test')
    alert('测试邮件已发送，请检查收件箱')
  } catch (error) {
    alert('发送测试邮件失败: ' + (error.response?.data?.error || '未知错误'))
  } finally {
    testing.value = false
  }
}
</script>

<style scoped>
.Form {
  max-width: 600px;
}

.Form-section {
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
  padding: 20px;
  margin-bottom: 20px;
}

.Section-title {
  margin: 0 0 20px 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  padding-bottom: 10px;
  border-bottom: 1px solid #e3e8ed;
}

.Form-group {
  margin-bottom: 20px;
}

.Form-group:last-child {
  margin-bottom: 0;
}

.Form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #333;
  font-size: 14px;
}

.FormControl {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 14px;
  font-family: inherit;
  transition: border-color 0.2s;
}

.FormControl:focus {
  outline: none;
  border-color: #4d698e;
}

.Form-actions {
  display: flex;
  align-items: center;
  gap: 15px;
  padding-top: 10px;
}

.Button {
  background: #f5f8fa;
  border: 1px solid #ddd;
  padding: 10px 20px;
  border-radius: 3px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.Button:hover:not(:disabled) {
  background: #e8eef5;
  border-color: #4d698e;
}

.Button--primary {
  background: #4d698e;
  color: white;
  border-color: #4d698e;
}

.Button--primary:hover:not(:disabled) {
  background: #3d5875;
}

.Button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.Form-success {
  color: #27ae60;
  font-size: 14px;
  font-weight: 500;
}

.Form-error {
  color: #e74c3c;
  font-size: 14px;
  font-weight: 500;
}
</style>
