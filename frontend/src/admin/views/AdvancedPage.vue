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
            <p>`debug_mode` 由 Django 配置文件或环境变量控制；`queue_enabled` / `queue_driver` 目前只声明目标执行方式，完整异步 worker 链路仍待接入。</p>
          </div>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">缓存设置</h3>

        <div class="Form-group">
          <label>缓存驱动</label>
          <select v-model="settings.cache_driver" class="FormControl">
            <option value="file">文件</option>
            <option value="redis">Redis</option>
            <option value="memcached">Memcached</option>
          </select>
          <p class="Form-help">选择缓存存储方式</p>
        </div>

        <div class="Form-group">
          <label>缓存时间（秒）</label>
          <input
            v-model.number="settings.cache_lifetime"
            type="number"
            class="FormControl"
            placeholder="3600"
          />
          <p class="Form-help">当前已接入公开论坛设置缓存。填 0 表示禁用该缓存，保存基础/外观/高级设置时会自动清理。</p>
        </div>

        <div class="Form-actions">
          <button @click="clearCache" class="Button" :disabled="clearing">
            {{ clearing ? '清除中...' : '清除缓存' }}
          </button>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">队列设置</h3>

        <div class="Form-group">
          <label>队列驱动</label>
          <select v-model="settings.queue_driver" class="FormControl">
            <option value="sync">同步</option>
            <option value="database">数据库</option>
            <option value="redis">Redis</option>
          </select>
          <p class="Form-help">当前用于声明目标执行器。未部署 worker 时，耗时任务仍按同步方式执行。</p>
        </div>

        <div class="Form-group">
          <label>
            <input
              v-model="settings.queue_enabled"
              type="checkbox"
              class="FormControl-checkbox"
            />
            启用队列处理
          </label>
          <p class="Form-help">关闭时强制同步执行。开启后仅保留运行目标配置，完整异步任务链路后续再补。</p>
        </div>
      </div>

      <div class="Form-section">
        <h3 class="Section-title">文件存储</h3>

        <div class="Form-group">
          <label>存储驱动</label>
          <select v-model="settings.storage_driver" class="FormControl">
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
            <label>附件目录</label>
            <input
              v-model="settings.storage_attachments_dir"
              type="text"
              class="FormControl"
              placeholder="attachments"
            />
            <p class="Form-help">统一的附件对象目录，支持多级路径</p>
          </div>

          <div class="Form-group">
            <label>头像目录</label>
            <input
              v-model="settings.storage_avatars_dir"
              type="text"
              class="FormControl"
              placeholder="avatars"
            />
            <p class="Form-help">头像和缩略图的对象目录</p>
          </div>
        </div>

        <template v-if="settings.storage_driver === 'local'">
          <div class="Form-grid">
            <div class="Form-group">
              <label>本地保存目录</label>
              <input
                v-model="settings.storage_local_path"
                type="text"
                class="FormControl"
                placeholder="D:\\data\\bias\\media"
              />
              <p class="Form-help">可填写绝对路径，也可填写相对项目根目录的路径</p>
            </div>

            <div class="Form-group">
              <label>本地访问基地址</label>
              <input
                v-model="settings.storage_local_base_url"
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
        <span v-if="saveSuccess" class="Form-success">✓ 保存成功</span>
        <span v-if="saveError" class="Form-error">保存失败，请重试</span>
      </div>
    </div>
  </AdminPage>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import api from '../../api'

const settings = ref({
  cache_driver: 'file',
  cache_lifetime: 3600,
  queue_driver: 'sync',
  queue_enabled: false,
  maintenance_mode: false,
  maintenance_message: '',
  debug_mode: false,
  log_queries: false,
  storage_driver: 'local',
  storage_attachments_dir: 'attachments',
  storage_avatars_dir: 'avatars',
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
const saveSuccess = ref(false)
const saveError = ref(false)

onMounted(async () => {
  try {
    const data = await api.get('/admin/advanced')
    settings.value = { ...settings.value, ...data }
  } catch (error) {
    console.error('加载高级设置失败:', error)
  }
})

async function saveSettings() {
  saving.value = true
  saveSuccess.value = false
  saveError.value = false

  try {
    await api.post('/admin/advanced', settings.value)
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  } catch (error) {
    console.error('保存高级设置失败:', error)
    saveError.value = true
  } finally {
    saving.value = false
  }
}

async function clearCache() {
  clearing.value = true
  try {
    await api.post('/admin/cache/clear')
    alert('缓存已清除')
  } catch (error) {
    alert('清除缓存失败: ' + (error.response?.data?.error || '未知错误'))
  } finally {
    clearing.value = false
  }
}
</script>

<style scoped>
.AdvancedPage-content {
  max-width: 920px;
}

.RuntimeNotice {
  background: linear-gradient(135deg, #f7fafc 0%, #edf3f9 100%);
  border: 1px solid #d6e1ec;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.RuntimeNotice-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.RuntimeNotice h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #223041;
}

.RuntimeNotice p {
  margin: 0;
  color: #536273;
  font-size: 13px;
  line-height: 1.7;
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

.Form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
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

.Form-group--checkbox label {
  margin-bottom: 6px;
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

.FormControl-checkbox {
  width: auto;
  margin-right: 8px;
}

.Form-help {
  margin: 6px 0 0 0;
  font-size: 13px;
  color: #999;
  line-height: 1.6;
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

@media (max-width: 768px) {
  .RuntimeNotice-grid,
  .Form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
