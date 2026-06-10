<template>
  <AdminPage
    class-name="AppearancePage"
    icon="fas fa-paint-brush"
    :title="appearanceCopy?.pageTitle || '外观设置'"
    :description="appearanceCopy?.pageDescription || '自定义论坛的外观和主题'"
  >
    <AdminStateBlock v-if="loading" tone="subtle">{{ appearanceCopy?.loadingText || '加载外观配置中...' }}</AdminStateBlock>
    <AdminStateBlock v-else-if="loadError" tone="danger">{{ loadError }}</AdminStateBlock>
    <div v-else class="AppearancePage-content">
      <div class="AppearancePage-section">
        <h3 class="Section-title">{{ appearanceCopy?.colorsSectionTitle || '颜色' }}</h3>
        <div class="Form-group">
          <label for="appearance-primary-color">{{ appearanceCopy?.primaryColorLabel || '主题色' }}</label>
          <AdminColorField
            v-model="settings.primary_color"
            input-id="appearance-primary-color"
            picker-id="appearance-primary-color-picker"
            name="primary_color"
            picker-name="primary_color_picker"
            :aria-label="appearanceCopy?.primaryColorPickerAriaLabel || '主题色取色器'"
            :placeholder="appearanceConfig?.placeholders?.primaryColor || '#4d698e'"
          />
          <p class="Form-help">{{ appearanceCopy?.primaryColorHelpText || '论坛的主题颜色' }}</p>
        </div>

        <div class="Form-group">
          <label for="appearance-accent-color">{{ appearanceCopy?.accentColorLabel || '强调色' }}</label>
          <AdminColorField
            v-model="settings.accent_color"
            input-id="appearance-accent-color"
            picker-id="appearance-accent-color-picker"
            name="accent_color"
            picker-name="accent_color_picker"
            :aria-label="appearanceCopy?.accentColorPickerAriaLabel || '强调色取色器'"
            :placeholder="appearanceConfig?.placeholders?.accentColor || '#e74c3c'"
          />
          <p class="Form-help">{{ appearanceCopy?.accentColorHelpText || '用于按钮和链接的强调色' }}</p>
        </div>
      </div>

      <div class="AppearancePage-section">
        <h3 class="Section-title">{{ appearanceCopy?.brandingSectionTitle || 'Logo 与图标' }}</h3>
        <div class="AssetCard">
          <div class="AssetCard-preview">
            <img
              v-if="settings.logo_url"
              :src="settings.logo_url"
              :alt="appearanceCopy?.logoPreviewAlt || 'Logo 预览'"
              class="AssetCard-image AssetCard-image--logo"
            />
            <div v-else class="AssetCard-placeholder">{{ appearanceCopy?.logoEmptyText || '暂无 Logo' }}</div>
          </div>
          <div class="AssetCard-meta">
            <div class="AssetCard-title">{{ appearanceCopy?.logoCardTitle || '站点 Logo' }}</div>
            <p class="Form-help">{{ appearanceCopy?.logoHelpText || '建议上传透明背景 PNG、SVG 或 WebP，Header 会优先展示这里的资源。' }}</p>
            <div class="AssetCard-actions">
              <label v-if="uploadSiteAssetAction" class="Button Button--secondary Button--upload" :class="{ 'is-disabled': uploadingLogo }">
                <input
                  name="logo_file"
                  type="file"
                  :accept="appearanceConfig?.uploads?.logoAccept || '.png,.jpg,.jpeg,.gif,.webp,.svg'"
                  hidden
                  @change="uploadAsset($event, 'logo')"
                />
                {{ uploadingLogo ? (appearanceCopy?.logoUploadingLabel || '上传中...') : (appearanceCopy?.logoUploadLabel || '上传本地 Logo') }}
              </label>
              <button v-if="settings.logo_url" type="button" class="Button" @click="settings.logo_url = ''">{{ appearanceCopy?.clearAssetLabel || '清空' }}</button>
            </div>
          </div>
        </div>

        <div class="Form-group Form-group--assetUrl">
          <label for="appearance-logo-url">{{ appearanceCopy?.logoUrlLabel || 'Logo URL' }}</label>
          <input
            id="appearance-logo-url"
            v-model="settings.logo_url"
            name="logo_url"
            type="text"
            class="FormControl"
            :placeholder="appearanceConfig?.placeholders?.logoUrl || 'https://example.com/logo.png'"
          />
          <p class="Form-help">{{ appearanceCopy?.logoUrlHelpText || '论坛 Logo 的 URL 地址' }}</p>
        </div>

        <div class="AssetCard">
          <div class="AssetCard-preview AssetCard-preview--favicon">
            <img
              v-if="settings.favicon_url"
              :src="settings.favicon_url"
              :alt="appearanceCopy?.faviconPreviewAlt || 'Favicon 预览'"
              class="AssetCard-image AssetCard-image--favicon"
            />
            <div v-else class="AssetCard-placeholder">{{ appearanceCopy?.faviconEmptyText || '暂无 Favicon' }}</div>
          </div>
          <div class="AssetCard-meta">
            <div class="AssetCard-title">{{ appearanceCopy?.faviconCardTitle || '浏览器图标' }}</div>
            <p class="Form-help">{{ appearanceCopy?.faviconHelpText || '建议上传 `.ico`、PNG 或 SVG，小尺寸图标在浏览器标签页里更清晰。' }}</p>
            <div class="AssetCard-actions">
              <label v-if="uploadSiteAssetAction" class="Button Button--secondary Button--upload" :class="{ 'is-disabled': uploadingFavicon }">
                <input
                  name="favicon_file"
                  type="file"
                  :accept="appearanceConfig?.uploads?.faviconAccept || '.ico,.png,.svg,.webp'"
                  hidden
                  @change="uploadAsset($event, 'favicon')"
                />
                {{ uploadingFavicon ? (appearanceCopy?.faviconUploadingLabel || '上传中...') : (appearanceCopy?.faviconUploadLabel || '上传本地 Favicon') }}
              </label>
              <button v-if="settings.favicon_url" type="button" class="Button" @click="settings.favicon_url = ''">{{ appearanceCopy?.clearAssetLabel || '清空' }}</button>
            </div>
          </div>
        </div>

        <div class="Form-group Form-group--assetUrl">
          <label for="appearance-favicon-url">{{ appearanceCopy?.faviconUrlLabel || 'Favicon URL' }}</label>
          <input
            id="appearance-favicon-url"
            v-model="settings.favicon_url"
            name="favicon_url"
            type="text"
            class="FormControl"
            :placeholder="appearanceConfig?.placeholders?.faviconUrl || 'https://example.com/favicon.ico'"
          />
          <p class="Form-help">{{ appearanceCopy?.faviconUrlHelpText || '浏览器标签页图标的 URL 地址' }}</p>
        </div>
      </div>

      <div class="AppearancePage-section">
        <h3 class="Section-title">{{ appearanceCopy?.customStyleSectionTitle || '自定义样式' }}</h3>
        <div class="Form-group">
          <label for="appearance-custom-head">{{ appearanceCopy?.customHeadLabel || 'Head / 统计代码注入' }}</label>
          <textarea
            id="appearance-custom-head"
            v-model="settings.custom_head_html"
            name="custom_head_html"
            class="FormControl"
            rows="5"
            :placeholder="appearanceConfig?.placeholders?.customHead || '<!-- 在这里添加 head 注入或统计代码 -->'"
          ></textarea>
          <p class="Form-help">{{ appearanceCopy?.customHeadHelpText || '用于统计脚本、验证标签或其他不直接展示给用户的 Head 注入。' }}</p>
        </div>

        <div class="Form-group">
          <label for="appearance-custom-footer">{{ appearanceCopy?.customFooterLabel || 'Footer HTML' }}</label>
          <textarea
            id="appearance-custom-footer"
            v-model="settings.custom_footer_html"
            name="custom_footer_html"
            class="FormControl"
            rows="5"
            :placeholder="appearanceConfig?.placeholders?.customFooter || '<p>在页脚展示备案号、版权说明或联系信息</p>'"
          ></textarea>
          <p class="Form-help">{{ appearanceCopy?.customFooterHelpText || '这里的内容会直接显示在站点页脚，适合备案、版权和联系信息。' }}</p>
        </div>
      </div>

      <div class="Form-actions">
        <button
          type="button"
          class="Button Button--primary"
          :disabled="saving"
          @click="saveSettings"
        >
          {{ saving ? (appearanceCopy?.savingLabel || '保存中...') : (appearanceCopy?.saveLabel || '保存设置') }}
        </button>
      </div>
      <AdminInlineMessage v-if="saveSuccess" tone="success">{{ appearanceCopy?.saveSuccessText || '保存成功' }}</AdminInlineMessage>
      <AdminInlineMessage v-if="saveError" tone="danger">{{ appearanceCopy?.saveErrorText || '保存失败，请重试' }}</AdminInlineMessage>
    </div>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AdminColorField from '../components/AdminColorField.vue'
