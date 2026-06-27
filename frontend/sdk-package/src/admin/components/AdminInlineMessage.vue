<template>
  <div class="AdminInlineMessage" :class="`AdminInlineMessage--${tone}`">
    <slot></slot>
  </div>
</template>

<script setup>
defineProps({
  tone: {
    type: String,
    default: 'neutral'
  }
})
</script>

<style scoped>
.AdminInlineMessage {
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid transparent;
  line-height: 1.6;
}

.AdminInlineMessage--neutral {
  background: var(--forum-bg-subtle);
  border-color: var(--forum-border-color);
  color: var(--forum-text-muted);
}

.AdminInlineMessage--success {
  background: #edf8f1;
  border-color: rgba(31, 122, 69, 0.16);
  color: #1f7a45;
}

.AdminInlineMessage--danger {
  background: #fdf0f0;
  border-color: rgba(176, 58, 55, 0.14);
  color: #b03a37;
}

.AdminInlineMessage--warning {
  background: #fff7e5;
  border-color: rgba(181, 128, 28, 0.16);
  color: #9a6a12;
}
</style>
