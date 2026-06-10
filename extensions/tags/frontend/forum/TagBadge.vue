<template>
  <router-link
    :to="resolvedTo"
    class="forum-tag-badge"
    :class="[`forum-tag-badge--${variant}`, `forum-tag-badge--${size}`]"
    :style="badgeStyle"
  >
    <span v-if="showDot" class="forum-tag-badge__dot"></span>
    <span class="forum-tag-badge__label">{{ tag.name }}</span>
  </router-link>
</template>

<script setup>

import { computed } from '@bias/core'
import { buildTagPath } from './tagUtils.js'

const props = defineProps({
  tag: {
    type: Object,
    required: true,
  },
  to: {
    type: [String, Object],
    default: null,
  },
  variant: {
    type: String,
    default: 'solid',
  },
  size: {
    type: String,
    default: 'md',
  },
  showDot: {
    type: Boolean,
    default: false,
  },
  maxWidth: {
    type: String,
    default: '',
  },
})

const resolvedTo = computed(() => props.to || buildTagPath(props.tag))
const resolvedColor = computed(() => String(props.tag?.color || '#4d698e'))

const badgeStyle = computed(() => {
  const style = {
    '--forum-tag-color': resolvedColor.value,
  }

  if (props.maxWidth) {
    style.maxWidth = props.maxWidth
  }

  return style
})
</script>

<style scoped>
.forum-tag-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  border-radius: 999px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.forum-tag-badge:hover {
  text-decoration: none;
}

.forum-tag-badge__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.forum-tag-badge__dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.85;
}

.forum-tag-badge--solid {
  color: var(--forum-text-inverse);
  background: var(--forum-tag-color);
}

.forum-tag-badge--solid:hover {
  filter: brightness(0.96);
}

.forum-tag-badge--soft {
  color: #314150;
  border: 1px solid color-mix(in srgb, var(--forum-tag-color) 25%, white);
  background: color-mix(in srgb, var(--forum-tag-color) 10%, white);
}

.forum-tag-badge--soft:hover {
  background: color-mix(in srgb, var(--forum-tag-color) 18%, white);
}

.forum-tag-badge--sm {
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 500;
}

.forum-tag-badge--md {
  padding: 4px 10px;
  font-size: var(--forum-font-size-sm);
}
</style>
