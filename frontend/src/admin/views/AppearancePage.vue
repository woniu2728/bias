<template>
  <AdminPage
    className="AppearancePage"
    icon="fas fa-paint-brush"
    title="外观设置"
    description="自定义论坛的外观和主题"
  >
    <div class="AppearancePage-content">
      <div class="AppearancePage-section">
        <h3 class="Section-title">颜色</h3>
        <div class="Form-group">
          <label>主题色</label>
          <div class="ColorPicker">
            <input
              v-model="settings.primary_color"
              type="color"
              class="ColorPicker-input"
            />
            <input
              v-model="settings.primary_color"
              type="text"
              class="FormControl ColorPicker-text"
              placeholder="#4d698e"
            />
          </div>
          <p class="Form-help">论坛的主题颜色</p>
        </div>

        <div class="Form-group">
          <label>强调色</label>
          <div class="ColorPicker">
            <input
              v-model="settings.accent_color"
              type="color"
              class="ColorPicker-input"
            />
            <input
              v-model="settings.accent_color"
              type="text"
              class="FormControl ColorPicker-text"
              placeholder="#e74c3c"
            />
          </div>
          <p class="Form-help">用于按钮和链接的强调色</p>
        </div>
      </div>

      <div class="AppearancePage-section">
        <h3 class="Section-title">Logo</h3>
        <div class="AssetCard">
          <div class="AssetCard-preview">
            <img v-if="settings.logo_url" :src="settings.logo_url" alt="Logo 预览" class="AssetCard-image AssetCard-image--logo" />
            <div v-else class="AssetCard-placeholder">暂无 Logo</div>
          </div>
          <div class="AssetCard-meta">
            <div class="AssetCard-title">站点 Logo</div>
            <p class="Form-help">建议上传透明背景 PNG、SVG 或 WebP，Header 会优先展示这里的资源。</p>
            <div class="AssetCard-actions">
              <label class="Button Button--secondary Button--upload" :class="{ 'is-disabled': uploadingLogo }">
                <input type="file" accept=".png,.jpg,.jpeg,.gif,.webp,.svg" hidden @change="uploadAsset($event, 'logo')" />
                {{ uploadingLogo ? '上传中...' : '上传本地 Logo' }}
              </label>
              <button v-if="settings.logo_url" type="button" class="Button" @click="settings.logo_url = ''">清空</button>
            </div>
          </div>
        </div>

        <div class="Form-group Form-group--assetUrl">
          <label>Logo URL</label>
          <input
            v-model="settings.logo_url"
            type="text"
            class="FormControl"
            placeholder="https://example.com/logo.png"
          />
          <p class="Form-help">论坛Logo的URL地址</p>
        </div>

        <div class="AssetCard">
          <div class="AssetCard-preview AssetCard-preview--favicon">
            <img v-if="settings.favicon_url" :src="settings.favicon_url" alt="Favicon 预览" class="AssetCard-image AssetCard-image--favicon" />
            <div v-else class="AssetCard-placeholder">暂无 Favicon</div>
          </div>
          <div class="AssetCard-meta">
            <div class="AssetCard-title">浏览器图标</div>
            <p class="Form-help">建议上传 `.ico`、PNG 或 SVG，小尺寸图标在浏览器标签页里更清晰。</p>
            <div class="AssetCard-actions">
              <label class="Button Button--secondary Button--upload" :class="{ 'is-disabled': uploadingFavicon }">
                <input type="file" accept=".ico,.png,.svg,.webp" hidden @change="uploadAsset($event, 'favicon')" />
                {{ uploadingFavicon ? '上传中...' : '上传本地 Favicon' }}
              </label>
              <button v-if="settings.favicon_url" type="button" class="Button" @click="settings.favicon_url = ''">清空</button>
            </div>
          </div>
        </div>

        <div class="Form-group Form-group--assetUrl">
          <label>Favicon URL</label>
          <input
            v-model="settings.favicon_url"
            type="text"
            class="FormControl"
            placeholder="https://example.com/favicon.ico"
          />
          <p class="Form-help">浏览器标签页图标的URL地址</p>
        </div>
      </div>

      <div class="AppearancePage-section">
        <h3 class="Section-title">自定义样式</h3>
        <div class="PresetPanel">
          <div class="PresetPanel-header">
            <div>
              <h4>样式预设</h4>
              <p>点击即可把常用样式片段填入自定义 CSS，你可以继续修改后再保存。</p>
            </div>
            <button type="button" class="Button" @click="settings.custom_css = ''">清空 CSS</button>
          </div>
          <div class="PresetPanel-grid">
            <button
              v-for="preset in cssPresets"
              :key="preset.name"
              type="button"
              class="PresetCard"
              @click="applyCssPreset(preset.css)"
            >
              <span class="PresetCard-name">{{ preset.name }}</span>
              <span class="PresetCard-desc">{{ preset.description }}</span>
            </button>
          </div>
        </div>

        <div class="Form-group">
          <label>自定义CSS</label>
          <textarea
            v-model="settings.custom_css"
            class="FormControl"
            rows="10"
            placeholder="/* 在这里添加自定义CSS */"
          ></textarea>
          <p class="Form-help">添加自定义CSS样式来进一步定制论坛外观</p>
        </div>

        <div class="Form-group">
          <label>自定义Header HTML</label>
          <textarea
            v-model="settings.custom_header"
            class="FormControl"
            rows="5"
            placeholder="<!-- 在这里添加自定义HTML -->"
          ></textarea>
          <p class="Form-help">在页面头部添加自定义HTML（如统计代码）</p>
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
import { ref, onMounted } from 'vue'
import AdminPage from '../components/AdminPage.vue'
import api from '../../api'

