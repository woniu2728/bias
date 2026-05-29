<template>
  <section class="ExtensionGeneratedSurface">
    <header class="ExtensionGeneratedSurface-hero">
      <p class="ExtensionGeneratedSurface-kicker">{{ operationsProfile.kicker }}</p>
      <h2>{{ operationsProfile.title }}</h2>
      <p>{{ heroDescription }}</p>
      <div v-if="operationsProfile.highlights.length" class="ExtensionGeneratedSurface-highlights">
        <span
          v-for="item in operationsProfile.highlights"
          :key="item"
          class="ExtensionGeneratedSurface-highlight"
        >
          {{ item }}
        </span>
      </div>
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

    <section v-if="surfaceCards.length" class="ExtensionGeneratedSurface-panel">
      <h3>关联后台入口</h3>
      <div class="ExtensionGeneratedSurface-actions">
        <router-link
          v-for="item in surfaceCards"
          :key="item.key"
          :to="item.target"
          class="ExtensionGeneratedAction"
        >
          <i v-if="item.icon" :class="item.icon"></i>
          <span>{{ item.label }}</span>
        </router-link>
      </div>
    </section>

    <section v-if="capabilitySummaryItems.length" class="ExtensionGeneratedSurface-panel">
      <h3>能力摘要</h3>
      <div class="ExtensionGeneratedSurface-grid ExtensionGeneratedSurface-grid--summary">
        <article
          v-for="item in capabilitySummaryItems"
          :key="item.key"
          class="ExtensionGeneratedSurface-card ExtensionGeneratedSurface-card--subtle"
        >
          <small>{{ item.label }}</small>
          <strong>{{ item.count }}</strong>
        </article>
      </div>
    </section>

    <section v-if="capabilityPanels.length" class="ExtensionGeneratedSurface-panel">
      <h3>已注册能力</h3>
      <div class="ExtensionGeneratedSurface-capabilities">
        <article
          v-for="panel in capabilityPanels"
          :key="panel.key"
          class="ExtensionGeneratedSurface-capabilityCard"
        >
          <div class="ExtensionGeneratedSurface-capabilityHead">
            <strong>{{ panel.label }}</strong>
            <span>{{ panel.items.length }}</span>
          </div>
          <ul class="ExtensionGeneratedSurface-capabilityList">
            <li v-for="item in panel.items.slice(0, 4)" :key="item.key">
              <strong>{{ item.label }}</strong>
              <code>{{ item.meta }}</code>
            </li>
          </ul>
        </article>
      </div>
    </section>

    <section v-if="focusSections.length" class="ExtensionGeneratedSurface-panel">
      <h3>重点范围</h3>
      <div class="ExtensionGeneratedSurface-focusGrid">
        <article
          v-for="section in focusSections"
          :key="section.key"
          class="ExtensionGeneratedSurface-focusCard"
        >
          <div class="ExtensionGeneratedSurface-focusHead">
            <strong>{{ section.title }}</strong>
            <span>{{ section.items.length }}</span>
          </div>
          <p>{{ section.description }}</p>
          <ul class="ExtensionGeneratedSurface-focusList">
            <li v-for="item in section.items.slice(0, 3)" :key="item.key">
              <strong>{{ item.label }}</strong>
              <code>{{ item.meta }}</code>
            </li>
          </ul>
        </article>
      </div>
    </section>

    <section v-if="actionGroups.length" class="ExtensionGeneratedSurface-panel">
      <h3>操作分区</h3>
      <div class="ExtensionGeneratedSurface-actionGroups">
        <article
          v-for="group in actionGroups"
          :key="group.key"
          class="ExtensionGeneratedSurface-actionGroup"
        >
          <div class="ExtensionGeneratedSurface-actionGroupHead">
            <strong>{{ group.title }}</strong>
            <p>{{ group.description }}</p>
          </div>
          <div class="ExtensionGeneratedSurface-actions">
            <template v-for="action in group.actions" :key="`${group.key}-${action.key}`">
              <button
                v-if="group.actionType === 'runtime'"
                type="button"
                class="ExtensionGeneratedAction"
                :class="resolveActionToneClass(action)"
                :disabled="actionLoading"
                @click="runRuntimeAction(action)"
              >
                {{ actionLoading ? '处理中...' : action.label }}
              </button>
              <router-link
                v-else-if="action.kind === 'route'"
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
        </article>
      </div>
      <AdminInlineMessage v-if="errorMessage" tone="danger">{{ errorMessage }}</AdminInlineMessage>
    </section>

    <section v-if="nextSteps.length" class="ExtensionGeneratedSurface-panel">
      <h3>下一步</h3>
      <ul class="ExtensionGeneratedSurface-nextSteps">
        <li v-for="item in nextSteps" :key="item">{{ item }}</li>
      </ul>
    </section>

    <AdminStateBlock v-if="!adminActions.length && !runtimeActions.length" tone="subtle">
      当前扩展未声明可执行后台动作。
    </AdminStateBlock>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import api from '../../api'
