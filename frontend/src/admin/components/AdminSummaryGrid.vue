<template>
  <div class="AdminSummaryGrid">
    <article v-for="item in items" :key="item.label" class="AdminSummaryGrid-card">
      <small>{{ item.label }}</small>
      <strong>{{ item.value }}</strong>
    </article>
  </div>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
.AdminSummaryGrid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.AdminSummaryGrid-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding: 16px 18px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-sm);
  background: linear-gradient(180deg, var(--forum-bg-elevated), #f6f9fc);
  box-shadow: var(--forum-shadow-sm);
}

.AdminSummaryGrid-card small {
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-xs);
  font-weight: 600;
}

.AdminSummaryGrid-card strong {
  min-width: 0;
  color: var(--forum-text-muted);
  font-size: 16px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

@media (max-width: 768px) {
  .AdminSummaryGrid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 560px) {
  .AdminSummaryGrid {
    grid-template-columns: 1fr;
  }
}
</style>
