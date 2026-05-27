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
      <div
        v-for="field in fields"
        :key="field.key"
        class="ExtensionGeneratedSettings-field"
      >
        <label :for="resolveFieldId(field.key)">{{ field.label }}</label>

        <input
          v-if="field.type === 'text' || field.type === 'number'"
          :id="resolveFieldId(field.key)"
          v-model="settings[field.key]"
          :type="field.type === 'number' ? 'number' : 'text'"
          class="FormControl"
          :placeholder="field.placeholder || ''"
        />

        <textarea
          v-else-if="field.type === 'textarea'"
          :id="resolveFieldId(field.key)"
          v-model="settings[field.key]"
          class="FormControl"
          rows="4"
          :placeholder="field.placeholder || ''"
        ></textarea>

        <AdminSelectMenu
          v-else-if="field.type === 'select'"
          :input-id="resolveFieldId(field.key)"
          v-model="settings[field.key]"
          :options="field.options || []"
          :placeholder="field.placeholder || '请选择'"
          :aria-label="field.label"
        />

        <label v-else-if="field.type === 'boolean'" class="ExtensionGeneratedSettings-toggle">
          <input
            :id="resolveFieldId(field.key)"
            v-model="settings[field.key]"
            type="checkbox"
            class="FormControl-checkbox"
          />
          <span>{{ field.help_text || '启用该设置项' }}</span>
        </label>

        <p v-if="field.type !== 'boolean' && field.help_text" class="Form-help">
          {{ field.help_text }}
        </p>
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
import AdminSelectMenu from '../components/AdminSelectMenu.vue'
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
    if (field.type === 'number') {
      const value = settings.value[field.key]
      payload[field.key] = value === '' || value === null || value === undefined ? '' : Number(value)
      continue
    }
    payload[field.key] = settings.value[field.key]
  }
  return payload
}

function resolveFieldId(key) {
  return `extension-generated-setting-${key}`
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

.ExtensionGeneratedSettings-field {
  display: grid;
  gap: 8px;
}

.ExtensionGeneratedSettings-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.ExtensionGeneratedSettings-actions {
  display: flex;
  justify-content: flex-start;
}
</style>
