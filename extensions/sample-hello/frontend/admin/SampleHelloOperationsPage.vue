<template>
  <section class="SampleHelloOps">
    <article class="SampleHelloOps-panel">
      <p class="SampleHelloOps-kicker">Sample Hello</p>
      <h2>示例扩展操作页</h2>
      <p>这里演示扩展可以为“操作入口”声明独立组件，而不是继续复用公共设置页。</p>

      <dl class="SampleHelloOps-meta">
        <div>
          <dt>扩展</dt>
          <dd>{{ extension?.name || 'Sample Hello' }}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd>{{ extension?.enabled ? '已启用' : '未启用' }}</dd>
        </div>
        <div>
          <dt>宿主入口</dt>
          <dd>{{ hostKind }}</dd>
        </div>
      </dl>
    </article>
  </section>
</template>

<script setup>
defineProps({
  extension: {
    type: Object,
    default: null,
  },
  hostKind: {
    type: String,
    default: 'operations',
  },
})
</script>

<style scoped>
.SampleHelloOps-panel {
  padding: 20px;
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.SampleHelloOps-kicker {
  margin: 0 0 10px;
  color: #8c4b00;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.SampleHelloOps-panel h2 {
  margin: 0 0 10px;
}

.SampleHelloOps-panel p {
  margin: 0 0 16px;
}

.SampleHelloOps-meta {
  display: grid;
  gap: 12px;
  margin: 0;
}

.SampleHelloOps-meta div {
  display: grid;
  gap: 4px;
}

.SampleHelloOps-meta dt {
  color: var(--forum-text-soft);
}

.SampleHelloOps-meta dd {
  margin: 0;
}
</style>
