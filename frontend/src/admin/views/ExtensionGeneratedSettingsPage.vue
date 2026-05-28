<template>
  <section class="ExtensionGeneratedSettings">
    <header class="ExtensionGeneratedSettings-hero">
      <p class="ExtensionGeneratedSettings-kicker">Extension Settings</p>
      <h2>{{ extension?.name || '扩展设置' }}</h2>
      <p>{{ heroDescription }}</p>
    </header>

    <div class="ExtensionGeneratedSettings-grid">
      <article class="ExtensionGeneratedSettings-card">
        <small>扩展 ID</small>
        <strong>{{ extension?.id || 'unknown' }}</strong>
      </article>
      <article class="ExtensionGeneratedSettings-card">
        <small>设置项数量</small>
        <strong>{{ fields.length }}</strong>
      </article>
      <article class="ExtensionGeneratedSettings-card">
        <small>当前入口</small>
        <strong>{{ hostKindLabel }}</strong>
      </article>
    </div>

    <AdminStateBlock v-if="loading" tone="subtle">加载扩展设置中...</AdminStateBlock>
    <AdminStateBlock v-else-if="loadError" tone="danger">{{ loadError }}</AdminStateBlock>
    <AdminStateBlock v-else-if="!fields.length" tone="subtle">当前扩展未声明可配置项。</AdminStateBlock>

    <form v-else class="ExtensionGeneratedSettings-form" @submit.prevent="handleSubmit">
      <div class="ExtensionGeneratedSettings-layout">
        <section class="ExtensionGeneratedSettings-fieldsCard">
          <header class="ExtensionGeneratedSettings-sectionHead">
            <div>
              <h3>设置项</h3>
              <p>由扩展声明的 `settings_schema` 自动生成。</p>
            </div>
          </header>

          <div class="ExtensionGeneratedSettings-fields">
            <AdminSettingField
              v-for="field in fields"
              :key="field.key"
              :field="field"
              :model-value="settings[field.key]"
              @update:modelValue="settings[field.key] = $event"
            />
          </div>
        </section>

        <aside class="ExtensionGeneratedSettings-sideCard">
          <h3>当前宿主</h3>
          <dl class="ExtensionGeneratedSettings-sideMeta">
            <div>
              <dt>承载方式</dt>
              <dd>自动生成表单</dd>
            </div>
            <div>
              <dt>入口类型</dt>
              <dd>{{ hostKindLabel }}</dd>
            </div>
            <div>
              <dt>字段数量</dt>
              <dd>{{ fields.length }}</dd>
            </div>
          </dl>
        </aside>
      </div>

      <div class="ExtensionGeneratedSettings-actions">
        <button type="submit" class="Button Button--primary" :disabled="saving">
          {{ saving ? '保存中...' : '保存扩展设置' }}
        </button>
      </div>

      <AdminInlineMessage v-if="saveSuccess" tone="success">扩展设置保存成功</AdminInlineMessage>
      <AdminInlineMessage v-if="saveError" tone="danger">
        {{ saveErrorMessage || '扩展设置保存失败，请稍后重试' }}
      </AdminInlineMessage>
    </form>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import api from '../../api'
import AdminInlineMessage from '../components/AdminInlineMessage.vue'
import AdminSettingField from '../components/AdminSettingField.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import { useAdminSaveFeedback } from '../composables/useAdminSaveFeedback'

const props = defineProps({
  extension: {
    type: Object,
    default: null,
  },
  hostKind: {
    type: String,
    default: 'settings',
  },
})

const loading = ref(true)
const saving = ref(false)
const loadError = ref('')
const fields = ref([])
const settings = ref({})
const { saveSuccess, saveError, saveErrorMessage, resetSaveFeedback, showSaveSuccess, showSaveError } = useAdminSaveFeedback()

const hostKindLabel = computed(() => {
  if (props.hostKind === 'permissions') return '权限页'
  if (props.hostKind === 'operations') return '操作页'
  return '设置页'
})

