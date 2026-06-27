<template>
  <div class="state-block">
    <slot></slot>
  </div>
</template>

<style scoped>
.state-block {
  padding: 60px 24px;
  background: var(--forum-bg-elevated);
  border-radius: var(--forum-radius-md);
  border: 1px solid var(--forum-border-color);
  text-align: center;
  color: var(--forum-text-soft);
}
</style>
