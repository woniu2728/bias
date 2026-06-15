<template>
  <section class="UploadsSettingsPage">
    <AdminStateBlock v-if="loading" tone="subtle">加载上传设置中...</AdminStateBlock>
    <AdminStateBlock v-else-if="loadError" tone="danger">{{ loadError }}</AdminStateBlock>

    <template v-else>
      <div class="UploadsSettingsPage-grid">
        <article class="UploadsSettingsPage-panel">
          <h3>上传策略</h3>

          <div class="UploadsSettingsPage-fields">
            <label>
              <span>附件目录</span>
              <input v-model="settings.attachments_dir" class="FormControl" type="text">
            </label>
            <label>
              <span>附件最大体积（MB）</span>
              <input v-model.number="settings.attachment_max_size_mb" class="FormControl" type="number" min="1" max="100">
            </label>
            <label>
              <span>站点资源最大体积（MB）</span>
              <input v-model.number="settings.upload_site_asset_max_size_mb" class="FormControl" type="number" min="1" max="100">
            </label>
            <label>
              <span>头像目录</span>
              <input v-model="settings.avatars_dir" class="FormControl" type="text">
            </label>
            <label>
              <span>头像最大体积（MB）</span>
              <input v-model.number="settings.avatar_max_size_mb" class="FormControl" type="number" min="1" max="100">
            </label>
          </div>
        </article>

        <article class="UploadsSettingsPage-panel">
          <h3>存储驱动</h3>

          <div class="UploadsSettingsPage-fields">
            <label>
              <span>当前驱动</span>
              <AdminSelectMenu
                v-model="settings.storage_driver"
                :options="storageDriverOptions"
                placeholder="请选择存储驱动"
              />
            </label>

            <template v-if="settings.storage_driver === 'local'">
              <label>
                <span>本地保存目录</span>
                <input v-model="settings.storage_local_path" class="FormControl" type="text">
              </label>
              <label>
                <span>本地访问基地址</span>
                <input v-model="settings.storage_local_base_url" class="FormControl" type="text">
              </label>
            </template>

            <template v-else-if="settings.storage_driver === 's3'">
              <label><span>S3 Bucket</span><input v-model="settings.storage_s3_bucket" class="FormControl" type="text"></label>
              <label><span>S3 Region</span><input v-model="settings.storage_s3_region" class="FormControl" type="text"></label>
              <label><span>S3 Endpoint</span><input v-model="settings.storage_s3_endpoint" class="FormControl" type="text"></label>
              <label><span>S3 Access Key ID</span><input v-model="settings.storage_s3_access_key_id" class="FormControl" type="text"></label>
              <label><span>S3 Secret Access Key</span><input v-model="settings.storage_s3_secret_access_key" class="FormControl" type="password"></label>
              <label><span>S3 公共访问 URL</span><input v-model="settings.storage_s3_public_url" class="FormControl" type="text"></label>
              <label><span>S3 对象前缀</span><input v-model="settings.storage_s3_object_prefix" class="FormControl" type="text"></label>
              <label class="UploadsSettingsPage-inlineToggle">
                <span>S3 使用 Path Style</span>
                <input v-model="settings.storage_s3_path_style" class="FormControl-checkbox" type="checkbox">
              </label>
            </template>

            <template v-else-if="settings.storage_driver === 'r2'">
              <label><span>R2 Bucket</span><input v-model="settings.storage_r2_bucket" class="FormControl" type="text"></label>
              <label><span>R2 Endpoint</span><input v-model="settings.storage_r2_endpoint" class="FormControl" type="text"></label>
              <label><span>R2 Access Key ID</span><input v-model="settings.storage_r2_access_key_id" class="FormControl" type="text"></label>
              <label><span>R2 Secret Access Key</span><input v-model="settings.storage_r2_secret_access_key" class="FormControl" type="password"></label>
              <label><span>R2 公共访问 URL</span><input v-model="settings.storage_r2_public_url" class="FormControl" type="text"></label>
              <label><span>R2 对象前缀</span><input v-model="settings.storage_r2_object_prefix" class="FormControl" type="text"></label>
            </template>

            <template v-else-if="settings.storage_driver === 'oss'">
              <label><span>OSS Bucket</span><input v-model="settings.storage_oss_bucket" class="FormControl" type="text"></label>
              <label><span>OSS Endpoint</span><input v-model="settings.storage_oss_endpoint" class="FormControl" type="text"></label>
              <label><span>OSS Access Key ID</span><input v-model="settings.storage_oss_access_key_id" class="FormControl" type="text"></label>
              <label><span>OSS Access Key Secret</span><input v-model="settings.storage_oss_access_key_secret" class="FormControl" type="password"></label>
              <label><span>OSS 公共访问 URL</span><input v-model="settings.storage_oss_public_url" class="FormControl" type="text"></label>
              <label><span>OSS 对象前缀</span><input v-model="settings.storage_oss_object_prefix" class="FormControl" type="text"></label>
            </template>

            <template v-else-if="settings.storage_driver === 'imagebed'">
              <label><span>图床上传接口地址</span><input v-model="settings.storage_imagebed_endpoint" class="FormControl" type="text"></label>
              <label>
                <span>图床请求方法</span>
                <AdminSelectMenu v-model="settings.storage_imagebed_method" :options="imagebedMethodOptions" placeholder="请选择请求方法" />
              </label>
              <label><span>图床文件字段名</span><input v-model="settings.storage_imagebed_file_field" class="FormControl" type="text"></label>
              <label><span>图床请求头 JSON</span><textarea v-model="settings.storage_imagebed_headers" class="FormControl" rows="3"></textarea></label>
              <label><span>图床额外表单参数 JSON</span><textarea v-model="settings.storage_imagebed_form_data" class="FormControl" rows="3"></textarea></label>
              <label><span>图床响应 URL 路径</span><input v-model="settings.storage_imagebed_url_path" class="FormControl" type="text"></label>
            </template>
          </div>
        </article>
      </div>

      <AdminInlineMessage v-if="saveSuccess" tone="success">上传设置已保存</AdminInlineMessage>
      <AdminInlineMessage v-if="saveError" tone="danger">{{ saveErrorMessage || '上传设置保存失败，请稍后重试' }}</AdminInlineMessage>

      <div class="UploadsSettingsPage-actions">
        <button type="button" class="Button" :disabled="loading || saving" @click="loadSettings">
          刷新
        </button>
        <button type="button" class="Button Button--primary" :disabled="loading || saving" @click="saveSettings">
          {{ saving ? '保存中...' : '保存上传设置' }}
        </button>
      </div>
    </template>
  </section>