const settings = ref({
  primary_color: '#4d698e',
  accent_color: '#e74c3c',
  logo_url: '',
  favicon_url: '',
  custom_css: '',
  custom_header: '',
})

const saving = ref(false)
const saveSuccess = ref(false)
const saveError = ref(false)
const uploadingLogo = ref(false)
const uploadingFavicon = ref(false)
const cssPresets = [
  {
    name: '柔和圆角',
    description: '让卡片、按钮和输入框更柔和一些',
    css: `:root {\n  --forum-primary-color: #3f6f90;\n  --forum-accent-color: #d66b4d;\n}\n\n.Button,\n.FormControl,\n.DiscussionListItem,\n.DiscussionHero,\n.PostCard {\n  border-radius: 12px;\n}\n`,
  },
  {
    name: '对比增强',
    description: '提高标题、边框和标签的可读性',
    css: `body {\n  color: #223245;\n}\n\n.Header,\n.DiscussionListItem,\n.PostCard,\n.Sidebar {\n  border-color: #d2dce6;\n}\n\nh1, h2, h3,\n.DiscussionListItem-title {\n  color: #162332;\n}\n`,
  },
  {
    name: '紧凑列表',
    description: '压缩讨论列表和帖子区域的纵向间距',
    css: `.DiscussionListItem,\n.PostCard {\n  padding-top: 12px;\n  padding-bottom: 12px;\n}\n\n.DiscussionHero {\n  padding-top: 20px;\n  padding-bottom: 20px;\n}\n`,
  },
]

onMounted(async () => {
  try {
    const data = await api.get('/admin/appearance')
    settings.value = { ...settings.value, ...data }
  } catch (error) {
    console.error('加载外观设置失败:', error)
  }
})

async function saveSettings() {
  saving.value = true
  saveSuccess.value = false
  saveError.value = false

  try {
    await api.post('/admin/appearance', settings.value)
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  } catch (error) {
    console.error('保存外观设置失败:', error)
    saveError.value = true
  } finally {
    saving.value = false
  }
}

function applyCssPreset(css) {
  settings.value.custom_css = css
}

