<template>
  <div class="AdminColorField">
    <input
      :id="inputId"
      :value="modelValue"
      :name="name"
      type="text"
      class="FormControl"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="emit('update:modelValue', $event.target.value)"
    />
    <input
      :id="pickerId"
      :value="modelValue"
      :name="pickerName"
      type="color"
      class="AdminColorField-picker"
      :aria-label="ariaLabel"
      :disabled="disabled"
      @input="emit('update:modelValue', $event.target.value)"
    />
  </div>
</template>

<script setup>
defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  inputId: {
    type: String,
    default: '',
  },
  pickerId: {
    type: String,
    default: '',
  },
  name: {
    type: String,
    default: '',
  },
  pickerName: {
    type: String,
    default: '',
  },
  placeholder: {
    type: String,
    default: '',
  },
  ariaLabel: {
    type: String,
    default: '',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue'])
</script>

<style scoped>
.AdminColorField {
  position: relative;
  min-width: 0;
}

.AdminColorField .FormControl {
  width: 100%;
  min-width: 0;
  padding-right: 48px;
}

.AdminColorField-picker {
  position: absolute;
  right: 8px;
  top: 50%;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: 7px;
  cursor: pointer;
  background: transparent;
  box-shadow: none;
  overflow: hidden;
  transform: translateY(-50%);
}

.AdminColorField-picker::-webkit-color-swatch-wrapper {
  padding: 0;
}

.AdminColorField-picker::-webkit-color-swatch {
  border: none;
  border-radius: 7px;
}

.AdminColorField-picker::-moz-color-swatch {
  border: none;
  border-radius: 7px;
}
</style>
