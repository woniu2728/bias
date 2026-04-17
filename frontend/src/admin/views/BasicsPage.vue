<template>
  <AdminPage
    className="BasicsPage"
    icon="fas fa-pencil-alt"
    title="基础设置"
    description="配置论坛的基本信息"
  >
    <form @submit.prevent="handleSubmit" class="Form">
      <div class="Form-group">
        <label>论坛名称</label>
        <input
          v-model="settings.forum_title"
          type="text"
          class="FormControl"
          placeholder="我的论坛"
        />
        <p class="Form-help">论坛的名称，显示在页面标题和头部</p>
      </div>

      <div class="Form-group">
        <label>论坛描述</label>
        <textarea
          v-model="settings.forum_description"
          class="FormControl"
          rows="3"
          placeholder="一个很棒的社区"
        ></textarea>
        <p class="Form-help">简短描述你的论坛，用于SEO</p>
      </div>

      <section class="Form-section">
        <div class="Form-sectionHeader">
          <h3>SEO 设置</h3>
          <p>这些字段会进入公开论坛设置，并在前台页面标题与 meta 标签中生效。</p>
        </div>

        <div class="Form-group">
          <label>SEO 标题</label>
          <input
            v-model="settings.seo_title"
            type="text"
            class="FormControl"
            placeholder="留空时使用论坛名称"
          />
          <p class="Form-help">建议控制在 30-60 字符，留空时自动回退到论坛名称。</p>
        </div>

        <div class="Form-group">
          <label>SEO 描述</label>
          <textarea
            v-model="settings.seo_description"
            class="FormControl"
            rows="3"
            placeholder="留空时使用论坛描述"
          ></textarea>
          <p class="Form-help">建议控制在 80-160 字符，留空时自动回退到论坛描述。</p>
        </div>

        <div class="Form-group">
          <label>SEO 关键词</label>
          <input
            v-model="settings.seo_keywords"
            type="text"
            class="FormControl"
            placeholder="论坛, 社区, 技术讨论"
          />
          <p class="Form-help">使用英文逗号分隔多个关键词，例如：Python, Django, Vue。</p>
        </div>

        <div class="Form-grid">
          <label class="Form-toggle">
            <input
              v-model="settings.seo_robots_index"
              type="checkbox"
              class="FormControl-checkbox"
            />
            <span>允许搜索引擎建立索引</span>
          </label>

          <label class="Form-toggle">
            <input
              v-model="settings.seo_robots_follow"
              type="checkbox"
              class="FormControl-checkbox"
            />
            <span>允许搜索引擎跟踪页面链接</span>
          </label>
        </div>

        <div class="Form-note Form-note--compact">
          SEO 设置保存后，对外访问的论坛页面通常刷新即可生效；若站点前面接了 CDN 或反向代理缓存，请同步清理缓存。
        </div>
      </section>

      <div class="Form-group">
        <label>默认语言</label>
        <select v-model="settings.default_locale" class="FormControl">
          <option value="zh-CN">简体中文</option>
          <option value="en">English</option>
        </select>
      </div>

      <div class="Form-group">
        <label>
          <input
            v-model="settings.show_language_selector"
            type="checkbox"
            class="FormControl-checkbox"
          />
          显示语言选择器
        </label>
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
  forum_title: '',
  forum_description: '',
  seo_title: '',
  seo_description: '',
  seo_keywords: '',
  seo_robots_index: true,
  seo_robots_follow: true,
  default_locale: 'zh-CN',
  show_language_selector: false,
})

const saving = ref(false)
const saveSuccess = ref(false)
const saveError = ref(false)

onMounted(async () => {
  try {
    const data = await api.get('/admin/settings')
    settings.value = {
      forum_title: data.forum_title || '',
      forum_description: data.forum_description || '',
      seo_title: data.seo_title || '',
      seo_description: data.seo_description || '',
      seo_keywords: data.seo_keywords || '',
      seo_robots_index: data.seo_robots_index !== false,
      seo_robots_follow: data.seo_robots_follow !== false,
      default_locale: data.default_locale || 'zh-CN',
      show_language_selector: Boolean(data.show_language_selector),
    }
  } catch (error) {
    console.error('加载设置失败:', error)
  }
})

async function handleSubmit() {
  saving.value = true
  saveSuccess.value = false
  saveError.value = false

  try {
    await api.post('/admin/settings', settings.value)
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  } catch (error) {
    console.error('保存设置失败:', error)
    saveError.value = true
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.Form {
  max-width: 600px;
}

.Form-group {
  margin-bottom: 25px;
}

.Form-section {
  margin-bottom: 28px;
  padding: 18px 18px 4px;
  border: 1px solid #e6ebf0;
  border-radius: 10px;
  background: #fbfcfe;
}

.Form-sectionHeader {
  margin-bottom: 18px;
}

.Form-sectionHeader h3 {
  margin: 0 0 6px;
  font-size: 15px;
  color: #243447;
}

.Form-sectionHeader p {
  margin: 0;
  color: #6b7a89;
  line-height: 1.6;
  font-size: 13px;
}

.Form-note {
  margin-bottom: 25px;
  padding: 12px 14px;
  border-radius: 8px;
  background: #f5f8fb;
  color: #617282;
  line-height: 1.6;
  font-size: 13px;
}

.Form-note--compact {
  margin-top: -6px;
  margin-bottom: 20px;
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

.FormControl-checkbox {
  width: auto;
  margin-right: 8px;
}

.Form-help {
  margin: 6px 0 0 0;
  font-size: 13px;
  color: #999;
}

.Form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 22px;
}

.Form-toggle {
  display: flex !important;
  align-items: center;
  gap: 10px;
  min-height: 48px;
  padding: 12px 14px;
  border: 1px solid #dde5ec;
  border-radius: 8px;
  background: white;
}

.Form-actions {
  display: flex;
  align-items: center;
  gap: 15px;
  padding-top: 10px;
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
