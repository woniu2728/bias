<template>
  <AdminPage
    className="AdvancedPage"
    icon="fas fa-cog"
    title="高级设置"
    description="配置缓存、队列、维护模式与文件存储"
  >
    <div class="AdvancedPage-content">
      <div class="RuntimeNotice">
        <h3 class="Section-title">运行时说明</h3>
        <div class="RuntimeNotice-grid">
          <div>
            <h4>即时生效</h4>
            <p>`maintenance_mode`、`maintenance_message`、`cache_lifetime`、`log_queries` 会在保存后直接影响请求层行为。</p>
          </div>
          <div>
            <h4>需额外部署或重启</h4>
            <p>`debug_mode` 由 Django 配置文件或环境变量控制；`queue_enabled` / `queue_driver` 会控制已接入队列入口的任务，新 worker 配置需重启服务后生效。</p>
          </div>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">缓存设置</h3>

        <div class="Form-group">
          <label for="advanced-cache-driver">缓存驱动</label>
          <select
            id="advanced-cache-driver"
            v-model="settings.cache_driver"
            name="cache_driver"
            class="FormControl"
          >
            <option value="file">文件</option>
            <option value="redis">Redis</option>
            <option value="memcached">Memcached</option>
          </select>
          <p class="Form-help">选择缓存存储方式</p>
        </div>

        <div class="Form-group">
          <label for="advanced-cache-lifetime">缓存时间（秒）</label>
          <input
            id="advanced-cache-lifetime"
            v-model.number="settings.cache_lifetime"
            name="cache_lifetime"
            type="number"
            class="FormControl"
            placeholder="3600"
          />
          <p class="Form-help">当前已接入公开论坛设置缓存。填 0 表示禁用该缓存，保存基础/外观/高级设置时会自动清理。</p>
        </div>

        <div class="Form-actions">
          <button type="button" @click="clearCache" class="Button" :disabled="clearing">
            {{ clearing ? '清除中...' : '清除缓存' }}
          </button>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">搜索索引</h3>

        <div class="Form-group">
          <label>PostgreSQL 全文索引</label>
          <p class="Form-help">用于英文、数字关键词的讨论、回复和用户搜索。数据量较大时请在低峰期执行。</p>
        </div>

        <div class="Form-actions">
          <button
            type="button"
            @click="rebuildSearchIndexes"
            class="Button"
            :disabled="rebuildingSearchIndexes"
          >
            {{ rebuildingSearchIndexes ? '重建中...' : '重建搜索索引' }}
          </button>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">队列设置</h3>

        <div class="Form-group">
          <label for="advanced-queue-driver">队列驱动</label>
          <select
            id="advanced-queue-driver"
            v-model="settings.queue_driver"
            name="queue_driver"
            class="FormControl"
          >
            <option value="sync">同步</option>
            <option value="database">数据库</option>
            <option value="redis">Redis</option>
          </select>
          <p class="Form-help">当前通知实时投递已接入统一队列入口。选择 Redis 并部署 worker 后会尝试异步投递。</p>
        </div>

        <div class="Form-group">
          <label>
            <input
              id="advanced-queue-enabled"
              v-model="settings.queue_enabled"
              name="queue_enabled"
              type="checkbox"
              class="FormControl-checkbox"
            />
            启用队列处理
          </label>
          <p class="Form-help">关闭时强制同步执行。开启后，已接入任务会入队执行；入队失败时会同步回退，避免影响主流程。</p>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">安全与真人验证</h3>

        <div class="Form-group">
          <label for="advanced-human-verification-provider">验证提供方</label>
          <select
            id="advanced-human-verification-provider"
            v-model="settings.auth_human_verification_provider"
            name="auth_human_verification_provider"
            class="FormControl"
          >
            <option value="off">关闭</option>
            <option value="turnstile">Cloudflare Turnstile</option>
          </select>
          <p class="Form-help">建议正式环境开启，优先拦截登录和注册机器人。</p>
        </div>

        <template v-if="settings.auth_human_verification_provider === 'turnstile'">
          <div class="Form-grid">
            <div class="Form-group">
              <label for="advanced-turnstile-site-key">Site Key</label>
              <input
                id="advanced-turnstile-site-key"
                v-model="settings.auth_turnstile_site_key"
                name="auth_turnstile_site_key"
                type="text"
                class="FormControl"
                placeholder="0x4AAAA..."
              />
            </div>

            <div class="Form-group">
              <label for="advanced-turnstile-secret-key">Secret Key</label>
              <input
                id="advanced-turnstile-secret-key"
                v-model="settings.auth_turnstile_secret_key"
                name="auth_turnstile_secret_key"
                type="password"
                class="FormControl"
                placeholder="0x4AAAA..."
              />
            </div>
          </div>

          <div class="Form-grid">
            <div class="Form-group Form-group--checkbox">
              <label>
                <input
                  id="advanced-human-verification-login-enabled"
                  v-model="settings.auth_human_verification_login_enabled"
                  name="auth_human_verification_login_enabled"
                  type="checkbox"
                  class="FormControl-checkbox"
                />
                登录时启用真人验证
              </label>
            </div>

            <div class="Form-group Form-group--checkbox">
              <label>
                <input
                  id="advanced-human-verification-register-enabled"
                  v-model="settings.auth_human_verification_register_enabled"
                  name="auth_human_verification_register_enabled"
                  type="checkbox"
                  class="FormControl-checkbox"
                />
                注册时启用真人验证
              </label>
            </div>
          </div>

          <p v-if="turnstileMisconfigured" class="Form-warning">
            已选择 Turnstile，但 Site Key 或 Secret Key 仍为空，当前不会真正启用验证。
          </p>
        </template>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">文件存储</h3>

        <div class="Form-group">
          <label for="advanced-storage-driver">存储驱动</label>
          <select
            id="advanced-storage-driver"
            v-model="settings.storage_driver"
            name="storage_driver"
            class="FormControl"
          >
            <option value="local">本地存储</option>
            <option value="s3">Amazon S3 / S3 兼容</option>
            <option value="r2">Cloudflare R2</option>
            <option value="oss">阿里云 OSS</option>
            <option value="imagebed">通用图床</option>
          </select>
          <p class="Form-help">composer 上传、头像上传和后续附件能力都会读取这里的运行时配置</p>
        </div>

        <div class="Form-grid">
          <div class="Form-group">
            <label for="advanced-storage-attachments-dir">附件目录</label>
            <input
              id="advanced-storage-attachments-dir"
              v-model="settings.storage_attachments_dir"
              name="storage_attachments_dir"
              type="text"
              class="FormControl"
              placeholder="attachments"
            />
            <p class="Form-help">统一的附件对象目录，支持多级路径</p>
          </div>

          <div class="Form-group">
            <label for="advanced-storage-avatars-dir">头像目录</label>
            <input
              id="advanced-storage-avatars-dir"
              v-model="settings.storage_avatars_dir"
              name="storage_avatars_dir"
              type="text"
              class="FormControl"
              placeholder="avatars"
            />
            <p class="Form-help">头像和缩略图的对象目录</p>
          </div>
        </div>

        <div class="Form-section Form-section--nested">
          <div class="Form-sectionHeader">
            <h4>上传策略</h4>
            <p>限制上传大小，扩展名白名单仍由服务端固定控制。</p>
          </div>

          <div class="Form-grid">
            <div class="Form-group">
              <label for="advanced-upload-avatar-max-size">头像最大体积（MB）</label>
              <input
                id="advanced-upload-avatar-max-size"
                v-model.number="settings.upload_avatar_max_size_mb"
                name="upload_avatar_max_size_mb"
                type="number"
                min="1"
                max="100"
                class="FormControl"
              />
            </div>

            <div class="Form-group">
              <label for="advanced-upload-attachment-max-size">附件最大体积（MB）</label>
              <input
                id="advanced-upload-attachment-max-size"
                v-model.number="settings.upload_attachment_max_size_mb"
                name="upload_attachment_max_size_mb"
                type="number"
                min="1"
                max="100"
                class="FormControl"
              />
            </div>

            <div class="Form-group">
              <label for="advanced-upload-site-asset-max-size">站点资源最大体积（MB）</label>
              <input
                id="advanced-upload-site-asset-max-size"
                v-model.number="settings.upload_site_asset_max_size_mb"
                name="upload_site_asset_max_size_mb"
                type="number"
                min="1"
                max="100"
                class="FormControl"
              />
            </div>
          </div>

          <p class="Form-help">头像默认 2MB，composer 附件默认 10MB，Logo/Favicon 默认 2MB。</p>
        </div>

        <template v-if="settings.storage_driver === 'local'">
          <div class="Form-grid">
            <div class="Form-group">
              <label for="advanced-storage-local-path">本地保存目录</label>
              <input
                id="advanced-storage-local-path"
                v-model="settings.storage_local_path"
                name="storage_local_path"
                type="text"
                class="FormControl"
                placeholder="D:\\data\\bias\\media"
              />
              <p class="Form-help">可填写绝对路径，也可填写相对项目根目录的路径</p>
            </div>

            <div class="Form-group">
              <label for="advanced-storage-local-base-url">本地访问基地址</label>
              <input
                id="advanced-storage-local-base-url"
                v-model="settings.storage_local_base_url"
                name="storage_local_base_url"
                type="text"
                class="FormControl"
                placeholder="/media/"
              />
              <p class="Form-help">上传完成后生成给前台的 URL 前缀</p>
            </div>
          </div>
        </template>

        <template v-if="settings.storage_driver === 's3'">
          <div class="Form-grid">
            <div class="Form-group">
              <label>Bucket</label>
              <input v-model="settings.storage_s3_bucket" type="text" class="FormControl" />
            </div>
            <div class="Form-group">
              <label>Region</label>
              <input
                v-model="settings.storage_s3_region"
                type="text"
                class="FormControl"
                placeholder="ap-southeast-1"
              />
            </div>
            <div class="Form-group">
              <label>Endpoint</label>
              <input
                v-model="settings.storage_s3_endpoint"
                type="text"
                class="FormControl"
                placeholder="https://s3.amazonaws.com"
              />
              <p class="Form-help">使用 MinIO、Wasabi 等兼容服务时填写自定义 Endpoint</p>
            </div>
            <div class="Form-group">
              <label>公共访问 URL</label>
              <input
                v-model="settings.storage_s3_public_url"
                type="text"
                class="FormControl"
                placeholder="https://cdn.example.com"
              />
              <p class="Form-help">如留空，系统会按标准 S3 域名尝试拼接</p>
            </div>
            <div class="Form-group">
              <label>Access Key ID</label>
              <input v-model="settings.storage_s3_access_key_id" type="text" class="FormControl" />
            </div>
            <div class="Form-group">
              <label>Secret Access Key</label>
              <input v-model="settings.storage_s3_secret_access_key" type="password" class="FormControl" />
            </div>
            <div class="Form-group">
              <label>对象前缀</label>
              <input
                v-model="settings.storage_s3_object_prefix"
                type="text"
                class="FormControl"
                placeholder="bias"
              />
            </div>
            <div class="Form-group Form-group--checkbox">
              <label>
                <input
                  v-model="settings.storage_s3_path_style"
                  type="checkbox"
                  class="FormControl-checkbox"
                />
                使用 Path Style
              </label>
              <p class="Form-help">兼容部分 S3 服务或自建对象存储</p>
            </div>
          </div>
        </template>

        <template v-if="settings.storage_driver === 'r2'">
          <div class="Form-grid">
            <div class="Form-group">
              <label>Bucket</label>
              <input v-model="settings.storage_r2_bucket" type="text" class="FormControl" />
            </div>
            <div class="Form-group">
              <label>Endpoint</label>
              <input
                v-model="settings.storage_r2_endpoint"
                type="text"
                class="FormControl"
                placeholder="https://&lt;accountid&gt;.r2.cloudflarestorage.com"
              />
            </div>
            <div class="Form-group">
              <label>公共访问 URL / CDN 域名</label>
              <input
                v-model="settings.storage_r2_public_url"
                type="text"
                class="FormControl"
                placeholder="https://pub-xxx.r2.dev"
              />
              <p class="Form-help">R2 通常需要单独的公开域名，否则前台生成的附件链接不可访问</p>
            </div>
            <div class="Form-group">
              <label>Access Key ID</label>
              <input v-model="settings.storage_r2_access_key_id" type="text" class="FormControl" />
            </div>
            <div class="Form-group">
              <label>Secret Access Key</label>
              <input v-model="settings.storage_r2_secret_access_key" type="password" class="FormControl" />
            </div>
            <div class="Form-group">
              <label>对象前缀</label>
              <input
                v-model="settings.storage_r2_object_prefix"
                type="text"
                class="FormControl"
                placeholder="bias"
              />
            </div>
          </div>
        </template>

        <template v-if="settings.storage_driver === 'oss'">
          <div class="Form-grid">
            <div class="Form-group">
              <label>Bucket</label>
              <input v-model="settings.storage_oss_bucket" type="text" class="FormControl" />
            </div>
            <div class="Form-group">
              <label>Endpoint</label>
              <input
                v-model="settings.storage_oss_endpoint"
                type="text"
                class="FormControl"
                placeholder="oss-cn-hangzhou.aliyuncs.com"
              />
            </div>
            <div class="Form-group">
              <label>公共访问 URL</label>
              <input
                v-model="settings.storage_oss_public_url"
                type="text"
                class="FormControl"
                placeholder="https://cdn.example.com"
              />
              <p class="Form-help">如留空，将按 Bucket + Endpoint 生成标准 OSS 访问地址</p>
            </div>
            <div class="Form-group">
              <label>Access Key ID</label>
              <input v-model="settings.storage_oss_access_key_id" type="text" class="FormControl" />
            </div>
            <div class="Form-group">
              <label>Access Key Secret</label>
              <input v-model="settings.storage_oss_access_key_secret" type="password" class="FormControl" />
            </div>
            <div class="Form-group">
              <label>对象前缀</label>
              <input
                v-model="settings.storage_oss_object_prefix"
                type="text"
                class="FormControl"
                placeholder="bias"
              />
            </div>
          </div>
        </template>

        <template v-if="settings.storage_driver === 'imagebed'">
          <div class="Form-grid">
            <div class="Form-group">
              <label>上传接口地址</label>
              <input
                v-model="settings.storage_imagebed_endpoint"
                type="text"
                class="FormControl"
                placeholder="https://example.com/api/upload"
              />
            </div>
            <div class="Form-group">
              <label>请求方法</label>
              <select v-model="settings.storage_imagebed_method" class="FormControl">
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="PATCH">PATCH</option>
              </select>
            </div>
            <div class="Form-group">
              <label>文件字段名</label>
              <input
                v-model="settings.storage_imagebed_file_field"
                type="text"
                class="FormControl"
                placeholder="file"
              />
            </div>
            <div class="Form-group">
              <label>响应 URL 路径</label>
              <input
                v-model="settings.storage_imagebed_url_path"
                type="text"
                class="FormControl"
                placeholder="data.url"
              />
              <p class="Form-help">支持点路径，例如 `data.url`、`result.images.0.url`</p>
            </div>
          </div>

          <div class="Form-group">
            <label>请求头 JSON</label>
            <textarea
              v-model="settings.storage_imagebed_headers"
              class="FormControl"
              rows="4"
              placeholder='{"Authorization":"Bearer token"}'
            ></textarea>
          </div>

          <div class="Form-group">
            <label>额外表单参数 JSON</label>
            <textarea
              v-model="settings.storage_imagebed_form_data"
              class="FormControl"
              rows="4"
              placeholder='{"album":"forum"}'
            ></textarea>
          </div>
        </template>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">维护模式</h3>

        <div class="Form-group">
          <label>
            <input
              v-model="settings.maintenance_mode"
              type="checkbox"
              class="FormControl-checkbox"
            />
            启用维护模式
          </label>
          <p class="Form-help">启用后，普通用户访问论坛 API 将收到 503；`/api/forum`、登录接口和后台入口保留豁免。</p>
        </div>

        <div class="Form-group">
          <label>维护提示信息</label>
          <textarea
            v-model="settings.maintenance_message"
            class="FormControl"
            rows="3"
            placeholder="论坛正在维护中，请稍后再试..."
          ></textarea>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">调试设置</h3>

        <div class="Form-group">
          <label>
            <input
              v-model="settings.debug_mode"
              type="checkbox"
              class="FormControl-checkbox"
              disabled
            />
            调试模式（只读）
          </label>
          <p class="Form-help">当前运行值来自 Django 配置文件或环境变量，保存这里不会热切换服务端 DEBUG。</p>
        </div>

        <div class="Form-group">
          <label>
            <input
              v-model="settings.log_queries"
              type="checkbox"
              class="FormControl-checkbox"
            />
            记录数据库查询
          </label>
          <p class="Form-help">保存后即时生效。会把每个 HTTP 请求触发的 SQL 记录到服务器日志。</p>
        </div>
      </div>

      <div class="Form-actions">
        <button
          @click="saveSettings"
          class="Button Button--primary"
          :disabled="saving"
        >
          {{ saving ? '保存中...' : '保存设置' }}
        </button>
      </div>
      <AdminInlineMessage v-if="saveSuccess" tone="success">保存成功</AdminInlineMessage>
      <AdminInlineMessage v-if="saveError" tone="danger">保存失败，请重试</AdminInlineMessage>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AdminInlineMessage from '../components/AdminInlineMessage.vue'
