<template>
  <section class="SampleHelloSettings">
    <header class="SampleHelloSettings-hero" :class="heroToneClass">
      <p class="SampleHelloSettings-kicker">Sample Hello</p>
      <h2>示例扩展设置</h2>
      <p>{{ welcomePreview }}</p>
    </header>

    <div class="SampleHelloSettings-grid">
      <article class="SampleHelloSettings-card">
        <small>扩展 ID</small>
        <strong>{{ extension?.id || 'sample-hello' }}</strong>
      </article>
      <article class="SampleHelloSettings-card">
        <small>当前入口</small>
        <strong>{{ hostKind === 'permissions' ? '权限页' : '设置页' }}</strong>
      </article>
      <article class="SampleHelloSettings-card">
        <small>设置项数量</small>
        <strong>{{ fields.length }}</strong>
      </article>
    </div>

    <AdminStateBlock v-if="loading" tone="subtle">加载扩展设置中...</AdminStateBlock>
    <AdminStateBlock v-else-if="loadError" tone="danger">{{ loadError }}</AdminStateBlock>

    <form v-else class="SampleHelloSettings-form" @submit.prevent="handleSubmit">
      <div
        v-for="field in fields"
        :key="field.key"
        class="SampleHelloSettings-field"
      >
        <label :for="`sample-setting-${field.key}`">{{ field.label }}</label>

        <input
          v-if="field.type === 'text' || field.type === 'number'"
          :id="`sample-setting-${field.key}`"
          v-model="settings[field.key]"
          :type="field.type === 'number' ? 'number' : 'text'"
          class="FormControl"
          :placeholder="field.placeholder || ''"
        />

        <textarea
          v-else-if="field.type === 'textarea'"
          :id="`sample-setting-${field.key}`"
          v-model="settings[field.key]"
          class="FormControl"
          rows="4"
          :placeholder="field.placeholder || ''"
        ></textarea>

        <select
          v-else-if="field.type === 'select'"
          :id="`sample-setting-${field.key}`"
          v-model="settings[field.key]"
          class="FormControl"
        >
          <option
            v-for="option in field.options || []"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>

        <label v-else-if="field.type === 'boolean'" class="SampleHelloSettings-toggle">
          <input
            :id="`sample-setting-${field.key}`"
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

      <div class="SampleHelloSettings-actions">
        <button type="submit" class="Button Button--primary" :disabled="saving">
          {{ saving ? '保存中...' : '保存扩展设置' }}
        </button>
      </div>

      <AdminInlineMessage v-if="saveSuccess" tone="success">扩展设置保存成功</AdminInlineMessage>
      <AdminInlineMessage v-if="saveError" tone="danger">
        {{ saveErrorMessage || '扩展设置保存失败，请重试' }}
      </AdminInlineMessage>

      <article
        v-if="showRuntimeTips"
        class="SampleHelloSettings-panel"
      >
        <h3>运行时提示</h3>
        <ul>
          <li>当前页面已经通过统一扩展设置 API 读写配置。</li>
          <li>后续第三方扩展可以直接复用这套 schema 和存储协议。</li>
        </ul>
      </article>
    </form>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import api from '@/api'
import AdminInlineMessage from '@/admin/components/AdminInlineMessage.vue'
import AdminStateBlock from '@/admin/components/AdminStateBlock.vue'
import { useAdminSaveFeedback } from '@/admin/composables/useAdminSaveFeedback'

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

const welcomePreview = computed(() => {
  return String(settings.value.welcome_message || '欢迎使用 Sample Hello').trim() || '欢迎使用 Sample Hello'
})

const showRuntimeTips = computed(() => {
  return Boolean(settings.value.show_runtime_tips)
})

const heroToneClass = computed(() => {
  const tone = String(settings.value.card_tone || 'primary')
  return `is-${tone}`
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
</script>

<style scoped>
.SampleHelloSettings {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.SampleHelloSettings-hero,
.SampleHelloSettings-card,
.SampleHelloSettings-panel,
.SampleHelloSettings-form {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.SampleHelloSettings-hero,
.SampleHelloSettings-panel,
.SampleHelloSettings-form {
  padding: 20px;
}

.SampleHelloSettings-hero.is-primary {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.SampleHelloSettings-hero.is-warm {
  border-color: rgba(180, 104, 39, 0.22);
  background: linear-gradient(135deg, rgba(180, 104, 39, 0.14), rgba(180, 104, 39, 0.04));
}

.SampleHelloSettings-hero.is-neutral {
  border-color: rgba(96, 104, 112, 0.2);
  background: linear-gradient(135deg, rgba(96, 104, 112, 0.12), rgba(96, 104, 112, 0.04));
}

.SampleHelloSettings-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.SampleHelloSettings-hero h2,
.SampleHelloSettings-panel h3 {
  margin: 0 0 10px;
}

.SampleHelloSettings-hero p:last-child,
.SampleHelloSettings-panel ul {
  margin: 0;
}

.SampleHelloSettings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.SampleHelloSettings-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.SampleHelloSettings-card small {
  color: var(--forum-text-soft);
}

.SampleHelloSettings-form {
  display: grid;
  gap: 16px;
}

.SampleHelloSettings-field {
  display: grid;
  gap: 8px;
}

.SampleHelloSettings-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.SampleHelloSettings-actions {
  display: flex;
  justify-content: flex-start;
}
</style>
