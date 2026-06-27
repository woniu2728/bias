<template>
  <div class="inline-message" :class="`inline-message--${tone}`">
    <slot></slot>
  </div>
</template>

<script setup>
defineProps({
  tone: {
    type: String,
    default: 'info'
  }
})
</script>

<style scoped>
.inline-message {
  padding: 12px 14px;
  border-radius: 10px;
  margin-bottom: 16px;
  font-size: 14px;
  line-height: 1.6;
  border: 1px solid transparent;
}

.inline-message--info {
  background: var(--forum-bg-subtle);
  border-color: var(--forum-border-color);
  color: var(--forum-text-muted);
}

.inline-message--success {
  background: #edf8f1;
  border-color: rgba(31, 122, 69, 0.16);
  color: #1f7a45;
}

.inline-message--danger {
  background: #fdf0f0;
  border-color: rgba(176, 58, 55, 0.14);
  color: #b03a37;
}

.inline-message--warning {
  background: #fff7e5;
  border-color: rgba(181, 128, 28, 0.16);
  color: #9a6a12;
}
</style>
