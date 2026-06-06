<template>
  <component
    :is="active.component"
    v-if="active?.component"
    :items="active.items"
    :active-index="active.activeIndex"
    :loading="active.loading"
    :style-object="active.styleObject"
    :provider="active.provider"
    :state="active.state"
    @highlight="$emit('highlight', $event)"
    @select="$emit('select', $event)"
  />
</template>

<script setup>
defineProps({
  active: {
    type: Object,
    default: null
  }
})

defineEmits(['highlight', 'select'])
</script>
