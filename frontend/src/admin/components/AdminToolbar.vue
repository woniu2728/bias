<template>
  <div class="AdminToolbar" :class="toolbarClass">
    <slot></slot>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  align: {
    type: String,
    default: 'start',
    validator: value => ['start', 'end', 'between'].includes(value)
  },
  mobileFullWidth: {
    type: Boolean,
    default: true
  }
})

const toolbarClass = computed(() => ({
  [`AdminToolbar--${props.align}`]: true,
  'AdminToolbar--mobileFullWidth': props.mobileFullWidth
}))
</script>

<style scoped>
.AdminToolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.AdminToolbar--start {
  justify-content: flex-start;
}

.AdminToolbar--end {
  justify-content: flex-end;
}

.AdminToolbar--between {
  justify-content: space-between;
}

@media (max-width: 768px) {
  .AdminToolbar--mobileFullWidth {
    align-items: stretch;
    flex-direction: column;
  }

  .AdminToolbar--mobileFullWidth :slotted(.Button),
  .AdminToolbar--mobileFullWidth :slotted(.FormControl) {
    width: 100%;
    justify-content: center;
  }
}
</style>