import { useModalStore } from '../../stores/modal'
import AdminInlineMessage from '../components/AdminInlineMessage.vue'
import AdminStateBlock from '../components/AdminStateBlock.vue'
import {
  buildExtensionRouteTarget,
  resolveExtensionAdminPageCards,
  resolveExtensionNavigationSource,
  resolveExtensionOperationsSections,
} from '../extensions/diagnostics'

const props = defineProps({
  extension: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['extension-updated'])

const route = useRoute()
const modalStore = useModalStore()
const actionLoading = ref(false)
const errorMessage = ref('')

const adminActions = computed(() => (
  (Array.isArray(props.extension?.admin_actions) ? props.extension.admin_actions : []).map((action) => {
    if (action?.kind !== 'route') {
      return action
    }
    return {
      ...action,
      target: buildExtensionRouteTarget(action.target, resolveExtensionNavigationSource(route)),
    }
  })
))

const runtimeActions = computed(() => (
  Array.isArray(props.extension?.runtime_actions) ? props.extension.runtime_actions : []
))

const surfaceCards = computed(() => (
  resolveExtensionAdminPageCards(props.extension, { hostKind: 'operations' }).map((item) => ({
    key: item.key,
    label: item.label,
    icon: item.icon,
    target: buildExtensionRouteTarget(item.target, route),
  }))
))

const capabilitySummaryItems = computed(() => (
  resolvedSections.value.capabilitySummaryItems
))

const capabilityPanels = computed(() => (
  resolvedSections.value.capabilityPanels
))

const resolvedSections = computed(() => resolveExtensionOperationsSections(props.extension))
const operationsProfile = computed(() => resolvedSections.value.profile)
const focusSections = computed(() => resolvedSections.value.focusSections)
const actionGroups = computed(() => (
  resolvedSections.value.actionGroups.map((group) => ({
    ...group,
    actions: group.actionType === 'admin'
      ? group.actions.map((action) => {
        if (action?.kind !== 'route') {
          return action
        }
        return {
          ...action,
          target: buildExtensionRouteTarget(action.target, resolveExtensionNavigationSource(route)),
        }
      })
      : group.actions,
  }))
))
const nextSteps = computed(() => resolvedSections.value.nextSteps)

const heroDescription = computed(() => {
  if (capabilitySummaryItems.value.length) {
    return operationsProfile.value.description
  }
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

.ExtensionGeneratedSurface-highlights {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.ExtensionGeneratedSurface-highlight {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.62);
  color: var(--forum-text-color);
  font-size: 12px;
  font-weight: 700;
}

.ExtensionGeneratedSurface-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.ExtensionGeneratedSurface-grid--summary {
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
}

.ExtensionGeneratedSurface-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
}

.ExtensionGeneratedSurface-card--subtle {
  background: var(--forum-bg-subtle);
}

.ExtensionGeneratedSurface-card small {
  color: var(--forum-text-soft);
}

.ExtensionGeneratedSurface-capabilities {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.ExtensionGeneratedSurface-focusGrid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.ExtensionGeneratedSurface-capabilityCard {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}

.ExtensionGeneratedSurface-focusCard {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: linear-gradient(180deg, var(--forum-bg-subtle) 0%, var(--forum-bg-elevated) 100%);
}

.ExtensionGeneratedSurface-capabilityHead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ExtensionGeneratedSurface-focusHead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.ExtensionGeneratedSurface-capabilityHead span {
  color: var(--forum-text-soft);
  font-size: 12px;
  font-weight: 700;
}

.ExtensionGeneratedSurface-focusHead span {
  color: var(--forum-text-soft);
  font-size: 12px;
  font-weight: 700;
}

.ExtensionGeneratedSurface-capabilityList {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.ExtensionGeneratedSurface-capabilityList li {
  display: grid;
  gap: 4px;
}

.ExtensionGeneratedSurface-capabilityList code {
  color: var(--forum-text-soft);
}

.ExtensionGeneratedSurface-focusCard p {
  margin: 0;
  color: var(--forum-text-muted);
  line-height: 1.6;
}

.ExtensionGeneratedSurface-focusList {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.ExtensionGeneratedSurface-focusList li {
  display: grid;
  gap: 4px;
}

.ExtensionGeneratedSurface-focusList code {
  color: var(--forum-text-soft);
}

.ExtensionGeneratedSurface-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.ExtensionGeneratedSurface-actionGroups {
  display: grid;
  gap: 12px;
}

.ExtensionGeneratedSurface-actionGroup {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--forum-border-color);
  border-radius: 14px;
  background: var(--forum-bg-subtle);
}

.ExtensionGeneratedSurface-actionGroupHead {
  display: grid;
  gap: 6px;
}

.ExtensionGeneratedSurface-actionGroupHead p {
  margin: 0;
  color: var(--forum-text-muted);
  line-height: 1.6;
}

.ExtensionGeneratedSurface-nextSteps {
  display: grid;
  gap: 10px;
  margin: 0;
  padding-left: 18px;
  color: var(--forum-text-muted);
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