import AdminPage from '../components/AdminPage.vue'
import { useAdminSaveFeedback } from '../composables/useAdminSaveFeedback'
import api from '../../api'
import { useModalStore } from '../../stores/modal'

const settings = ref({
  cache_driver: 'file',
  cache_lifetime: 3600,
  queue_driver: 'sync',
  queue_enabled: false,
  maintenance_mode: false,
  maintenance_message: '',
  debug_mode: false,
  log_queries: false,
  auth_human_verification_provider: 'off',
  auth_turnstile_site_key: '',
  auth_turnstile_secret_key: '',
  auth_human_verification_login_enabled: true,
  auth_human_verification_register_enabled: true,
  storage_driver: 'local',
  storage_attachments_dir: 'attachments',
  storage_avatars_dir: 'avatars',
  upload_avatar_max_size_mb: 2,
  upload_attachment_max_size_mb: 10,
  upload_site_asset_max_size_mb: 2,
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
  storage_imagebed_url_path: 'data.url'
})

const saving = ref(false)
const clearing = ref(false)
const rebuildingSearchIndexes = ref(false)
const loadedSettingsSnapshot = ref(null)
const modalStore = useModalStore()
const { saveSuccess, saveError, resetSaveFeedback, showSaveSuccess, showSaveError } = useAdminSaveFeedback()
const turnstileMisconfigured = computed(() => (
  settings.value.auth_human_verification_provider === 'turnstile'
  && (!settings.value.auth_turnstile_site_key || !settings.value.auth_turnstile_secret_key)
))

