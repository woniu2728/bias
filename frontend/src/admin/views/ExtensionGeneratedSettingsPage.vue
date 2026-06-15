<template>
  <section class="ExtensionGeneratedSettings">
    <AdminStateBlock v-if="loading" tone="subtle">加载扩展设置中...</AdminStateBlock>
    <AdminStateBlock v-else-if="loadError" tone="danger">{{ loadError }}</AdminStateBlock>
    <AdminStateBlock v-else-if="!fields.length" tone="subtle">当前扩展未声明可配置项。</AdminStateBlock>

    <form v-else class="ExtensionGeneratedSettings-form" @submit.prevent="handleSubmit">
      <div class="ExtensionGeneratedSettings-fields">
        <AdminSettingField
          v-for="field in fields"
          :key="field.key"
          :field="field"
          :model-value="settings[field.key]"
          @update:modelValue="settings[field.key] = $event"
        />
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
import { onMounted, ref, watch } from 'vue'
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
}

.ExtensionGeneratedSettings-form {
  display: grid;
  gap: 16px;
}

.ExtensionGeneratedSettings-fields {
  display: grid;
  gap: 16px;
}

.ExtensionGeneratedSettings-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
