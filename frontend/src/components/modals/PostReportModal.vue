<template>
  <div class="Modal Modal--small Modal--simple fade" :class="{ in: showing }" @click.stop>
    <div class="Modal-content">
      <div class="Modal-close">
        <button
          type="button"
          class="Button Button--icon Button--link"
          aria-label="关闭"
          @click="modalStore.dismiss()"
        >
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="Modal-header">
        <h3>举报帖子</h3>
      </div>

      <div class="Modal-body">
        <p class="modal-form-description">
          帖子 #{{ post?.number || '?' }} 会进入举报队列，版主可以直接在讨论页或后台查看并处理。
        </p>

        <div v-if="errorMessage" class="modal-form-error">
          {{ errorMessage }}
        </div>

        <div class="modal-form-group">
          <label for="post-report-reason">举报原因</label>
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
          <label for="post-report-message">补充说明</label>
          <p class="modal-form-help">
            {{ form.reason === '其他' ? '请尽量写清楚问题背景，方便版主快速判断。' : '可补充上下文、受影响内容或希望的处理方式。' }}
          </p>
          <textarea
            id="post-report-message"
            v-model="form.message"
            name="message"
            rows="4"
            class="modal-form-control modal-form-control--textarea"
            placeholder="告诉管理员这条帖子为什么需要处理"
          ></textarea>
        </div>
      </div>

      <div class="Modal-footer Modal-footer--split">
        <button type="button" class="Button Button--secondary" :disabled="submitting" @click="modalStore.dismiss()">
          取消
        </button>
        <button type="button" class="Button Button--primary" :disabled="submitting" @click="submit">
          {{ submitting ? '提交中...' : '提交举报' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useModalStore } from '@/stores/modal'

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
    errorMessage.value = error.response?.data?.error || error.message || '提交失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
