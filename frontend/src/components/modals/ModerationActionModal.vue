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
        <h3>{{ title }}</h3>
      </div>

      <div class="Modal-body">
        <p class="modal-form-description">{{ description }}</p>

        <div v-if="errorMessage" class="modal-form-error">
          {{ errorMessage }}
        </div>

        <div class="modal-form-group">
          <label for="moderation-action-note">处理备注</label>
          <textarea
            id="moderation-action-note"
            v-model="note"
            name="note"
            rows="4"
            class="modal-form-control modal-form-control--textarea"
            :placeholder="placeholder"
          ></textarea>
          <p class="modal-form-help">备注会同步显示给内容作者，建议简明说明处理原因。</p>
        </div>
      </div>

      <div class="Modal-footer Modal-footer--split">
        <button type="button" class="Button Button--secondary" :disabled="submitting" @click="modalStore.dismiss()">
          取消
        </button>
        <button type="button" class="Button" :class="confirmButtonClass" :disabled="submitting" @click="submit">
          {{ submitting ? '提交中...' : confirmText }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useModalStore } from '@/stores/modal'

const props = defineProps({
  title: {
    type: String,
    default: '处理内容'
  },
  description: {
    type: String,
    default: ''
  },
  confirmText: {
    type: String,
    default: '提交'
  },
  confirmTone: {
    type: String,
    default: 'primary'
  },
  placeholder: {
    type: String,
    default: '例如：内容符合社区规范，已通过审核'
  },
  submitAction: {
    type: Function,
    required: true
  },
  showing: {
    type: Boolean,
    default: false
  }
})

const modalStore = useModalStore()
const note = ref('')
const submitting = ref(false)
const errorMessage = ref('')

const confirmButtonClass = {
  'Button--primary': props.confirmTone === 'primary',
  'Button--danger': props.confirmTone === 'danger'
}

async function submit() {
  submitting.value = true
  errorMessage.value = ''

  try {
    const result = await props.submitAction({
      note: note.value.trim()
    })
    modalStore.close(result || { success: true, note: note.value.trim() })
  } catch (error) {
    errorMessage.value = error.response?.data?.error || error.message || '提交失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>
