<template>
  <div
    ref="container"
    class="SecurityTurnstileChallenge"
    :class="{ 'SecurityTurnstileChallenge--loading': loading }"
  ></div>
</template>

<script setup>
import {
  getUiCopy,
} from '@bias/forum'
import {
  nextTick,
  onBeforeUnmount,
  ref,
  watch,
} from '@bias/core'
import { ensureTurnstileScript } from './turnstile.js'

const props = defineProps({
  settings: {
    type: Object,
    default: () => ({})
  },
  mode: {
    type: String,
    default: 'login'
  }
})

const emit = defineEmits(['update:token', 'update:payload', 'error'])

const container = ref(null)
const loading = ref(false)
let widgetId = null
let renderNonce = 0

watch(
  () => [props.mode, props.settings.auth_turnstile_site_key],
  () => renderWidget(),
  { immediate: true }
)

onBeforeUnmount(() => {
  removeWidget()
})

function reset() {
  emit('update:token', '')
  emit('update:payload', null)
  if (typeof window === 'undefined' || !window.turnstile || widgetId === null) {
    renderWidget()
    return
  }
  try {
    window.turnstile.reset(widgetId)
  } catch (error) {
    emit('error', error)
  }
}

async function renderWidget() {
  const siteKey = String(props.settings.auth_turnstile_site_key || '').trim()
  const currentNonce = renderNonce + 1
  renderNonce = currentNonce
  removeWidget(false)
  emit('update:token', '')
  emit('update:payload', null)

  if (!siteKey) {
    return
  }

  await nextTick()
  if (!container.value) {
    return
  }

  loading.value = true
  try {
    const turnstile = await ensureTurnstileScript()
    if (!turnstile || currentNonce !== renderNonce || !container.value) {
      return
    }

    widgetId = turnstile.render(container.value, {
      sitekey: siteKey,
      callback(token) {
        emit('update:token', token || '')
      },
      'expired-callback'() {
        emit('update:token', '')
        emit('error', getUiCopy({
          surface: 'auth-turnstile-expired-error',
        })?.text || '真人验证已过期，请重新完成验证。')
      },
      'error-callback'() {
        emit('update:token', '')
        emit('error', getUiCopy({
          surface: 'auth-turnstile-load-error',
        })?.text || '真人验证加载失败，请稍后重试。')
      }
    })
  } catch (error) {
    emit('error', error.message || getUiCopy({
      surface: 'auth-turnstile-load-error',
    })?.text || '真人验证加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

function removeWidget(invalidatePendingRender = true) {
  if (invalidatePendingRender) {
    renderNonce += 1
  }
  if (typeof window === 'undefined' || !window.turnstile || widgetId === null) {
    widgetId = null
    return
  }
  try {
    window.turnstile.remove(widgetId)
  } catch (error) {
    emit('error', error)
  } finally {
    widgetId = null
  }
}

defineExpose({
  reset,
})
</script>

<style scoped>
.SecurityTurnstileChallenge {
  min-height: 68px;
  padding: 8px;
  border: 1px solid #d7e0e8;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.92);
}

.SecurityTurnstileChallenge--loading {
  opacity: 0.75;
}
</style>
