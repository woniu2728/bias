<template>
  <div class="AiAssistantPanel">
    <div class="AiAssistantPanel-tabs" role="tablist" aria-label="AI 助手">
      <button
        v-for="item in tabs"
        :key="item.key"
        type="button"
        :class="{ active: activeTab === item.key }"
        @click="activeTab = item.key"
      >
        <i :class="item.icon" aria-hidden="true"></i>
        <span>{{ item.label }}</span>
      </button>
    </div>

    <div class="AiAssistantPanel-body">
      <div v-if="error" class="AiAssistantPanel-error">{{ error }}</div>
      <AiResultCard v-if="result" :result="result" :title="resultTitle" />

      <div v-if="activeTab === 'coach'" class="AiAssistantPanel-actions">
        <button type="button" class="Button Button--primary" :disabled="loading" @click="runCoach">
          {{ loading ? '检查中...' : '检查提问质量' }}
        </button>
      </div>

      <div v-else-if="activeTab === 'roles'" class="AiAssistantPanel-roleGrid">
        <button
          v-for="role in roles"
          :key="role.key"
          type="button"
          class="AiAssistantPanel-role"
          :disabled="loading"
          @click="runRole(role.key)"
        >
          <i :class="role.icon" aria-hidden="true"></i>
          <span>{{ role.label }}</span>
          <small>{{ role.description }}</small>
        </button>
      </div>

      <div v-else class="AiAssistantPanel-actions">
        <button type="button" class="Button Button--primary" :disabled="loading" @click="insertResult">
          插入结果
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { api, computed, ref } from '@bias/core'
import AiResultCard from './AiResultCard.vue'

const props = defineProps({
  title: {
    type: String,
    default: '',
  },
  content: {
    type: String,
    default: '',
  },
  insertText: {
    type: Function,
    default: null,
  },
  selectionStart: {
    type: Number,
    default: 0,
  },
  selectionEnd: {
    type: Number,
    default: 0,
  },
  setToolPopoverVisible: {
    type: Function,
    default: null,
  },
})

const tabs = [
  { key: 'coach', label: '教练', icon: 'fas fa-wand-magic-sparkles' },
  { key: 'roles', label: '召唤', icon: 'fas fa-users-rays' },
  { key: 'insert', label: '插入', icon: 'fas fa-pen-to-square' },
]
const roles = [
  { key: 'scribe', label: '书记员', icon: 'fas fa-clipboard-list', description: '整理观点和下一步' },
  { key: 'detective', label: '侦探', icon: 'fas fa-magnifying-glass', description: '提炼搜索线索' },
  { key: 'challenger', label: '挑战官', icon: 'fas fa-scale-balanced', description: '提出反方追问' },
]

const activeTab = ref('coach')
const loading = ref(false)
const error = ref('')
const result = ref(null)

const resultTitle = computed(() => {
  if (result.value?.action === 'question_coach') return '提问教练'
  if (String(result.value?.action || '').startsWith('role_')) return 'AI 角色反馈'
  return 'AI 反馈'
})

async function runCoach() {
  await runRequest('/ai/question-coach', {
    title: props.title,
    content: props.content,
  })
}

async function runRole(role) {
  await runRequest('/ai/summon', {
    role,
    title: props.title,
    content: props.content,
  })
}

async function runRequest(url, payload) {
  loading.value = true
  error.value = ''
  try {
    result.value = await api.post(url, payload)
    activeTab.value = 'insert'
  } catch (requestError) {
    error.value = requestError?.response?.data?.message || requestError?.message || 'AI 请求失败'
  } finally {
    loading.value = false
  }
}

async function insertResult() {
  if (!props.insertText || !result.value) return
  const text = formatResultMarkdown(result.value)
  const prefix = props.content?.trim() ? '\n\n' : ''
  await props.insertText(`${prefix}${text}`, {
    start: props.selectionStart,
    end: props.selectionEnd,
    cursor: props.selectionStart + prefix.length + text.length,
  })
  props.setToolPopoverVisible?.(false)
}

function formatResultMarkdown(payload) {
  const lines = ['> AI 助手建议', '']
  if (payload.text) {
    lines.push(String(payload.text).trim(), '')
  }
  for (const card of Array.isArray(payload.cards) ? payload.cards : []) {
    const title = String(card?.title || '').trim()
    if (title) lines.push(`**${title}**`)
    for (const item of Array.isArray(card?.items) ? card.items : []) {
      const value = String(item || '').trim()
      if (value) lines.push(`- ${value}`)
    }
    lines.push('')
  }
  return lines.join('\n').trim()
}
</script>

<style scoped>
.AiAssistantPanel {
  display: grid;
  gap: 12px;
  width: min(520px, calc(100vw - 32px));
  padding: 12px;
}

.AiAssistantPanel-tabs {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
}

.AiAssistantPanel-tabs button,
.AiAssistantPanel-role {
  border: 1px solid var(--border-color, #dedede);
  border-radius: 8px;
  background: var(--control-bg, #fff);
  color: inherit;
  cursor: pointer;
}

.AiAssistantPanel-tabs button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 10px;
}

.AiAssistantPanel-tabs button.active {
  border-color: var(--primary-color, #3b82f6);
  color: var(--primary-color, #3b82f6);
}

.AiAssistantPanel-body {
  display: grid;
  gap: 12px;
}

.AiAssistantPanel-error {
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff1f0;
  color: #b42318;
}

.AiAssistantPanel-actions {
  display: flex;
  justify-content: flex-end;
}

.AiAssistantPanel-roleGrid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.AiAssistantPanel-role {
  display: grid;
  justify-items: center;
  gap: 5px;
  min-height: 96px;
  padding: 12px 8px;
  text-align: center;
}

.AiAssistantPanel-role i {
  color: var(--primary-color, #3b82f6);
}

.AiAssistantPanel-role span {
  font-weight: 700;
}

.AiAssistantPanel-role small {
  color: var(--muted-color, #667085);
  line-height: 1.4;
}

@media (max-width: 560px) {
  .AiAssistantPanel-roleGrid {
    grid-template-columns: 1fr;
  }
}
</style>
