<template>
  <div class="Modal Modal--large Modal--ai-summary fade" :class="{ in: showing }" @click.stop>
    <div class="Modal-content AiDiscussionSummaryModal">
      <div class="Modal-close">
        <button type="button" class="Button Button--icon Button--link" aria-label="关闭" @click="modalStore.dismiss()">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <header class="Modal-header">
        <h3>AI 讨论纪要</h3>
      </header>

      <main class="Modal-body">
        <div v-if="loading" class="AiDiscussionSummaryModal-state">正在整理讨论...</div>
        <div v-else-if="error" class="AiDiscussionSummaryModal-error">{{ error }}</div>
        <AiResultCard v-else-if="result" :result="result" title="讨论纪要" />
      </main>

      <footer class="Modal-footer">
        <button type="button" class="Button Button--secondary" @click="modalStore.dismiss()">关闭</button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { api, onMounted, ref, useModalStore } from '@bias/core'
import AiResultCard from './AiResultCard.vue'

const props = defineProps({
  discussionId: {
    type: Number,
    required: true,
  },
  showing: {
    type: Boolean,
    default: false,
  },
})

const modalStore = useModalStore()
const loading = ref(true)
const error = ref('')
const result = ref(null)

onMounted(async () => {
  try {
    result.value = await api.post('/ai/discussion-summary', {
      discussion_id: props.discussionId,
    })
  } catch (requestError) {
    error.value = requestError?.response?.data?.message || requestError?.message || 'AI 纪要生成失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.AiDiscussionSummaryModal {
  display: grid;
  max-height: min(720px, calc(100vh - 64px));
}

.AiDiscussionSummaryModal-state,
.AiDiscussionSummaryModal-error {
  padding: 14px;
  border-radius: 8px;
}

.AiDiscussionSummaryModal-state {
  color: var(--muted-color, #667085);
}

.AiDiscussionSummaryModal-error {
  background: #fff1f0;
  color: #b42318;
}
</style>