import AdminInlineMessage from '../components/AdminInlineMessage.vue'
import AdminPage from '../components/AdminPage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import { useAdminSaveFeedback } from '../composables/useAdminSaveFeedback'
import api from '../../api'
import { useModalStore } from '../../stores/modal'
import { useAdminRegistryStore } from '../../stores/adminRegistry'
import {
  getAdminAppearancePageAction,
  getAdminAppearancePageActionMeta,
  getAdminAppearancePageConfig,
  getAdminAppearancePageCopy,
} from '../registry'

const adminRegistryStore = useAdminRegistryStore()
const pageContext = computed(() => ({
  isModuleEnabled: moduleId => adminRegistryStore.isModuleEnabled(moduleId),
}))
const appearanceCopy = computed(() => getAdminAppearancePageCopy(pageContext.value))
const appearanceConfig = computed(() => getAdminAppearancePageConfig(pageContext.value))
const appearanceActionMeta = computed(() => getAdminAppearancePageActionMeta(pageContext.value))
const loading = ref(true)
const loadError = ref('')
const settings = ref({})
const saving = ref(false)
const uploadingLogo = ref(false)
const uploadingFavicon = ref(false)
const modalStore = useModalStore()
const { saveSuccess, saveError, resetSaveFeedback, showSaveSuccess, showSaveError } = useAdminSaveFeedback()
const uploadSiteAssetAction = computed(() => getAdminAppearancePageAction('upload-site-asset', {
  api,
  modalStore,
  appearanceActionMeta: appearanceActionMeta.value,
  ...pageContext.value,
  settings: settings.value,
  setUploading: (target, value) => {
    if (target === 'logo') {
      uploadingLogo.value = value
    } else {
      uploadingFavicon.value = value
    }
  },
}))

