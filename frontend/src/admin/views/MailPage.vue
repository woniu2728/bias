<template>
  <AdminPage
    className="MailPage"
    icon="fas fa-envelope"
    title="邮件设置"
    description="配置 Gmail 或其他 SMTP 服务的发信参数。"
  >
    <div v-if="!loaded" class="MailPage-loading">加载中...</div>

    <template v-else>
      <div class="MailContent">
        <form class="Form" @submit.prevent="handleSubmit">
          <div v-if="!configIsSendable" class="StatusAlert">
            当前邮件配置尚不可发送。请先补全发件地址和 SMTP 信息。
          </div>

          <section class="Form-section">
            <div class="Form-sectionHeader">
              <h3>发件设置</h3>
              <p>默认按 Gmail SMTP 预填。若使用 Gmail，密码处需要填写应用专用密码。</p>
            </div>

            <div class="Form-grid">
              <div class="Form-group Form-group--full">
                <label>发件地址</label>
                <input
                  v-model="settings.mail_from"
                  type="text"
                  class="FormControl"
                  placeholder="Bias <your@gmail.com>"
                />
                <p class="Form-hint">支持 `your@gmail.com` 或 `Bias &lt;your@gmail.com&gt;`。</p>
                <div v-if="fieldErrors.mail_from?.length" class="ValidationError">
                  <p v-for="error in fieldErrors.mail_from" :key="error">{{ error }}</p>
                </div>
              </div>

              <div class="Form-group">
                <label>SMTP 主机</label>
                <input
                  v-model="settings.mail_host"
                  type="text"
                  class="FormControl"
                  placeholder="smtp.gmail.com"
                />
                <div v-if="fieldErrors.mail_host?.length" class="ValidationError">
                  <p v-for="error in fieldErrors.mail_host" :key="error">{{ error }}</p>
                </div>
              </div>

              <div class="Form-group">
                <label>SMTP 端口</label>
                <input
                  v-model="settings.mail_port"
                  type="number"
                  class="FormControl"
                  placeholder="587"
                />
                <div v-if="fieldErrors.mail_port?.length" class="ValidationError">
                  <p v-for="error in fieldErrors.mail_port" :key="error">{{ error }}</p>
                </div>
              </div>

              <div class="Form-group">
                <label>加密方式</label>
                <select v-model="settings.mail_encryption" class="FormControl">
                  <option value="">无</option>
                  <option value="tls">TLS</option>
                  <option value="ssl">SSL</option>
                </select>
                <p class="Form-hint">Gmail 通常使用 `TLS + 587`。</p>
                <div v-if="fieldErrors.mail_encryption?.length" class="ValidationError">
                  <p v-for="error in fieldErrors.mail_encryption" :key="error">{{ error }}</p>
                </div>
              </div>

              <div class="Form-group">
                <label>邮件格式</label>
                <select v-model="settings.mail_format" class="FormControl">
                  <option value="multipart">Multipart</option>
                  <option value="plain">Plain Text</option>
                  <option value="html">HTML</option>
                </select>
                <p class="Form-hint">`Multipart` 兼容性最好。</p>
                <div v-if="fieldErrors.mail_format?.length" class="ValidationError">
                  <p v-for="error in fieldErrors.mail_format" :key="error">{{ error }}</p>
                </div>
              </div>

              <div class="Form-group">
                <label>SMTP 用户名</label>
                <input
                  v-model="settings.mail_username"
                  type="text"
                  class="FormControl"
                  placeholder="your@gmail.com"
                />
              </div>

              <div class="Form-group">
                <label>SMTP 密码</label>
                <input
                  v-model="settings.mail_password"
                  type="password"
                  class="FormControl"
                  placeholder="应用专用密码"
                />
                <p class="Form-hint">保存后会按当前输入覆盖运行时密码。</p>
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
              <span v-if="saveSuccess" class="Form-success">✓ 保存成功</span>
              <span v-if="saveError" class="Form-error">保存失败，请检查当前配置</span>
            </div>
          </section>
        </form>

        <section class="Form-section Form-section--test">
          <div class="Form-sectionHeader">
            <h3>发送测试邮件</h3>
            <p>优先发送到你填写的测试收件箱。留空时，会回退到当前管理员邮箱。</p>
          </div>

          <div class="TestMailPanel">
            <div class="Form-group TestMailPanel-input">
              <label>测试收件箱</label>
              <input
                v-model="settings.mail_test_recipient"
                type="email"
                class="FormControl"
                placeholder="admin@example.com"
              />
              <p class="Form-hint">建议填写一个真实可收信邮箱，便于直接验证 SMTP 是否可用。</p>
            </div>

            <div class="TestMailPanel-meta">
              <div class="TestMailPanel-target">
                实际发送到：<strong>{{ effectiveTestToEmail || '（未设置）' }}</strong>
              </div>
              <div v-if="hasUnsavedChanges" class="Form-hint">
                请先保存当前修改，再发送测试邮件。
              </div>
            </div>

            <div class="Form-actions TestMailPanel-actions">
              <button
                type="button"
                class="Button Button--primary"
                :disabled="testing || hasUnsavedChanges || !configIsSendable || !effectiveTestToEmail"
                @click="sendTestEmail"
              >
                {{ testing ? '发送中...' : '发送测试邮件' }}
              </button>
            </div>
          </div>
        </section>
      </div>
    </template>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import api from '../../api'

