<template>
  <div v-if="alerts.length" class="RuntimeAlertHost" aria-live="polite">
    <article
      v-for="alert in alerts"
      :key="alert.key"
      class="RuntimeAlert"
      :class="`RuntimeAlert--${alert.tone}`"
    >
      <div class="RuntimeAlert-icon" aria-hidden="true">
        <i :class="iconForTone(alert.tone)"></i>
      </div>
      <div class="RuntimeAlert-body">
        <strong v-if="alert.title">{{ alert.title }}</strong>
        <p>{{ alert.message }}</p>
        <small v-if="alert.detail">{{ alert.detail }}</small>
      </div>
      <button type="button" aria-label="关闭提示" @click="dismiss(alert.key)">
        <i class="fas fa-times"></i>
      </button>
    </article>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import {
  normalizeRuntimeAlert,
  removeRuntimeAlert,
  upsertRuntimeAlert,
} from '../common/runtimeAlerts'

const alerts = ref([])
const timers = new Map()

function pushAlert(detail, source) {
  const alert = normalizeRuntimeAlert(detail, source)
  upsertRuntimeAlert(alerts.value, alert)
  if (alert.timeout) {
    window.clearTimeout(timers.get(alert.key))
    timers.set(alert.key, window.setTimeout(() => dismiss(alert.key), Number(alert.timeout)))
  }
}

function dismiss(key) {
  removeRuntimeAlert(alerts.value, key)
  window.clearTimeout(timers.get(key))
  timers.delete(key)
}

function handleExtensionRuntimeError(event) {
  pushAlert(event?.detail || {}, 'extension-runtime')
}

function handleApplicationAlert(event) {
  pushAlert(event?.detail || {}, 'application-alert')
}

function handleApplicationError(event) {
  pushAlert(event?.detail || {}, 'application-error')
}

function iconForTone(tone) {
  if (tone === 'success') return 'fas fa-check-circle'
  if (tone === 'warning') return 'fas fa-exclamation-triangle'
  if (tone === 'danger') return 'fas fa-exclamation-circle'
  return 'fas fa-info-circle'
}

onMounted(() => {
  window.addEventListener('bias:extension-runtime-error', handleExtensionRuntimeError)
  window.addEventListener('bias:application-alert', handleApplicationAlert)
  window.addEventListener('bias:application-error', handleApplicationError)
})

onBeforeUnmount(() => {
  window.removeEventListener('bias:extension-runtime-error', handleExtensionRuntimeError)
  window.removeEventListener('bias:application-alert', handleApplicationAlert)
  window.removeEventListener('bias:application-error', handleApplicationError)
  for (const timer of timers.values()) {
    window.clearTimeout(timer)
  }
  timers.clear()
})
</script>

<style scoped>
.RuntimeAlertHost {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 1100;
  width: min(420px, calc(100vw - 28px));
  display: grid;
  gap: 10px;
}

.RuntimeAlert {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) 32px;
  align-items: start;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  background: var(--forum-bg-surface);
  box-shadow: var(--forum-shadow-md);
}

.RuntimeAlert--warning {
  border-color: var(--forum-warning-border);
  background: var(--forum-warning-bg);
}

.RuntimeAlert--danger {
  border-color: #f0c3c3;
  background: #fff4f4;
}

.RuntimeAlert--success {
  border-color: #c9ead8;
  background: #edf8f2;
}

.RuntimeAlert-icon {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--forum-primary-color);
}

.RuntimeAlert--warning .RuntimeAlert-icon {
  color: var(--forum-warning-color);
}

.RuntimeAlert--danger .RuntimeAlert-icon {
  color: var(--forum-danger-color);
}

.RuntimeAlert--success .RuntimeAlert-icon {
  color: var(--forum-success-color);
}

.RuntimeAlert-body {
  min-width: 0;
}

.RuntimeAlert strong {
  display: block;
  margin-bottom: 3px;
  font-size: var(--forum-font-size-sm);
  color: var(--forum-text-color);
}

.RuntimeAlert p,
.RuntimeAlert small {
  display: block;
  min-width: 0;
  overflow-wrap: anywhere;
}

.RuntimeAlert p {
  margin: 0;
  font-size: var(--forum-font-size-sm);
  line-height: 1.45;
  color: var(--forum-text-color);
}

.RuntimeAlert small {
  margin-top: 4px;
  color: var(--forum-text-muted);
  font-size: var(--forum-font-size-xs);
}

.RuntimeAlert button {
  width: 32px;
  height: 32px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  background: transparent;
  color: var(--forum-text-muted);
}

.RuntimeAlert button:hover {
  border-color: var(--forum-border-color);
  background: rgba(255, 255, 255, 0.7);
}

@media (max-width: 768px) {
  .RuntimeAlertHost {
    right: 14px;
    bottom: 14px;
  }
}
</style>
