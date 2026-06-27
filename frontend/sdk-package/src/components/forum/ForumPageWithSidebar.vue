<template>
  <div class="forum-page-shell">
    <aside class="forum-page-shell__sidebar">
      <slot name="sidebar"></slot>
    </aside>
    <div class="forum-page-shell__content">
      <slot></slot>
    </div>
  </div>
</template>

<style scoped>
.forum-page-shell {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 240px 1fr;
}

.forum-page-shell__sidebar {
  padding: 20px 15px;
  background: var(--forum-bg-elevated);
  border-right: 1px solid var(--forum-border-color);
  min-height: calc(100vh - 56px);
}

.forum-page-shell__content {
  min-width: 0;
}

@media (max-width: 900px) {
  .forum-page-shell {
    grid-template-columns: 1fr;
  }

  .forum-page-shell__sidebar {
    min-height: auto;
    border-right: none;
    border-bottom: 1px solid #e3e8ed;
  }
}
</style>