const defaultSettings = () => ({
  mail_from: '',
  mail_format: 'multipart',
  mail_host: 'smtp.gmail.com',
  mail_port: 587,
  mail_encryption: 'tls',
  mail_username: '',
  mail_password: '',
  mail_test_recipient: '',
})

const settings = ref(defaultSettings())
const fieldErrors = ref({})
const loaded = ref(false)
const fallbackTestToEmail = ref('')
const saving = ref(false)
const testing = ref(false)
const saveSuccess = ref(false)
const saveError = ref(false)
const initialSnapshot = ref('')

const hasUnsavedChanges = computed(() => JSON.stringify(buildConfigPayload()) !== initialSnapshot.value)
const effectiveTestToEmail = computed(() => settings.value.mail_test_recipient || fallbackTestToEmail.value)
const configIsSendable = computed(() => {
  const mailFrom = String(settings.value.mail_from || '').trim()
  const mailHost = String(settings.value.mail_host || '').trim()
  const encryption = String(settings.value.mail_encryption || '').trim().toLowerCase()
  const mailFormat = String(settings.value.mail_format || '').trim().toLowerCase()
  const rawPort = String(settings.value.mail_port || '').trim()
  const port = Number(rawPort)

  return Boolean(
    mailFrom
    && mailHost
    && rawPort
    && Number.isInteger(port)
    && port > 0
    && ['', 'tls', 'ssl'].includes(encryption)
    && ['multipart', 'plain', 'html'].includes(mailFormat)
  )
})

function composeMailFrom(source) {
  const mailFrom = String(source?.mail_from || '').trim()
  if (mailFrom) {
    return mailFrom
  }

  const address = String(source?.mail_from_address || '').trim()
  const name = String(source?.mail_from_name || '').trim()
  if (!address) {
    return ''
  }
  return name ? `${name} <${address}>` : address
}

function buildConfigPayload() {
  return {
    mail_driver: 'smtp',
    mail_from: settings.value.mail_from || '',
    mail_format: settings.value.mail_format || 'multipart',
    mail_host: settings.value.mail_host || '',
    mail_port: settings.value.mail_port || '',
    mail_encryption: settings.value.mail_encryption || '',
    mail_username: settings.value.mail_username || '',
    mail_password: settings.value.mail_password || '',
  }
}

function buildSavePayload() {
  return {
    ...buildConfigPayload(),
    mail_test_recipient: settings.value.mail_test_recipient || '',
  }
}

function applyResponse(data, options = {}) {
  const { preferLocalValues = false } = options
  const source = data?.settings && typeof data.settings === 'object' ? data.settings : data
  const currentValues = { ...settings.value }
  settings.value = {
    ...defaultSettings(),
    ...currentValues,
    ...Object.fromEntries(
      Object.keys(defaultSettings()).map((key) => {
        if (preferLocalValues) {
          return [key, currentValues[key] ?? source?.[key] ?? defaultSettings()[key]]
        }
        return [key, source?.[key] ?? currentValues[key] ?? defaultSettings()[key]]
      })
    ),
  }
  settings.value.mail_from = preferLocalValues
    ? (currentValues.mail_from || composeMailFrom(source) || '')
    : (composeMailFrom(source) || settings.value.mail_from || '')
  fieldErrors.value = data?.errors || {}
  fallbackTestToEmail.value =
    String((preferLocalValues ? currentValues.mail_test_recipient : source?.mail_test_recipient) || '').trim()
    || String(source?.mail_test_recipient || '').trim()
    || String(data?.test_to_email || '').trim()
    || fallbackTestToEmail.value
  initialSnapshot.value = JSON.stringify(buildConfigPayload())
  loaded.value = true
}

