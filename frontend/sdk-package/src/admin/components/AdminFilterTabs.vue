<template>
  <div class="AdminFilterTabs" role="tablist">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      class="AdminFilterTabs-button"
      :class="{ 'is-active': modelValue === option.value }"
      role="tab"
      :aria-selected="modelValue === option.value"
      @click="selectOption(option.value)"
    >
      <i v-if="option.icon" :class="option.icon"></i>
      <span>{{ option.label }}</span>
    </button>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: {
    type: String,
    required: true
  },
  options: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

function selectOption(value) {
  if (props.modelValue === value) return
  emit('update:modelValue', value)
  emit('change', value)
}
</script>

<style scoped>
.AdminFilterTabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}

.AdminFilterTabs-button {
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
  background: var(--forum-bg-elevated);
  padding: 0 14px;
  color: var(--forum-text-muted);
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s, color 0.2s;
}

.AdminFilterTabs-button:hover {
  border-color: var(--forum-primary-color);
  color: var(--forum-primary-color);
}

.AdminFilterTabs-button.is-active {
  background: var(--forum-primary-color);
  border-color: var(--forum-primary-color);
  color: var(--forum-text-inverse);
}

@media (max-width: 768px) {
  .AdminFilterTabs {
    overflow-x: auto;
    padding-bottom: 4px;
    scrollbar-width: none;
  }

  .AdminFilterTabs::-webkit-scrollbar {
    display: none;
  }

  .AdminFilterTabs-button {
    flex: 0 0 auto;
    border-radius: var(--forum-radius-pill);
    white-space: nowrap;
  }
}
</style>
