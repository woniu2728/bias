<template>
  <section class="ExtensionGeneratedSurface">
    <header class="ExtensionGeneratedSurface-hero">
      <p class="ExtensionGeneratedSurface-kicker">Extension Operations</p>
      <h2>{{ extension?.name || '扩展操作' }}</h2>
      <p>{{ heroDescription }}</p>
    </header>

    <div class="ExtensionGeneratedSurface-grid">
      <article class="ExtensionGeneratedSurface-card">
        <small>后台动作</small>
        <strong>{{ adminActions.length }}</strong>
      </article>
      <article class="ExtensionGeneratedSurface-card">
        <small>运行操作</small>
        <strong>{{ runtimeActions.length }}</strong>
      </article>
      <article class="ExtensionGeneratedSurface-card">
        <small>当前状态</small>
        <strong>{{ extension?.runtime_status?.label || '未知' }}</strong>
      </article>
    </div>

    <section v-if="adminActions.length" class="ExtensionGeneratedSurface-panel">
      <h3>后台动作</h3>
      <div class="ExtensionGeneratedSurface-actions">
        <template v-for="action in adminActions" :key="`admin-${action.key}`">
          <router-link
            v-if="action.kind === 'route'"
            :to="action.target"
            class="ExtensionGeneratedAction"
            :class="resolveActionToneClass(action)"
          >
            <i v-if="action.icon" :class="action.icon"></i>
            <span>{{ action.label }}</span>
          </router-link>
          <a
            v-else
            :href="action.target"
            class="ExtensionGeneratedAction"
            :class="resolveActionToneClass(action)"
            :target="action.opens_in_new_tab ? '_blank' : null"
            :rel="action.opens_in_new_tab ? 'noreferrer noopener' : null"
          >
            <i v-if="action.icon" :class="action.icon"></i>
            <span>{{ action.label }}</span>
          </a>
        </template>
      </div>
    </section>

    <section v-if="runtimeActions.length" class="ExtensionGeneratedSurface-panel">
      <h3>运行操作</h3>
      <div class="ExtensionGeneratedSurface-actions">
        <button
          v-for="action in runtimeActions"
          :key="`runtime-${action.key}`"
          type="button"
          class="ExtensionGeneratedAction"
          :class="resolveActionToneClass(action)"
          :disabled="actionLoading"
          @click="runRuntimeAction(action)"
        >
          {{ actionLoading ? '处理中...' : action.label }}
        </button>
      </div>
      <AdminInlineMessage v-if="errorMessage" tone="danger">{{ errorMessage }}</AdminInlineMessage>
    </section>

    <AdminStateBlock v-if="!adminActions.length && !runtimeActions.length" tone="subtle">
      当前扩展未声明可执行后台动作。
    </AdminStateBlock>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import api from '../../api'
import { useModalStore } from '../../stores/modal'
import AdminInlineMessage from '../components/AdminInlineMessage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'

const props = defineProps({
  extension: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['extension-updated'])

const modalStore = useModalStore()
const actionLoading = ref(false)
const errorMessage = ref('')

const adminActions = computed(() => (
  Array.isArray(props.extension?.admin_actions) ? props.extension.admin_actions : []
))

const runtimeActions = computed(() => (
  Array.isArray(props.extension?.runtime_actions) ? props.extension.runtime_actions : []
))

const heroDescription = computed(() => {
  const name = props.extension?.name || '当前扩展'
  return `${name} 未提供自定义操作页组件，当前页面会直接复用统一动作协议承接后台动作与运行操作。`
})

async function runRuntimeAction(action) {
  if (!props.extension?.id || !action?.action) {
    return
  }

  if (action.confirm_message) {
    const confirmed = await modalStore.confirm({
      title: action.confirm_title || action.label,
      message: action.confirm_message,
      confirmText: action.confirm_text || action.label,
      cancelText: '取消',
      tone: action.tone === 'danger' ? 'danger' : 'primary',
    })
    if (!confirmed) {
      return
    }
  }

  actionLoading.value = true
  errorMessage.value = ''

  try {
    const data = action.action.startsWith('hook:')
      ? await api.post(`/admin/extensions/${props.extension.id}/runtime-hooks/${action.action.slice(5)}`)
      : await api.post(`/admin/extensions/${props.extension.id}/${action.action}`)
    emit('extension-updated', data)
    if (action.success_message) {
      await modalStore.alert({
        title: action.label,
        message: action.success_message,
        tone: 'success',
      })
    }
  } catch (error) {
    console.error('执行扩展运行操作失败:', error)
    errorMessage.value = error.response?.data?.error || '执行扩展运行操作失败，请稍后重试'
  } finally {
    actionLoading.value = false
  }
}

function resolveActionToneClass(action) {
  if (action?.tone === 'primary') {
    return 'ExtensionGeneratedAction--primary'
  }
  if (action?.tone === 'danger') {
    return 'ExtensionGeneratedAction--danger'
  }
  if (action?.tone === 'subtle') {
    return 'ExtensionGeneratedAction--subtle'
  }
  return ''
}
</script>

<style scoped>
.ExtensionGeneratedSurface {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.ExtensionGeneratedSurface-hero,
.ExtensionGeneratedSurface-card,
.ExtensionGeneratedSurface-panel {
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.ExtensionGeneratedSurface-hero,
.ExtensionGeneratedSurface-panel {
  padding: 20px;
}

.ExtensionGeneratedSurface-hero {
  border-color: rgba(77, 105, 142, 0.22);
  background: linear-gradient(135deg, rgba(77, 105, 142, 0.14), rgba(77, 105, 142, 0.04));
}

.ExtensionGeneratedSurface-kicker {
  margin: 0 0 10px;
  color: var(--forum-primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.ExtensionGeneratedSurface-hero h2,
.ExtensionGeneratedSurface-panel h3 {
  margin: 0 0 10px;
}

.ExtensionGeneratedSurface-hero p:last-child {
  margin: 0;
}

.ExtensionGeneratedSurface-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.ExtensionGeneratedSurface-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.ExtensionGeneratedSurface-card small {
  color: var(--forum-text-soft);
}

.ExtensionGeneratedSurface-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.ExtensionGeneratedAction {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid var(--forum-border-color);
  border-radius: 999px;
  background: var(--forum-bg-subtle);
  color: var(--forum-text-color);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

.ExtensionGeneratedAction--primary {
  background: #edf4fb;
  border-color: #d6e4f3;
  color: #325b85;
}

.ExtensionGeneratedAction--subtle {
  background: transparent;
}

.ExtensionGeneratedAction--danger {
  background: #fff4f4;
  border-color: #f0d0d0;
  color: #b54747;
}
</style>
