<template>
  <section class="forum-hero-panel" :class="variantClass">
    <div v-if="pill" class="forum-hero-pill">{{ pill }}</div>
    <h1>{{ title }}</h1>
    <p v-if="description">{{ description }}</p>
    <div v-if="$slots.meta" class="forum-hero-meta">
      <slot name="meta"></slot>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  description: {
    type: String,
    default: ''
  },
  pill: {
    type: String,
    default: ''
  },
  title: {
    type: String,
    required: true
  },
  variant: {
    type: String,
    default: 'default'
  }
})

const variantClass = computed(() => `forum-hero-panel--${props.variant}`)
</script>

<style scoped>
.forum-hero-panel {
  margin-bottom: 24px;
  padding: 28px 32px;
  border-radius: var(--forum-radius-lg);
  border: 1px solid var(--forum-border-color);
  box-shadow: var(--forum-shadow-sm);
}

.forum-hero-panel--default {
  background: linear-gradient(135deg, #f9fbfc 0%, #e8eef4 100%);
}

.forum-hero-panel--primary {
  background: linear-gradient(135deg, color-mix(in srgb, var(--forum-primary-color) 14%, white) 0%, #eef4f8 100%);
}

.forum-hero-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 12px;
}

.forum-hero-panel h1 {
  font-size: var(--forum-font-size-3xl);
  font-weight: 300;
  margin-bottom: 8px;
  color: var(--forum-text-color);
}

.forum-hero-panel p {
  color: var(--forum-text-muted);
  max-width: 720px;
}

.forum-hero-meta {
  margin-top: 18px;
}
</style>
