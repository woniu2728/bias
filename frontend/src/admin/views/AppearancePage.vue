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
          <div class="ColorPicker">
            <input
              id="appearance-primary-color-picker"
              v-model="settings.primary_color"
              name="primary_color_picker"
              type="color"
              class="ColorPicker-input"
              :aria-label="appearanceCopy?.primaryColorPickerAriaLabel || '主题色取色器'"
            />
            <input
              id="appearance-primary-color"
              v-model="settings.primary_color"
              name="primary_color"
              type="text"
              class="FormControl ColorPicker-text"
              :placeholder="appearanceConfig?.placeholders?.primaryColor || '#4d698e'"
            />
          </div>
          <p class="Form-help">{{ appearanceCopy?.primaryColorHelpText || '论坛的主题颜色' }}</p>
        </div>

        <div class="Form-group">
          <label for="appearance-accent-color">{{ appearanceCopy?.accentColorLabel || '强调色' }}</label>
          <div class="ColorPicker">
            <input
              id="appearance-accent-color-picker"
              v-model="settings.accent_color"
              name="accent_color_picker"
              type="color"
              class="ColorPicker-input"
              :aria-label="appearanceCopy?.accentColorPickerAriaLabel || '强调色取色器'"
            />
            <input
              id="appearance-accent-color"
              v-model="settings.accent_color"
              name="accent_color"
              type="text"
              class="FormControl ColorPicker-text"
              :placeholder="appearanceConfig?.placeholders?.accentColor || '#e74c3c'"
            />
          </div>
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
              <label class="Button Button--secondary Button--upload" :class="{ 'is-disabled': uploadingLogo }">
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
              <label class="Button Button--secondary Button--upload" :class="{ 'is-disabled': uploadingFavicon }">
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
          <label for="appearance-custom-css">{{ appearanceCopy?.customCssLabel || '自定义 CSS' }}</label>
          <textarea
            id="appearance-custom-css"
            v-model="settings.custom_css"
            name="custom_css"
            class="FormControl"
            rows="10"
            :placeholder="appearanceConfig?.placeholders?.customCss || '/* 在这里添加自定义 CSS */'"
          ></textarea>
          <p class="Form-help">{{ appearanceCopy?.customCssHelpText || '添加自定义 CSS 样式来进一步定制论坛外观' }}</p>
        </div>

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

      <div class="AppearancePage-section">
        <h3 class="Section-title">{{ appearanceCopy?.previewSectionTitle || '实时预览' }}</h3>
        <div class="AppearancePreviewCard">
          <div class="AppearancePreviewShell" :style="previewStyleVars">
            <div class="AppearancePreviewHeader">
              <div class="AppearancePreviewLogo">
                <span>{{ settings.logo_url ? (appearanceCopy?.previewLogoText || 'Logo') : (settings.primary_color || '#4d698e').toUpperCase().slice(0, 7) }}</span>
              </div>
              <div class="AppearancePreviewHeaderText">
                <strong>{{ settings.primary_color || '#4d698e' }}</strong>
                <span>{{ settings.accent_color || '#e74c3c' }}</span>
              </div>
            </div>
            <div class="AppearancePreviewHero">
              <h4>{{ previewTitleText }}</h4>
              <p>{{ previewDescriptionText }}</p>
              <div class="AppearancePreviewActions">
                <button type="button" class="AppearancePreviewPrimary">{{ appearanceCopy?.previewPrimaryActionLabel || '主操作' }}</button>
                <button type="button" class="AppearancePreviewSecondary">{{ appearanceCopy?.previewSecondaryActionLabel || '次操作' }}</button>
              </div>
            </div>
            <div v-if="settings.custom_footer_html" class="AppearancePreviewFooter" v-html="settings.custom_footer_html"></div>
            <div v-else class="AppearancePreviewFooter AppearancePreviewFooter--placeholder">
              {{ appearanceCopy?.previewFooterPlaceholder || '页脚自定义内容会显示在这里。' }}
            </div>
          </div>
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
import AdminInlineMessage from '../components/AdminInlineMessage.vue'
import AdminPage from '../components/AdminPage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import { useAdminSaveFeedback } from '../composables/useAdminSaveFeedback'
import api from '../../api'
import { useModalStore } from '../../stores/modal'
import {
  getAdminAppearancePageActionMeta,
  getAdminAppearancePageConfig,
  getAdminAppearancePageCopy,
} from '../registry'