onMounted(async () => {
  try {
    const data = await api.get('/admin/advanced')
    settings.value = { ...settings.value, ...data }
    loadedSettingsSnapshot.value = createSettingsSnapshot(settings.value)
  } catch (error) {
    console.error('加载高级设置失败:', error)
  }
})

async function saveSettings() {
  const sensitiveChanges = getSensitiveSettingChanges()
  if (sensitiveChanges.length > 0) {
    const confirmed = await modalStore.confirm({
      title: '保存高级设置',
      message: `以下设置会影响运行时行为：${sensitiveChanges.join('、')}。确定保存当前配置吗？`,
      confirmText: '保存',
      cancelText: '取消',
      tone: 'warning'
    })
    if (!confirmed) {
      return
    }
  }

  saving.value = true
  resetSaveFeedback()

  try {
    const response = await api.post('/admin/advanced', settings.value)
    if (response?.settings) {
      settings.value = { ...settings.value, ...response.settings }
    }
    loadedSettingsSnapshot.value = createSettingsSnapshot(settings.value)
    showSaveSuccess()
  } catch (error) {
    console.error('保存高级设置失败:', error)
    showSaveError()
  } finally {
    saving.value = false
  }
}

async function clearCache() {
  const confirmed = await modalStore.confirm({
    title: '清除缓存',
    message: '确定清除运行时缓存吗？短时间内部分页面可能重新读取配置和数据。',
    confirmText: '清除',
    cancelText: '取消',
    tone: 'warning'
  })
  if (!confirmed) {
    return
  }

  clearing.value = true
  try {
    await api.post('/admin/cache/clear')
    await modalStore.alert({
      title: '缓存已清除',
      message: '运行时缓存已成功清理。',
      tone: 'success'
    })
  } catch (error) {
    await modalStore.alert({
      title: '清除缓存失败',
      message: error.response?.data?.error || '未知错误',
      tone: 'danger'
    })
  } finally {
    clearing.value = false
  }
}