async function loadSettings() {
  const data = await api.get('/admin/mail')
  applyResponse(data)
}

onMounted(async () => {
  try {
    await loadSettings()
  } catch (error) {
    console.error('加载邮件设置失败:', error)
    loaded.value = true
  }
})

async function handleSubmit() {
  saving.value = true
  saveSuccess.value = false
  saveError.value = false

  try {
    const data = await api.post('/admin/mail', buildSavePayload())
    applyResponse(data, { preferLocalValues: true })
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  } catch (error) {
    console.error('保存邮件设置失败:', error)
    saveError.value = true
    if (error.response?.data) {
      applyResponse(error.response.data)
    }
  } finally {
    saving.value = false
  }
}

async function sendTestEmail() {
  testing.value = true
  try {
    await api.post('/admin/mail/test', {
      to_email: effectiveTestToEmail.value,
    })
    alert(`测试邮件已发送到 ${effectiveTestToEmail.value}，请检查收件箱`)
  } catch (error) {
    alert('发送测试邮件失败: ' + (error.response?.data?.error || '未知错误'))
  } finally {
    testing.value = false
  }
}
</script>

<style scoped>
.Form {
  width: 100%;
}

.MailContent {
  max-width: 820px;
  width: 100%;
}

.MailPage-loading {
  color: #68717d;
  font-size: 14px;
}

.StatusAlert {
  margin-bottom: 20px;
  padding: 14px 16px;
  border: 1px solid #f1d5d2;
  border-radius: 12px;
  background: #fff3f1;
  color: #8f3d34;
  line-height: 1.6;
}

.Form-section {
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 14px;
  padding: 20px;
  margin-bottom: 20px;
}

.Form-sectionHeader {
  margin-bottom: 20px;
}

.Form-sectionHeader h3 {
  margin: 0 0 8px;
  font-size: 17px;
  color: #243447;
}

.Form-sectionHeader p {
  margin: 0;
  color: #68717d;
  font-size: 14px;
  line-height: 1.6;
}

.Form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px 16px;
}

.Form-group {
  min-width: 0;
}

.Form-group--full {
  grid-column: 1 / -1;
}

.Form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
  color: #243447;
  font-size: 14px;
}

.FormControl {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 11px 12px;
  border: 1px solid #d6dee6;
  border-radius: 10px;
  font-size: 14px;
  font-family: inherit;
  background: #fff;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.FormControl:focus {
  outline: none;
  border-color: #4d698e;
  box-shadow: 0 0 0 3px rgba(77, 105, 142, 0.14);
}

.Form-hint {
  margin: 8px 0 0;
  color: #68717d;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

.ValidationError {
  margin-top: 8px;
  color: #b0423d;
  font-size: 13px;
  line-height: 1.5;
}

.ValidationError p {
  margin: 0;
}

.Form-actions {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 20px;
}

.TestMailPanel {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}

.TestMailPanel-input {
  margin: 0;
}

.TestMailPanel-meta {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}

.TestMailPanel-target {
  color: #4b5663;
  font-size: 14px;
  word-break: break-word;
}

.TestMailPanel-actions {
  margin-top: 0;
}

.Button {
  background: #f5f8fa;
  border: 1px solid #d6dee6;
  padding: 10px 18px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
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
  color: #1f8a52;
  font-size: 14px;
  font-weight: 600;
}

.Form-error {
  color: #b0423d;
  font-size: 14px;
  font-weight: 600;
}

@media (max-width: 768px) {
  .Form {
    max-width: none;
  }

  .Form-section {
    padding: 16px;
  }

  .Form-grid {
    grid-template-columns: 1fr;
  }

  .Form-group--full {
    grid-column: auto;
  }

  .Form-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .Form-actions .Button {
    width: 100%;
  }

  .TestMailPanel-meta {
    flex-direction: column;
  }
}
</style>
