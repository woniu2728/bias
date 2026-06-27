<template>
  <span
    class="forum-state-badge"
    :class="[`forum-state-badge--${tone}`, `forum-state-badge--${size}`]"
    :title="title || ''"
  >
    <i v-if="icon" :class="icon"></i>
    <span>{{ label }}</span>
  </span>
</template>

<script setup>
defineProps({
  label: {
    type: String,
    required: true,
  },
  tone: {
    type: String,
    default: 'muted',
  },
  size: {
    type: String,
    default: 'sm',
  },
  icon: {
    type: String,
    default: '',
  },
  title: {
    type: String,
    default: '',
  },
})
</script>

<style scoped>
.forum-state-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--forum-radius-pill);
  font-weight: 600;
  flex-shrink: 0;
}

.forum-state-badge--sm {
  padding: 2px 8px;
  font-size: 11px;
}

.forum-state-badge--md {
  padding: 4px 10px;
  font-size: var(--forum-font-size-sm);
}

.forum-state-badge--primary {
  background: var(--forum-primary-color);
  color: var(--forum-text-inverse);
}

.forum-state-badge--warning {
  background: #fff3cd;
  color: #856404;
}

.forum-state-badge--danger {
  background: #fdeeee;
  color: #b14545;
}

.forum-state-badge--soft-primary {
  background: #edf4fb;
  color: var(--forum-primary-color);
}

.forum-state-badge--info {
  background: var(--forum-info-bg);
  color: var(--forum-info-color);
}

.forum-state-badge--soft-warning {
  background: #fff1df;
  color: #9a5520;
}

.forum-state-badge--muted {
  background: var(--forum-bg-elevated-strong);
  color: var(--forum-text-soft);
}
</style>
