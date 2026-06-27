<template>
  <div class="AdminStateBlock" :class="`AdminStateBlock--${tone}`">
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
.AdminStateBlock {
  padding: 28px 18px;
  border-radius: 16px;
  border: 1px solid var(--forum-border-color);
  background: var(--forum-bg-elevated);
  text-align: center;
  color: var(--forum-text-soft);
}

.AdminStateBlock--neutral {
  background: var(--forum-bg-elevated);
}

.AdminStateBlock--subtle {
  background: var(--forum-bg-subtle);
  color: var(--forum-text-muted);
}

.AdminStateBlock--danger {
  background: #fdf0f0;
  border-color: rgba(176, 58, 55, 0.14);
  color: #b03a37;
}
</style>
