<template>
  <div ref="rootRef" class="AdminSelectMenu" :class="{ 'is-open': isOpen, 'is-disabled': disabled }">
    <button
      :id="inputId"
      type="button"
      class="FormControl AdminSelectMenu-trigger"
      :aria-expanded="isOpen"
      :aria-label="ariaLabel"
      :disabled="disabled"
      @click="toggleMenu"
    >
      <span class="AdminSelectMenu-summary" :class="{ 'is-placeholder': !selectedOption }">
        {{ selectedLabel }}
      </span>
      <i class="fas fa-chevron-down AdminSelectMenu-arrow"></i>
    </button>

    <div v-if="isOpen" class="AdminSelectMenu-menu" role="listbox">
      <button
        v-for="option in normalizedOptions"
        :key="option.key"
        type="button"
        class="AdminSelectMenu-option"
        :class="{ 'is-active': isSelected(option.value) }"
        :aria-selected="isSelected(option.value)"
        @click="selectOption(option.value)"
      >
        <span class="AdminSelectMenu-name">{{ option.label }}</span>
        <i v-if="isSelected(option.value)" class="fas fa-check AdminSelectMenu-check"></i>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  modelValue: {
    type: [String, Number, Boolean, null],
    default: '',
  },
  options: {
    type: Array,
    default: () => [],
  },
  placeholder: {
    type: String,
    default: '',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  ariaLabel: {
    type: String,
    default: '',
  },
  inputId: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:modelValue', 'change'])

const isOpen = ref(false)
const rootRef = ref(null)

const normalizedOptions = computed(() => (
  Array.isArray(props.options)
    ? props.options.map((option, index) => ({
      ...option,
      key: `${index}-${String(option?.value ?? '')}`,
    }))
    : []
))

const selectedOption = computed(() => (
  normalizedOptions.value.find(option => Object.is(option.value, props.modelValue))
))

const selectedLabel = computed(() => (
  selectedOption.value?.label || props.placeholder || ''
))

function isSelected(value) {
  return Object.is(value, props.modelValue)
}

function toggleMenu() {
  if (props.disabled) {
    return
  }
  isOpen.value = !isOpen.value
}

function closeMenu() {
  isOpen.value = false
}

function selectOption(value) {
  emit('update:modelValue', value)
  emit('change', value)
  closeMenu()
}

function handleDocumentClick(event) {
  if (!rootRef.value?.contains(event.target)) {
    closeMenu()
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<style scoped>
.AdminSelectMenu {
  position: relative;
  width: 100%;
}

.AdminSelectMenu-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-height: 48px;
  cursor: pointer;
}

.AdminSelectMenu-summary {
  min-width: 0;
  color: var(--forum-text-color);
  font-size: 14px;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.AdminSelectMenu-summary.is-placeholder {
  color: var(--forum-text-soft);
}

.AdminSelectMenu-arrow {
  color: var(--forum-text-soft);
  font-size: 12px;
  transition: transform 0.18s ease;
}

.AdminSelectMenu.is-open .AdminSelectMenu-arrow {
  transform: rotate(180deg);
}

.AdminSelectMenu-menu {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  z-index: 20;
  padding: 10px 0;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-elevated);
  box-shadow: 0 18px 38px rgba(15, 23, 42, 0.12);
}

.AdminSelectMenu-option {
  width: 100%;
  border: none;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 44px;
  padding: 0 14px;
  cursor: pointer;
}

.AdminSelectMenu-option:hover {
  background: color-mix(in srgb, var(--forum-primary-color) 4%, transparent);
}

.AdminSelectMenu-option.is-active .AdminSelectMenu-name {
  color: var(--forum-primary-color);
  font-weight: 600;
}

.AdminSelectMenu-name {
  color: var(--forum-text-color);
  font-size: 14px;
  text-align: left;
}

.AdminSelectMenu-check {
  color: var(--forum-primary-color);
  font-size: 12px;
}

.AdminSelectMenu.is-disabled .AdminSelectMenu-trigger {
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .AdminSelectMenu-menu {
    position: static;
    margin-top: 8px;
  }
}
</style>
