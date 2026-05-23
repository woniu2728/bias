<template>
  <AdminPage
    class-name="BasicsPage"
    icon="fas fa-pencil-alt"
    :title="basicsCopy?.pageTitle || '基础设置'"
    :description="basicsCopy?.pageDescription || '配置论坛的基本信息'"
  >
    <AdminStateBlock v-if="loading" tone="subtle">{{ basicsCopy?.loadingText || '加载基础设置中...' }}</AdminStateBlock>
    <AdminStateBlock v-else-if="loadError" tone="danger">{{ loadError }}</AdminStateBlock>
    <form v-else class="Form" @submit.prevent="handleSubmit">
      <div class="Form-group">
        <label for="basics-forum-title">{{ basicsCopy?.forumTitleLabel || '论坛名称' }}</label>
        <input
          id="basics-forum-title"
          v-model="settings.forum_title"
          name="forum_title"
          type="text"
          class="FormControl"
          :placeholder="basicsConfig?.placeholders?.forumTitle || '我的论坛'"
        />
        <p class="Form-help">{{ basicsCopy?.forumTitleHelpText || '论坛的名称，显示在页面标题和头部' }}</p>
      </div>

      <div class="Form-group">
        <label for="basics-forum-description">{{ basicsCopy?.forumDescriptionLabel || '论坛描述' }}</label>
        <textarea
          id="basics-forum-description"
          v-model="settings.forum_description"
          name="forum_description"
          class="FormControl"
          rows="3"
          :placeholder="basicsConfig?.placeholders?.forumDescription || '一个很棒的社区'"
        ></textarea>
        <p class="Form-help">{{ basicsCopy?.forumDescriptionHelpText || '简短描述你的论坛，用于 SEO' }}</p>
      </div>

      <section class="Form-section">
        <div class="Form-sectionHeader">
          <h3>{{ basicsCopy?.seoSectionTitle || 'SEO 设置' }}</h3>
          <p>{{ basicsCopy?.seoSectionDescription || '这些字段会进入公开论坛设置，并在前台页面标题与 meta 标签中生效。' }}</p>
        </div>

        <div class="Form-group">
          <label for="basics-seo-title">{{ basicsCopy?.seoTitleLabel || 'SEO 标题' }}</label>
          <input
            id="basics-seo-title"
            v-model="settings.seo_title"
            name="seo_title"
            type="text"
            class="FormControl"
            :placeholder="basicsConfig?.placeholders?.seoTitle || '留空时使用论坛名称'"
          />
          <p class="Form-help">{{ basicsCopy?.seoTitleHelpText || '建议控制在 30-60 字符，留空时自动回退到论坛名称。' }}</p>
        </div>

        <div class="Form-group">
          <label for="basics-seo-description">{{ basicsCopy?.seoDescriptionLabel || 'SEO 描述' }}</label>
          <textarea
            id="basics-seo-description"
            v-model="settings.seo_description"
            name="seo_description"
            class="FormControl"
            rows="3"
            :placeholder="basicsConfig?.placeholders?.seoDescription || '留空时使用论坛描述'"
          ></textarea>
          <p class="Form-help">{{ basicsCopy?.seoDescriptionHelpText || '建议控制在 80-160 字符，留空时自动回退到论坛描述。' }}</p>
        </div>

        <div class="Form-group">
          <label for="basics-seo-keywords">{{ basicsCopy?.seoKeywordsLabel || 'SEO 关键词' }}</label>
          <input
            id="basics-seo-keywords"
            v-model="settings.seo_keywords"
            name="seo_keywords"
            type="text"
            class="FormControl"
            :placeholder="basicsConfig?.placeholders?.seoKeywords || '论坛, 社区, 技术讨论'"
          />
          <p class="Form-help">{{ basicsCopy?.seoKeywordsHelpText || '使用英文逗号分隔多个关键词，例如：Python, Django, Vue。' }}</p>
        </div>

        <div class="Form-grid">
          <label class="Form-toggle">
            <input
              v-model="settings.seo_robots_index"
              name="seo_robots_index"
              type="checkbox"
              class="FormControl-checkbox"
            />
            <span>{{ basicsCopy?.seoRobotsIndexLabel || '允许搜索引擎建立索引' }}</span>
          </label>

          <label class="Form-toggle">
            <input
              v-model="settings.seo_robots_follow"
              name="seo_robots_follow"
              type="checkbox"
              class="FormControl-checkbox"
            />
            <span>{{ basicsCopy?.seoRobotsFollowLabel || '允许搜索引擎跟踪页面链接' }}</span>
          </label>
        </div>

        <div class="Form-note Form-note--compact">
          {{ basicsCopy?.seoNoteText || 'SEO 设置保存后，对外访问的论坛页面通常刷新即可生效；若站点前面接了 CDN 或反向代理缓存，请同步清理缓存。' }}
        </div>
      </section>

      <section class="Form-section">
        <div class="Form-sectionHeader">
          <h3>{{ basicsCopy?.announcementSectionTitle || '站点公告' }}</h3>
          <p>{{ basicsCopy?.announcementSectionDescription || '在前台顶部展示一条全站公告，适合发布维护预告、运营通知或临时提醒。' }}</p>
        </div>

        <label class="Form-toggle Announcement-toggle">
          <input
            v-model="settings.announcement_enabled"
            name="announcement_enabled"
            type="checkbox"
            class="FormControl-checkbox"
          />
          <span>{{ basicsCopy?.announcementEnabledLabel || '启用全站公告' }}</span>
        </label>

        <div class="Form-group">
          <label for="basics-announcement-message">{{ basicsCopy?.announcementMessageLabel || '公告内容' }}</label>
          <textarea
            id="basics-announcement-message"
            v-model="settings.announcement_message"
            name="announcement_message"
            class="FormControl"
            rows="3"
            maxlength="240"
            :placeholder="basicsConfig?.placeholders?.announcementMessage || '例如：今晚 23:00-23:30 将进行短暂维护。'"
          ></textarea>
          <p class="Form-help">{{ basicsCopy?.announcementMessageHelpText || '最多 240 个字符，内容为空时前台不会展示公告。' }}</p>
        </div>

        <div class="Form-group">
          <label for="basics-announcement-tone">{{ basicsCopy?.announcementToneLabel || '公告样式' }}</label>
          <select
            id="basics-announcement-tone"
            v-model="settings.announcement_tone"
            name="announcement_tone"
            class="FormControl"
          >
            <option v-for="option in announcementToneOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>
      </section>

      <div class="Form-actions">
        <button
          type="submit"
          class="Button Button--primary"
          :disabled="saving"
        >
          {{ saving ? (basicsCopy?.savingLabel || '保存中...') : (basicsCopy?.saveLabel || '保存设置') }}
        </button>
      </div>
      <AdminInlineMessage v-if="saveSuccess" tone="success">{{ basicsCopy?.saveSuccessText || '保存成功' }}</AdminInlineMessage>
      <AdminInlineMessage v-if="saveError" tone="danger">{{ basicsCopy?.saveErrorText || '保存失败，请重试' }}</AdminInlineMessage>
    </form>
  </AdminPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import AdminInlineMessage from '../components/AdminInlineMessage.vue'