async function rebuildSearchIndexes() {
  const confirmed = await modalStore.confirm({
    title: '重建搜索索引',
    message: '确定在后台重建 PostgreSQL 全文搜索索引吗？数据量较大时可能耗时较长，建议在低峰期执行。',
    confirmText: '重建',
    cancelText: '取消',
    tone: 'warning'
  })
  if (!confirmed) {
    return
  }

  rebuildingSearchIndexes.value = true
  try {
    await api.post('/admin/search-indexes/rebuild')
    await modalStore.alert({
      title: '搜索索引已重建',
      message: '已重建讨论、回复和用户搜索索引。',
      tone: 'success'
    })
  } catch (error) {
    await modalStore.alert({
      title: '重建搜索索引失败',
      message: error.response?.data?.error || error.message || '未知错误',
      tone: 'danger'
    })
  } finally {
    rebuildingSearchIndexes.value = false
  }
}

function createSettingsSnapshot(value) {
  return {
    maintenance_mode: Boolean(value.maintenance_mode),
    queue_enabled: Boolean(value.queue_enabled),
    queue_driver: value.queue_driver,
    log_queries: Boolean(value.log_queries),
    storage_driver: value.storage_driver,
    upload_avatar_max_size_mb: normalizeUploadSize(value.upload_avatar_max_size_mb),
    upload_attachment_max_size_mb: normalizeUploadSize(value.upload_attachment_max_size_mb),
    upload_site_asset_max_size_mb: normalizeUploadSize(value.upload_site_asset_max_size_mb),
  }
}