const heroDescription = computed(() => {
  const name = props.extension?.name || '当前扩展'
  return `${name} 未提供自定义设置组件，当前页面已按统一 schema 自动生成设置表单。`
})

onMounted(async () => {
  await loadSettings()
})

watch(
  () => props.extension?.id,
  async () => {
    await loadSettings()
  }
)

async function loadSettings() {
  if (!props.extension?.id) {
    loading.value = false
    fields.value = []
    settings.value = {}
    return
  }

  loading.value = true
  loadError.value = ''
  resetSaveFeedback()

  try {
    const data = await api.get(`/admin/extensions/${props.extension.id}/settings`)
    fields.value = Array.isArray(data.schema) ? data.schema : []
    settings.value = { ...(data.settings || {}) }
  } catch (error) {
    console.error('加载扩展设置失败:', error)
    loadError.value = error.response?.data?.error || '加载扩展设置失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!props.extension?.id) {
    return
  }

  saving.value = true
  resetSaveFeedback()

  try {
    const payload = buildSubmitPayload()
    const data = await api.post(`/admin/extensions/${props.extension.id}/settings`, payload)
    settings.value = { ...(data.settings || settings.value) }
    showSaveSuccess()
  } catch (error) {
    console.error('保存扩展设置失败:', error)
    showSaveError(error.response?.data?.error || '保存扩展设置失败，请稍后重试')
  } finally {
    saving.value = false
  }
}

function buildSubmitPayload() {
  const payload = {}
  for (const field of fields.value) {
    payload[field.key] = settings.value[field.key]
  }
  return payload
}
</script>

<style scoped>
.ExtensionGeneratedSettings {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.ExtensionGeneratedSettings-hero,
.ExtensionGeneratedSettings-card,
.ExtensionGeneratedSettings-form {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.ExtensionGeneratedSettings-hero,
.ExtensionGeneratedSettings-form {
  padding: 20px;
}

.ExtensionGeneratedSettings-hero {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.ExtensionGeneratedSettings-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.ExtensionGeneratedSettings-hero h2 {
  margin: 0 0 10px;
}

.ExtensionGeneratedSettings-hero p:last-child {
  margin: 0;
}

.ExtensionGeneratedSettings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.ExtensionGeneratedSettings-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.ExtensionGeneratedSettings-card small {
  color: var(--forum-text-soft);
}

.ExtensionGeneratedSettings-form {
  display: grid;
  gap: 16px;
}

.ExtensionGeneratedSettings-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 16px;
  align-items: start;
}

.ExtensionGeneratedSettings-fieldsCard,
.ExtensionGeneratedSettings-sideCard {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-subtle);
  padding: 18px;
}

.ExtensionGeneratedSettings-sectionHead {
  margin-bottom: 16px;
}

.ExtensionGeneratedSettings-sectionHead h3,
.ExtensionGeneratedSettings-sideCard h3 {
  margin: 0 0 8px;
}

.ExtensionGeneratedSettings-sectionHead p {
  margin: 0;
  color: var(--forum-text-soft);
}

.ExtensionGeneratedSettings-fields {
  display: grid;
  gap: 16px;
}

.ExtensionGeneratedSettings-sideMeta {
  display: grid;
  gap: 14px;
  margin: 0;
}

.ExtensionGeneratedSettings-sideMeta div {
  display: grid;
  gap: 4px;
}

.ExtensionGeneratedSettings-sideMeta dt {
  color: var(--forum-text-soft);
}

.ExtensionGeneratedSettings-sideMeta dd {
  margin: 0;
  color: var(--forum-text-color);
  font-weight: 600;
}

.ExtensionGeneratedSettings-actions {
  display: flex;
  justify-content: flex-start;
}

@media (max-width: 900px) {
  .ExtensionGeneratedSettings-layout {
    grid-template-columns: 1fr;
  }
}
</style>
