<template>
  <div class="Modal Modal--small Modal--simple fade" :class="{ in: showing }" @click.stop>
    <div class="Modal-content">
      <div class="Modal-close">
        <button
          type="button"
          class="Button Button--icon Button--link"
          :aria-label="closeLabelText"
          @click="modalStore.dismiss()"
        >
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="Modal-header">
        <h3>{{ titleText }}</h3>
      </div>

      <div class="Modal-body">
        <p class="modal-form-description">
          {{ descriptionText }}
        </p>

        <div v-if="errorMessage" class="modal-form-error">
          {{ errorMessage }}
        </div>

        <div class="modal-form-group">
          <label for="post-report-reason">{{ reasonLabelText }}</label>
          <select
            id="post-report-reason"
            v-model="form.reason"
            name="reason"
            class="modal-form-control"
          >
            <option v-for="option in REPORT_REASON_OPTIONS" :key="option" :value="option">
              {{ option }}
            </option>
          </select>
        </div>

        <div class="modal-form-group">
          <label for="post-report-message">{{ messageLabelText }}</label>
          <p class="modal-form-help">
            {{ messageHelpText }}
          </p>
          <textarea
            id="post-report-message"
            v-model="form.message"
            name="message"
            rows="4"
            class="modal-form-control modal-form-control--textarea"
            :placeholder="messagePlaceholderText"
          ></textarea>
        </div>
      </div>

      <div class="Modal-footer Modal-footer--split">
        <button type="button" class="Button Button--secondary" :disabled="submitting" @click="modalStore.dismiss()">
          {{ cancelButtonText }}
        </button>
        <button type="button" class="Button Button--primary" :disabled="submitting" @click="submit">
          {{ submitButtonText }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  ref,
  computed,
  reactive,
  useModalStore
} from '@bias/core'
import { getUiCopy
} from '@bias/forum'

const props = defineProps({
  post: {
    type: Object,
    default: null
  },
  submitReport: {
    type: Function,
    required: true
  },
  showing: {
    type: Boolean,
    default: false
  }
})

const modalStore = useModalStore()
const REPORT_REASON_OPTIONS = [
  '垃圾广告',
  '骚扰攻击',
  '仇恨或歧视',
  '违规内容',
  '侵权/隐私',
  '灌水离题',
  '其他'
]
const submitting = ref(false)
const errorMessage = ref('')
const form = reactive({
  reason: '垃圾广告',
  message: ''
})
const closeLabelText = computed(() => getUiCopy({
  surface: 'post-report-close-label',
})?.text || '关闭')
const titleText = computed(() => getUiCopy({
  surface: 'post-report-title',
})?.text || '举报帖子')
const descriptionText = computed(() => getUiCopy({
  surface: 'post-report-description',
  postNumber: props.post?.number || '?',
})?.text || `帖子 #${props.post?.number || '?'} 会进入举报队列，版主可以直接在讨论页或后台查看并处理。`)
const reasonLabelText = computed(() => getUiCopy({
  surface: 'post-report-reason-label',
})?.text || '举报原因')
const messageLabelText = computed(() => getUiCopy({
  surface: 'post-report-message-label',
})?.text || '补充说明')
const messageHelpText = computed(() => getUiCopy({
  surface: 'post-report-message-help',
  reason: form.reason,
})?.text || (form.reason === '其他' ? '请尽量写清楚问题背景，方便版主快速判断。' : '可补充上下文、受影响内容或希望的处理方式。'))
const messagePlaceholderText = computed(() => getUiCopy({
  surface: 'post-report-message-placeholder',
})?.text || '告诉管理员这条帖子为什么需要处理')
const cancelButtonText = computed(() => getUiCopy({
  surface: 'modal-cancel-button',
})?.text || '取消')
const submitButtonText = computed(() => getUiCopy({
  surface: 'post-report-submit-button',
  submitting: submitting.value,
})?.text || (submitting.value ? '提交中...' : '提交举报'))

async function submit() {
  submitting.value = true
  errorMessage.value = ''

  try {
    const result = await props.submitReport({
      reason: form.reason,
      message: form.message
    })
    modalStore.close({ reported: true, flag: result })
  } catch (error) {
    errorMessage.value = error.response?.data?.error || error.message || (getUiCopy({
      surface: 'modal-submit-error',
    })?.text || '提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}
</script>
