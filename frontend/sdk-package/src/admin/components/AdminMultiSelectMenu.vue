<template>
  <div ref="rootRef" class="AdminMultiSelectMenu" :class="{ 'is-open': isOpen, 'is-disabled': disabled }">
    <button
      :id="inputId"
      type="button"
      class="FormControl AdminMultiSelectMenu-trigger"
      :aria-expanded="isOpen"
      :aria-label="ariaLabel"
      :disabled="disabled"
      @click="toggleMenu"
    >
      <span class="AdminMultiSelectMenu-summary" :class="{ 'is-placeholder': !selectedCount }">
        {{ summary || placeholder }}
      </span>
      <i class="fas fa-chevron-down AdminMultiSelectMenu-arrow"></i>
    </button>

    <div v-if="isOpen" class="AdminMultiSelectMenu-menu">
      <button
        v-for="option in normalizedOptions"
        :key="option.key"
        type="button"
        class="AdminMultiSelectMenu-option"
        :class="{ 'is-active': isSelected(option.value) }"
        @click="toggleOption(option.value)"
      >
        <span class="AdminMultiSelectMenu-optionMain">
          <span class="AdminMultiSelectMenu-checkbox" :class="{ 'is-checked': isSelected(option.value) }">
            <i v-if="isSelected(option.value)" class="fas fa-check"></i>
          </span>
          <span
            v-if="option.color || option.icon || option.fallbackLabel"
            class="AdminMultiSelectMenu-badge"
            :style="{ backgroundColor: option.color || '#4d698e' }"
            :title="option.label"
          >
            <i v-if="option.icon" :class="option.icon"></i>
            <span v-else>{{ option.fallbackLabel }}</span>
          </span>
          <span class="AdminMultiSelectMenu-name">{{ option.label }}</span>
        </span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  options: {
    type: Array,
    default: () => [],
  },
  placeholder: {
    type: String,
    default: '',
  },
  summary: {
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

const selectedCount = computed(() => props.modelValue.length)

function isSelected(value) {
  return props.modelValue.some(item => Object.is(item, value))
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

function toggleOption(value) {
  const nextValue = isSelected(value)
    ? props.modelValue.filter(item => !Object.is(item, value))
    : [...props.modelValue, value]
  emit('update:modelValue', nextValue)
  emit('change', nextValue)
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
.AdminMultiSelectMenu {
  position: relative;
  width: 100%;
}

.AdminMultiSelectMenu-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-height: 48px;
  cursor: pointer;
}

.AdminMultiSelectMenu-summary {
  min-width: 0;
  color: var(--forum-text-color);
  font-size: 14px;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.AdminMultiSelectMenu-summary.is-placeholder {
  color: var(--forum-text-soft);
}

.AdminMultiSelectMenu-arrow {
  color: var(--forum-text-soft);
  font-size: 12px;
  transition: transform 0.18s ease;
}

.AdminMultiSelectMenu.is-open .AdminMultiSelectMenu-arrow {
  transform: rotate(180deg);
}

.AdminMultiSelectMenu-menu {
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

.AdminMultiSelectMenu-option {
  width: 100%;
  border: none;
  background: transparent;
  display: block;
  cursor: pointer;
}

.AdminMultiSelectMenu-optionMain {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 44px;
  padding: 0 14px;
}

.AdminMultiSelectMenu-option:hover {
  background: color-mix(in srgb, var(--forum-primary-color) 4%, transparent);
}

.AdminMultiSelectMenu-checkbox {
  width: 16px;
  height: 16px;
  border: 1px solid var(--forum-border-strong);
  border-radius: 4px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: #fff;
}

.AdminMultiSelectMenu-checkbox.is-checked {
  border-color: var(--forum-primary-color);
  background: var(--forum-primary-color);
}

.AdminMultiSelectMenu-checkbox i {
  font-size: 10px;
}

.AdminMultiSelectMenu-badge {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 13px;
  flex: 0 0 auto;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.16);
}

.AdminMultiSelectMenu-name {
  color: var(--forum-text-color);
  font-size: 14px;
  font-weight: 500;
}

.AdminMultiSelectMenu.is-disabled .AdminMultiSelectMenu-trigger {
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .AdminMultiSelectMenu-menu {
    position: static;
    margin-top: 8px;
  }
}
</style>