function buildDefaultSettings() {
  return {
    primary_color: '#4d698e',
    accent_color: '#e74c3c',
    logo_url: '',
    favicon_url: '',
    custom_head_html: '',
    custom_footer_html: '',
    ...(appearanceConfig.value?.defaultSettings || {}),
  }
}

onMounted(async () => {
  settings.value = buildDefaultSettings()
  loading.value = true
  loadError.value = ''
  try {
    const appearanceData = await api.get('/admin/appearance')
    const data = appearanceData
    settings.value = { ...settings.value, ...data }
  } catch (error) {
    console.error('加载外观设置失败:', error)
    loadError.value = error.response?.data?.error || error.message || appearanceActionMeta.value?.loadErrorText || '加载外观设置失败，请稍后重试'
  } finally {
    loading.value = false
  }
})

async function saveSettings() {
  saving.value = true
  resetSaveFeedback()

  try {
    await api.post('/admin/appearance', settings.value)
    showSaveSuccess()
  } catch (error) {
    console.error('保存外观设置失败:', error)
    showSaveError()
  } finally {
    saving.value = false
  }
}

async function uploadAsset(event, target) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return

  if (!uploadSiteAssetAction.value?.run) {
    return
  }
  await uploadSiteAssetAction.value.run({ file, target })
}
</script>

<style scoped>
.AppearancePage-content {
  max-width: 800px;
}

.AppearancePage-section {
  background: var(--forum-bg-elevated);
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: var(--forum-shadow-sm);
}

.AssetCard {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 18px;
  margin-bottom: 20px;
  padding: 16px;
  border: 1px solid var(--forum-border-soft);
  border-radius: var(--forum-radius-md);
  background: var(--forum-bg-elevated-strong);
}

.AssetCard-preview {
  display: grid;
  place-items: center;
  min-height: 110px;
  padding: 18px;
  border: 1px dashed var(--forum-border-strong);
  border-radius: var(--forum-radius-md);
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
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
}

.AssetCard-meta {
  min-width: 0;
}

.AssetCard-title {
  margin-bottom: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--forum-text-color);
}

.AssetCard-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.Section-title {
  margin: 0 0 20px 0;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--forum-border-soft);
}

.Form-group--assetUrl {
  margin-left: 198px;
  max-width: calc(100% - 198px);
}

.Button {
  border-radius: var(--forum-radius-md);
}

.Button--secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 16px;
  border: 1px solid var(--forum-border-color);
  background: var(--forum-bg-elevated);
  color: var(--forum-text-muted);
}

.Button--upload {
  cursor: pointer;
}

.Button--upload.is-disabled {
  opacity: 0.6;
  pointer-events: none;
}

@media (max-width: 768px) {
  .AppearancePage-content {
    max-width: none;
  }

  .AppearancePage-section,
  .AppearancePage-section {
    padding: 16px;
    border-radius: 14px;
  }

  .AssetCard {
    grid-template-columns: 1fr;
    padding: 14px;
  }

  .Form-group--assetUrl {
    margin-left: 0;
    max-width: none;
  }

  .AssetCard-preview {
    min-height: 96px;
  }

  .Form-actions {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .Form-actions .Button {
    width: 100%;
    justify-content: center;
  }
}
</style>
