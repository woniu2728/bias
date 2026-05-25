<template>
  <section class="SampleHelloDetail">
    <article class="SampleHelloDetail-panel">
      <div class="SampleHelloDetail-head">
        <div>
          <p class="SampleHelloDetail-kicker">Sample Hello</p>
          <h3>扩展自定义详情卡片</h3>
        </div>
        <span class="SampleHelloDetail-status" :class="extension?.enabled ? 'is-enabled' : 'is-disabled'">
          {{ extension?.enabled ? '运行中' : '已停用' }}
        </span>
      </div>

      <p class="SampleHelloDetail-copy">
        这个区域用于验证扩展可以把自己的说明、诊断摘要和下一步操作直接挂进详情页，而不是全部依赖平台通用字段。
      </p>

      <div class="SampleHelloDetail-grid">
        <article class="SampleHelloDetail-card">
          <small>后台入口</small>
          <code>{{ extension?.frontend_admin_entry || 'extensions/sample-hello/frontend/admin/index.js' }}</code>
        </article>
        <article class="SampleHelloDetail-card">
          <small>动作数量</small>
          <strong>{{ Array.isArray(extension?.admin_actions) ? extension.admin_actions.length : 0 }}</strong>
        </article>
        <article class="SampleHelloDetail-card">
          <small>声明能力</small>
          <strong>{{ Array.isArray(extension?.provides) && extension.provides.length ? extension.provides.join('、') : '无' }}</strong>
        </article>
      </div>
    </article>
  </section>
</template>

<script setup>
defineProps({
  extension: {
    type: Object,
    default: null,
  },
  surface: {
    type: String,
    default: 'detail',
  },
})
</script>

<style scoped>
.SampleHelloDetail-panel {
  padding: 20px;
  border: 1px solid var(--forum-border-color);
  border-radius: 18px;
  background:
    radial-gradient(circle at top right, rgba(50, 91, 133, 0.08), transparent 30%),
    var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.SampleHelloDetail-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.SampleHelloDetail-kicker {
  margin: 0 0 8px;
  color: #325b85;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.SampleHelloDetail-head h3 {
  margin: 0;
}

.SampleHelloDetail-status {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.SampleHelloDetail-status.is-enabled {
  background: #edf8f2;
  color: #25704d;
}

.SampleHelloDetail-status.is-disabled {
  background: #f5f7fa;
  color: #6c7988;
}

.SampleHelloDetail-copy {
  margin: 14px 0 0;
  color: var(--forum-text-muted);
  line-height: 1.6;
}

.SampleHelloDetail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.SampleHelloDetail-card {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}

.SampleHelloDetail-card small {
  color: var(--forum-text-soft);
}

.SampleHelloDetail-card code {
  overflow-wrap: anywhere;
}
</style>