</template>

<script setup>
import { onMounted, ref } from '@bias/core'
import { adminApi, AdminInlineMessage, AdminSelectMenu, AdminStateBlock, useAdminSaveFeedback, useModalStore } from '@bias/admin/components'

const modalStore = useModalStore()
const loading = ref(true)
const saving = ref(false)
const loadError = ref('')
const settings = ref(buildDefaultSettings())
const storageDriverOptions = [
  { value: 'local', label: '本地存储' },
  { value: 's3', label: 'Amazon S3 / S3 兼容' },
  { value: 'r2', label: 'Cloudflare R2' },
  { value: 'oss', label: '阿里云 OSS' },
  { value: 'imagebed', label: '通用图床' },
]
const imagebedMethodOptions = [
  { value: 'POST', label: 'POST' },
  { value: 'PUT', label: 'PUT' },
  { value: 'PATCH', label: 'PATCH' },
]
const { saveSuccess, saveError, saveErrorMessage, resetSaveFeedback, showSaveSuccess, showSaveError } = useAdminSaveFeedback()

onMounted(loadSettings)

async function loadSettings() {
  loading.value = true
  loadError.value = ''
  resetSaveFeedback()
  try {
    const data = await adminApi.get('/admin/extensions/uploads/settings')
    settings.value = { ...buildDefaultSettings(), ...(data.settings || {}) }
  } catch (error) {
    console.error('加载上传设置失败:', error)
    loadError.value = error.response?.data?.error || '加载上传设置失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  resetSaveFeedback()
  try {
    const payload = buildSubmitPayload()
    const data = await adminApi.post('/admin/extensions/uploads/settings', payload)
    settings.value = { ...buildDefaultSettings(), ...(data.settings || settings.value) }
    showSaveSuccess()
    await modalStore.alert({
      title: '上传设置已保存',
      message: '新的上传策略和存储驱动配置已生效。',
      tone: 'success',
    })
  } catch (error) {
    console.error('保存上传设置失败:', error)
    showSaveError(error.response?.data?.error || '保存上传设置失败，请稍后重试')
    await modalStore.alert({
      title: '保存上传设置失败',
      message: error.response?.data?.error || error.message || '未知错误',
      tone: 'danger',
    })
  } finally {
    saving.value = false
  }
}

function buildDefaultSettings() {
  return {
    attachments_dir: 'attachments',
    attachment_max_size_mb: 10,
    upload_site_asset_max_size_mb: 2,
    avatars_dir: 'avatars',
    avatar_max_size_mb: 2,
    storage_driver: 'local',
    storage_local_path: '',
    storage_local_base_url: '/media/',
    storage_s3_bucket: '',
    storage_s3_region: '',
    storage_s3_endpoint: '',
    storage_s3_access_key_id: '',
    storage_s3_secret_access_key: '',
    storage_s3_public_url: '',
    storage_s3_object_prefix: '',
    storage_s3_path_style: false,
    storage_r2_bucket: '',
    storage_r2_endpoint: '',
    storage_r2_access_key_id: '',
    storage_r2_secret_access_key: '',
    storage_r2_public_url: '',
    storage_r2_object_prefix: '',
    storage_oss_bucket: '',
    storage_oss_endpoint: '',
    storage_oss_access_key_id: '',
    storage_oss_access_key_secret: '',
    storage_oss_public_url: '',
    storage_oss_object_prefix: '',
    storage_imagebed_endpoint: '',
    storage_imagebed_method: 'POST',
    storage_imagebed_file_field: 'file',
    storage_imagebed_headers: '{}',
    storage_imagebed_form_data: '{}',
    storage_imagebed_url_path: 'data.url',
  }
}

function buildSubmitPayload() {
  return { ...settings.value }
}
</script>

<style scoped>
.UploadsSettingsPage {
  display: grid;
  gap: 16px;
}

.UploadsSettingsPage-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.UploadsSettingsPage-panel {
  padding: 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 8px;
  background: var(--forum-bg-elevated);
}

.UploadsSettingsPage-panel h3 {
  margin: 0 0 12px;
  font-size: 16px;
}

.UploadsSettingsPage-fields {
  display: grid;
  gap: 12px;
}

.UploadsSettingsPage-fields label {
  display: grid;
  gap: 6px;
}

.UploadsSettingsPage-fields label.UploadsSettingsPage-inlineToggle {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  min-height: 40px;
  width: fit-content;
}

.UploadsSettingsPage-fields span {
  font-size: 13px;
  color: var(--forum-text-muted);
}

.UploadsSettingsPage-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 768px) {
  .UploadsSettingsPage-grid {
    grid-template-columns: 1fr;
  }
}
</style>
