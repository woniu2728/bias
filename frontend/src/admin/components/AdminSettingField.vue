<template>
  <div class="AdminSettingField">
    <label class="AdminSettingField-label" :for="fieldId">
      {{ field.label }}
      <span v-if="field.required" class="AdminSettingField-required">*</span>
    </label>

    <input
      v-if="field.type === 'text' || field.type === 'number'"
      :id="fieldId"
      :value="modelValue"
      :type="field.type === 'number' ? 'number' : 'text'"
      class="FormControl"
      :placeholder="field.placeholder || ''"
      :aria-label="field.label"
      @input="handleTextInput"
    />

    <textarea
      v-else-if="field.type === 'textarea'"
      :id="fieldId"
      :value="modelValue"
      class="FormControl AdminSettingField-textarea"
      :rows="field.rows || 4"
      :placeholder="field.placeholder || ''"
      :aria-label="field.label"
      @input="handleTextInput"
    ></textarea>

    <AdminSelectMenu
      v-else-if="field.type === 'select'"
      :input-id="fieldId"
      :model-value="modelValue"
      :options="field.options || []"
      :placeholder="field.placeholder || '请选择'"
      :aria-label="field.label"
      @update:modelValue="emit('update:modelValue', $event)"
    />

    <label v-else-if="field.type === 'boolean'" class="AdminSettingField-toggle">
      <input
        :id="fieldId"
        :checked="Boolean(modelValue)"
        type="checkbox"
        class="FormControl-checkbox"
        @change="emit('update:modelValue', $event.target.checked)"
      />
      <span>{{ field.help_text || '启用该设置项' }}</span>
    </label>

    <p v-if="field.help_text" class="Form-help">
      {{ field.help_text }}
    </p>
  </div>
</template>

<script setup>
import AdminSelectMenu from './AdminSelectMenu.vue'

const props = defineProps({
  field: {
    type: Object,
    required: true,
  },
  modelValue: {
    type: [String, Number, Boolean],
    default: '',
  },
})

const emit = defineEmits(['update:modelValue'])

const fieldId = `extension-setting-${String(props.field?.key || '').trim()}`

function handleTextInput(event) {
  if (props.field.type === 'number') {
    emit('update:modelValue', event.target.value === '' ? '' : Number(event.target.value))
    return
  }
  emit('update:modelValue', event.target.value)
}
</script>

<style scoped>
.AdminSettingField {
  display: grid;
  gap: 8px;
}

.AdminSettingField-label {
  font-weight: 600;
  color: var(--forum-text-color);
}

.AdminSettingField-required {
  margin-left: 4px;
  color: #b54747;
}

.AdminSettingField-textarea {
  resize: vertical;
}

.AdminSettingField-toggle {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
</style>