const appearanceCopy = computed(() => getAdminAppearancePageCopy())
const appearanceConfig = computed(() => getAdminAppearancePageConfig())
const appearanceActionMeta = computed(() => getAdminAppearancePageActionMeta())
const loading = ref(true)
const loadError = ref('')
const settings = ref({})
const previewContent = ref({
  forum_title: 'Bias',
  forum_description: '这里会预览首页说明和页脚内容。',
})
const saving = ref(false)
const uploadingLogo = ref(false)
const uploadingFavicon = ref(false)
const modalStore = useModalStore()
const { saveSuccess, saveError, resetSaveFeedback, showSaveSuccess, showSaveError } = useAdminSaveFeedback()
const previewTitleText = computed(() => String(previewContent.value.forum_title || 'Bias').trim() || 'Bias')
const previewDescriptionText = computed(() => String(previewContent.value.forum_description || '这里会预览首页说明和页脚内容。').trim() || '这里会预览首页说明和页脚内容。')
const previewStyleVars = computed(() => ({
  '--appearance-preview-primary': settings.value.primary_color || '#4d698e',
  '--appearance-preview-accent': settings.value.accent_color || '#e74c3c',
}))

function buildDefaultSettings() {
  return {
    primary_color: '#4d698e',
    accent_color: '#e74c3c',
    logo_url: '',
    favicon_url: '',
    custom_css: '',
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
    const [appearanceData, basicsData] = await Promise.all([
      api.get('/admin/appearance'),
      api.get('/admin/settings'),
    ])
    const data = appearanceData
    settings.value = { ...settings.value, ...data }
    previewContent.value = {
      forum_title: basicsData.forum_title || 'Bias',
      forum_description: basicsData.forum_description || '这里会预览首页说明和页脚内容。',
    }
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
    await modalStore.alert({
      title: appearanceActionMeta.value?.uploadFailedTitle || '上传失败',
      message: error.response?.data?.error || error.message || appearanceActionMeta.value?.uploadUnknownErrorText || '未知错误',
      tone: 'danger'
    })
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

.ColorPicker {
  display: flex;
  gap: 10px;
  align-items: center;
}

.ColorPicker-input {
  width: 60px;
  height: 40px;
  border: 1px solid var(--forum-border-strong);
  border-radius: var(--forum-radius-sm);
  cursor: pointer;
}

.ColorPicker-text {
  flex: 1;
  max-width: 200px;
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

.AppearancePreviewCard {
  border: 1px solid var(--forum-border-soft);
  border-radius: var(--forum-radius-md);
  background: var(--forum-bg-elevated-strong);
  padding: 16px;
}

.AppearancePreviewShell {
  --appearance-preview-primary: #4d698e;
  --appearance-preview-accent: #e74c3c;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid rgba(36, 52, 71, 0.08);
  background:
    radial-gradient(circle at top left, color-mix(in srgb, var(--appearance-preview-primary) 16%, white) 0%, transparent 36%),
    linear-gradient(180deg, #ffffff 0%, #f7fafc 100%);
}

.AppearancePreviewHeader {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px 0;
}

.AppearancePreviewLogo {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--appearance-preview-primary) 0%, var(--appearance-preview-accent) 100%);
  color: white;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
}

.AppearancePreviewHeaderText {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.AppearancePreviewHeaderText strong {
  color: var(--forum-text-color);
}

.AppearancePreviewHeaderText span {
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-sm);
}

.AppearancePreviewHero {
  padding: 18px 20px 20px;
}

.AppearancePreviewHero h4 {
  margin: 0 0 10px;
  font-size: 26px;
  color: #13202f;
}

.AppearancePreviewHero p {
  margin: 0;
  color: #546577;
  line-height: 1.7;
}

.AppearancePreviewActions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.AppearancePreviewPrimary,
.AppearancePreviewSecondary {
  min-height: 38px;
  padding: 0 16px;
  border-radius: 999px;
  font-weight: 600;
}

.AppearancePreviewPrimary {
  background: var(--appearance-preview-primary);
  color: white;
}

.AppearancePreviewSecondary {
  background: white;
  color: #213243;
  border: 1px solid rgba(36, 52, 71, 0.12);
}

.AppearancePreviewFooter {
  border-top: 1px solid rgba(36, 52, 71, 0.08);
  background: rgba(255, 255, 255, 0.82);
  padding: 14px 20px 18px;
  color: #607080;
  font-size: var(--forum-font-size-sm);
}

.AppearancePreviewFooter--placeholder {
  color: var(--forum-text-soft);
}

.AppearancePreviewFooter :deep(p) {
  margin: 0;
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

  .ColorPicker {
    flex-direction: column;
    align-items: stretch;
  }

  .ColorPicker-text {
    max-width: none;
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

  .AppearancePreviewActions {
    flex-direction: column;
  }
}
</style>