async function uploadAsset(event, target) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return

  const uploadingRef = target === 'logo' ? uploadingLogo : uploadingFavicon
  uploadingRef.value = true

  try {
    const formData = new FormData()
    formData.append('file', file)

    const response = await api.post('/admin/appearance/upload', formData, {
      params: { target },
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    if (target === 'logo') {
      settings.value.logo_url = response.url || ''
    } else {
      settings.value.favicon_url = response.url || ''
    }
  } catch (error) {
    console.error('上传站点资源失败:', error)
    alert('上传失败: ' + (error.response?.data?.error || error.message || '未知错误'))
  } finally {
    uploadingRef.value = false
  }
}
</script>

<style scoped>
.AppearancePage-content {
  max-width: 800px;
}

.AppearancePage-section {
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 20px;
}

.PresetPanel {
  margin-bottom: 20px;
  padding: 16px;
  border: 1px solid #e6ebf0;
  border-radius: 10px;
  background: #fbfcfe;
}

.PresetPanel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 14px;
}

.PresetPanel-header h4 {
  margin: 0 0 6px;
  font-size: 15px;
  color: #223245;
}

.PresetPanel-header p {
  margin: 0;
  color: #6c7b88;
  font-size: 13px;
  line-height: 1.6;
}

.PresetPanel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.PresetCard {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 14px;
  border: 1px solid #d7e0e9;
  border-radius: 10px;
  background: white;
  text-align: left;
}

.PresetCard:hover {
  border-color: #4d698e;
  background: #f8fbff;
}

.PresetCard-name {
  font-size: 14px;
  font-weight: 600;
  color: #223245;
}

.PresetCard-desc {
  color: #6d7a87;
  font-size: 12px;
  line-height: 1.5;
}

.AssetCard {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 18px;
  margin-bottom: 20px;
  padding: 16px;
  border: 1px solid #e6ebf0;
  border-radius: 10px;
  background: #fbfcfe;
}

.AssetCard-preview {
  display: grid;
  place-items: center;
  min-height: 110px;
  padding: 18px;
  border: 1px dashed #cfd9e3;
  border-radius: 10px;
  background:
    linear-gradient(45deg, #f3f6f9 25%, transparent 25%, transparent 75%, #f3f6f9 75%, #f3f6f9),
    linear-gradient(45deg, #f3f6f9 25%, transparent 25%, transparent 75%, #f3f6f9 75%, #f3f6f9);
  background-size: 18px 18px;
  background-position: 0 0, 9px 9px;
}

.AssetCard-preview--favicon {
  min-height: 92px;
}

.AssetCard-image {
  max-width: 100%;
  display: block;
}

.AssetCard-image--logo {
  max-height: 72px;
}

.AssetCard-image--favicon {
  width: 48px;
  height: 48px;
  object-fit: contain;
}

.AssetCard-placeholder {
  color: #7b8794;
  font-size: 13px;
}

.AssetCard-meta {
  min-width: 0;
}

.AssetCard-title {
  margin-bottom: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #223245;
}

.AssetCard-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
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
  min-width: 0;
}

.Form-group--assetUrl {
  margin-left: 198px;
  max-width: calc(100% - 198px);
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
  min-width: 0;
  max-width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 3px;
  font-size: 14px;
  font-family: inherit;
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.FormControl:focus {
  outline: none;
  border-color: #4d698e;
}

.ColorPicker {
  display: flex;
  gap: 10px;
  align-items: center;
}

.ColorPicker-input {
  width: 60px;
  height: 40px;
  border: 1px solid #ddd;
  border-radius: 3px;
  cursor: pointer;
}

.ColorPicker-text {
  flex: 1;
  max-width: 200px;
}

.Form-help {
  margin: 6px 0 0 0;
  font-size: 13px;
  color: #999;
}

.Form-actions {
  display: flex;
  align-items: center;
  gap: 15px;
  padding-top: 10px;
}

.Button {
  border-radius: 6px;
}

.Button--primary {
  background: #4d698e;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 3px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.Button--primary:hover:not(:disabled) {
  background: #3d5875;
}

.Button--primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.Button--secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 16px;
  border: 1px solid #d4dde6;
  background: #fff;
  color: #435466;
}

.Button--upload {
  cursor: pointer;
}

.Button--upload.is-disabled {
  opacity: 0.6;
  pointer-events: none;
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
  .PresetPanel-header {
    flex-direction: column;
  }

  .AssetCard {
    grid-template-columns: 1fr;
  }

  .Form-group--assetUrl {
    margin-left: 0;
    max-width: none;
  }

  .AssetCard-preview {
    min-height: 96px;
  }
}
</style>
