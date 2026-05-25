<template>
  <section class="SampleHelloPage">
    <header class="SampleHelloPage-hero">
      <p class="SampleHelloPage-kicker">Sample Hello</p>
      <h2>示例扩展设置</h2>
      <p>这个页面用于验证扩展 manifest 声明的 `frontend_admin_entry` 已经可以承载真实后台组件。</p>
    </header>

    <div class="SampleHelloPage-grid">
      <article class="SampleHelloPage-card">
        <small>扩展 ID</small>
        <strong>{{ extension?.id || 'sample-hello' }}</strong>
      </article>
      <article class="SampleHelloPage-card">
        <small>当前入口</small>
        <strong>{{ hostKind === 'operations' ? '操作页' : '设置页' }}</strong>
      </article>
      <article class="SampleHelloPage-card">
        <small>后台入口文件</small>
        <code>{{ extension?.frontend_admin_entry || 'extensions/sample-hello/frontend/admin/index.js' }}</code>
      </article>
    </div>

    <article class="SampleHelloPage-panel">
      <h3>下一步开发建议</h3>
      <ul>
        <li>把设置表单、说明文档和状态摘要沉淀到扩展自身目录。</li>
        <li>后续可在这里继续接入真正的扩展配置 API。</li>
      </ul>
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
    default: 'settings',
  },
})
</script>

<style scoped>
.SampleHelloPage {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.SampleHelloPage-hero,
.SampleHelloPage-card,
.SampleHelloPage-panel {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.SampleHelloPage-hero,
.SampleHelloPage-panel {
  padding: 20px;
}

.SampleHelloPage-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.SampleHelloPage-hero h2,
.SampleHelloPage-panel h3 {
  margin: 0 0 10px;
}

.SampleHelloPage-hero p:last-child,
.SampleHelloPage-panel ul {
  margin: 0;
}

.SampleHelloPage-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.SampleHelloPage-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.SampleHelloPage-card small {
  color: var(--forum-text-soft);
}

.SampleHelloPage-card code {
  overflow-wrap: anywhere;
}
</style>
