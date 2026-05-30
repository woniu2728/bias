<template>
  <section class="ExtensionGeneratedSurface">
    <div v-if="surfaceCards.length" class="ExtensionGeneratedSurface-panel">
      <div class="ExtensionGeneratedSurface-sectionHead">
        <h3>相关页面</h3>
      </div>
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
    </div>

    <div v-if="visibleActionGroups.length" class="ExtensionGeneratedSurface-panels">
      <section
        v-for="group in visibleActionGroups"
        :key="group.key"
        class="ExtensionGeneratedSurface-panel"
      >
        <div class="ExtensionGeneratedSurface-sectionHead">
          <h3>{{ group.title }}</h3>
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
      </section>
    </div>

    <AdminInlineMessage v-if="errorMessage" tone="danger">{{ errorMessage }}</AdminInlineMessage>

    <AdminStateBlock v-if="!hasAnyAction" tone="subtle">
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

const resolvedSections = computed(() => resolveExtensionOperationsSections(props.extension))

const surfaceCards = computed(() => (
  resolveExtensionAdminPageCards(props.extension, { hostKind: 'operations' }).map((item) => ({
    key: item.key,
    label: item.label,
    icon: item.icon,
    target: buildExtensionRouteTarget(item.target, route),
  }))
))

const visibleActionGroups = computed(() => (
  resolvedSections.value.actionGroups
    .map((group) => ({
      ...group,
      title: normalizeGroupTitle(group),
      actions: group.actionType === 'admin'
        ? group.actions
          .filter(action => !['details', 'operations'].includes(action?.key))
          .map((action) => {
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
    .filter(group => group.actions.length > 0)
))

const hasAnyAction = computed(() => (
  surfaceCards.value.length > 0 || visibleActionGroups.value.length > 0
))

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

function normalizeGroupTitle(group) {
  if (group?.key === 'recommended') {
    return '常用操作'
  }
  if (group?.key === 'admin') {
    return '更多操作'
  }
  if (group?.key === 'runtime') {
    return '运行操作'
  }
  return group?.title || '操作'
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
  gap: 16px;
}

.ExtensionGeneratedSurface-panels {
  display: grid;
  gap: 16px;
}

.ExtensionGeneratedSurface-panel {
  padding: 20px;
  border: 1px solid var(--forum-border-color);
  border-radius: 16px;
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-sm);
}

.ExtensionGeneratedSurface-sectionHead {
  margin-bottom: 14px;
}

.ExtensionGeneratedSurface-sectionHead h3 {
  margin: 0;
  font-size: 17px;
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
  cursor: pointer;
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