function getSensitiveSettingChanges() {
  const previous = loadedSettingsSnapshot.value
  if (!previous) {
    return []
  }

  const current = createSettingsSnapshot(settings.value)
  const labels = {
    maintenance_mode: '维护模式',
    queue_enabled: '队列启用状态',
    queue_driver: '队列驱动',
    log_queries: 'SQL 查询日志',
    storage_driver: '文件存储驱动',
    upload_avatar_max_size_mb: '头像上传上限',
    upload_attachment_max_size_mb: '附件上传上限',
    upload_site_asset_max_size_mb: '站点资源上传上限',
  }

  return Object.keys(labels).filter(key => previous[key] !== current[key]).map(key => labels[key])
}

function normalizeUploadSize(value) {
  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed)) {
    return 1
  }
  return Math.min(100, Math.max(1, parsed))
}
</script>

<style scoped>
.AdvancedPage-content {
  max-width: 920px;
}

.RuntimeNotice {
  background: linear-gradient(135deg, var(--forum-bg-elevated-strong) 0%, var(--forum-bg-subtle) 100%);
  border: 1px solid var(--forum-border-color);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: var(--forum-shadow-sm);
}

.RuntimeNotice-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.RuntimeNotice h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--forum-text-color);
}

.RuntimeNotice p {
  margin: 0;
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
  line-height: 1.7;
}

.Section-title {
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--forum-border-soft);
}

.Form-grid {
  gap: 0 16px;
}

.Form-group--checkbox label {
  margin-bottom: 6px;
}

.Form-section--nested {
  margin: 4px 0 22px;
  padding: 16px;
  background: var(--forum-bg-elevated-strong);
  box-shadow: none;
}

.Form-section--nested .Form-sectionHeader {
  margin-bottom: 14px;
}

.Form-section--nested h4 {
  margin: 0 0 6px;
  color: var(--forum-text-color);
  font-size: 15px;
}

.Form-section--nested p {
  margin: 0;
}

.Form-warning {
  margin: 0;
  color: var(--forum-warning-color);
  font-size: var(--forum-font-size-sm);
  line-height: 1.6;
}

@media (max-width: 768px) {
  .RuntimeNotice-grid,
  .Form-grid {
    grid-template-columns: 1fr;
  }

  .AdvancedPage-content {
    max-width: none;
  }

  .RuntimeNotice {
    padding: 16px;
    border-radius: 14px;
  }
}
</style>