import AdminPage from '../components/AdminPage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import { useAdminSaveFeedback } from '../composables/useAdminSaveFeedback'
import api from '../../api'
import {
  getAdminBasicsPageActionMeta,
  getAdminBasicsPageConfig,
  getAdminBasicsPageCopy,
} from '../registry'

const basicsCopy = computed(() => getAdminBasicsPageCopy())
const basicsConfig = computed(() => getAdminBasicsPageConfig())
const basicsActionMeta = computed(() => getAdminBasicsPageActionMeta())
const settings = ref({})
const saving = ref(false)
const loading = ref(true)
const loadError = ref('')
const { saveSuccess, saveError, resetSaveFeedback, showSaveSuccess, showSaveError } = useAdminSaveFeedback()
const announcementToneOptions = computed(() => basicsConfig.value?.announcementToneOptions || [])

function defaultSettings() {
  return {
    forum_title: '',
    forum_description: '',
    seo_title: '',
    seo_description: '',
    seo_keywords: '',
    seo_robots_index: true,
    seo_robots_follow: true,
    announcement_enabled: false,
    announcement_message: '',
    announcement_tone: 'info',
    ...(basicsConfig.value?.defaultSettings || {}),
  }
}

onMounted(async () => {
  settings.value = defaultSettings()
  loading.value = true
  loadError.value = ''
  try {
    const data = await api.get('/admin/settings')
    settings.value = {
      ...settings.value,
      forum_title: data.forum_title || '',
      forum_description: data.forum_description || '',
      seo_title: data.seo_title || '',
      seo_description: data.seo_description || '',
      seo_keywords: data.seo_keywords || '',
      seo_robots_index: data.seo_robots_index !== false,
      seo_robots_follow: data.seo_robots_follow !== false,
      announcement_enabled: Boolean(data.announcement_enabled),
      announcement_message: data.announcement_message || '',
      announcement_tone: ['info', 'warning', 'success'].includes(data.announcement_tone) ? data.announcement_tone : 'info',
    }
  } catch (error) {
    console.error('加载设置失败:', error)
    loadError.value = error.response?.data?.error || error.message || basicsActionMeta.value?.loadErrorText || '加载设置失败，请稍后重试'
  } finally {
    loading.value = false
  }
})

async function handleSubmit() {
  saving.value = true
  resetSaveFeedback()

  try {
    await api.post('/admin/settings', settings.value)
    showSaveSuccess()
  } catch (error) {
    console.error('保存设置失败:', error)
    showSaveError()
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.Form {
  max-width: 600px;
}

.Form-section {
  padding: 18px 18px 4px;
  background: var(--forum-bg-elevated-strong);
}

.Form-sectionHeader h3 {
  font-size: 15px;
}

.Form-note {
  margin-bottom: 25px;
}

.Form-note--compact {
  margin-top: -6px;
  margin-bottom: 20px;
}

.Form-grid {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  margin-bottom: 22px;
}

.Form-toggle {
  min-height: 48px;
  padding: 12px 14px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  background: var(--forum-bg-elevated);
}

.Form-actions {
  padding-top: 10px;
}

.Announcement-toggle {
  margin-bottom: 20px;
}

@media (max-width: 768px) {
  .Form {
    max-width: none;
  }

  .Form-section {
    padding: 16px 16px 2px;
    border-radius: 14px;
  }

  .Form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
