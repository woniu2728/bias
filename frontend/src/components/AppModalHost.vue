<template>
  <Teleport to="body">
    <div
      v-if="current"
      class="Modal-backdrop"
      :data-showing="showing ? '' : null"
      @click="handleBackdropClick"
    >
      <div class="ModalManager" :data-modal-key="current.key">
        <component
          v-if="current.kind === 'custom'"
          :is="current.component"
          v-bind="current.props"
          :showing="showing"
          @click.stop
        />

        <div
          v-else
          class="Modal fade"
          :class="[current.className, sizeClass, { in: showing }]"
          @click.stop
        >
          <div class="Modal-content">
            <div v-if="current.dismissibleViaCloseButton" class="Modal-close">
              <button
                type="button"
                class="Button Button--icon Button--link"
                aria-label="关闭"
                @click="handleDismiss"
              >
                <i class="fas fa-times"></i>
              </button>
            </div>

            <div class="Modal-header">
              <h3>{{ current.title }}</h3>
            </div>

            <div class="Modal-body">
              <p class="Modal-copy">{{ current.message }}</p>
            </div>

            <div class="Modal-footer" :class="{ 'Modal-footer--split': current.kind === 'confirm' }">
              <button
                v-if="current.kind === 'confirm'"
                type="button"
                class="Button Button--secondary"
                @click="handleDismiss"
              >
                {{ current.cancelText }}
              </button>
              <button
                ref="primaryAction"
                type="button"
                class="Button"
                :class="primaryButtonClass"
                @click="handlePrimaryAction"
              >
                {{ current.confirmText }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useModalStore } from '@/stores/modal'

const modalStore = useModalStore()
const current = computed(() => modalStore.current)
const showing = ref(false)
const primaryAction = ref(null)

const sizeClass = computed(() => {
  if (!current.value?.size) return ''
  return `Modal--${current.value.size}`
})

const primaryButtonClass = computed(() => {
  if (current.value?.tone === 'danger') return 'Button--danger'
  return 'Button--primary'
})

watch(
  () => current.value?.key,
  async key => {
    showing.value = false

    if (!key) {
      document.body.classList.remove('has-modal-open')
      document.body.style.overflow = ''
      return
    }

    document.body.classList.add('has-modal-open')
    document.body.style.overflow = 'hidden'

    await nextTick()
    requestAnimationFrame(() => {
      showing.value = true
      primaryAction.value?.focus()
    })
  },
  { immediate: true }
)

function handlePrimaryAction() {
  if (!current.value) return

  if (current.value.kind === 'confirm') {
    modalStore.close(true)
    return
  }

  modalStore.close(true)
}

function handleDismiss() {
  modalStore.dismiss()
}

function handleBackdropClick() {
  if (!current.value?.dismissibleViaBackdropClick) return
  modalStore.dismiss()
}

function handleWindowKeydown(event) {
  if (event.key !== 'Escape') return
  if (!current.value?.dismissibleViaEscKey) return

  event.preventDefault()
  modalStore.dismiss()
}

if (typeof window !== 'undefined') {
  window.addEventListener('keydown', handleWindowKeydown)
}

onBeforeUnmount(() => {
  document.body.classList.remove('has-modal-open')
  document.body.style.overflow = ''
  if (typeof window !== 'undefined') {
    window.removeEventListener('keydown', handleWindowKeydown)
  }
})
</script>

<style>
.Modal-backdrop {
  --modal-backdrop-color: rgba(31, 41, 51, 0.56);
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--modal-backdrop-color);
  opacity: 0;
  transition: opacity 0.2s ease-out;
  z-index: 1400;
}

.Modal-backdrop[data-showing] {
  opacity: 1;
}

.ModalManager {
  position: fixed;
  inset: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 24px 0;
  z-index: 1401;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.Modal {
  position: relative;
  width: min(100% - 32px, 600px);
  margin: 72px auto;
  border-radius: 12px;
  transform: scale(0.92) translateY(12px);
  opacity: 0;
  transition: transform 0.2s ease-out, opacity 0.2s ease-out;
  box-shadow: 0 22px 48px rgba(15, 23, 42, 0.24);
}

.Modal.in {
  transform: scale(1) translateY(0);
  opacity: 1;
}

.Modal--small {
  width: min(100% - 32px, 420px);
}

.Modal--large {
  width: min(100% - 32px, 760px);
}

.Modal-content {
  position: relative;
  overflow: hidden;
  border-radius: 12px;
  background: #fff;
}

.Modal-close {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 2;
}

.Button.Button--icon.Button--link {
  width: 34px;
  height: 34px;
  padding: 0;
  border-radius: 50%;
  background: transparent;
  color: #7b8794;
}

.Button.Button--icon.Button--link:hover {
  background: #eef2f6;
  color: #415061;
}

.Modal-header {
  padding: 24px 28px 0;
  text-align: center;
}

.Modal-header h3 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #22303d;
}

.Modal-body {
  padding: 18px 28px 22px;
  color: #526170;
}

.Modal-copy {
  margin: 0;
  line-height: 1.7;
  font-size: 14px;
  white-space: pre-line;
}

.Modal-footer {
  padding: 0 28px 26px;
  text-align: center;
}

.Modal-footer--split {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.Button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  border-radius: 8px;
  padding: 0 16px;
  font-weight: 600;
}

.Button--primary {
  background: #4d698e;
  color: #fff;
}

.Button--primary:hover {
  filter: brightness(0.95);
}

.Button--secondary {
  background: #e7edf3;
  color: #536274;
}

.Button--secondary:hover {
  background: #dde5ed;
}

.Button--danger {
  background: #c94d3f;
  color: #fff;
}

.Button--danger:hover {
  background: #b64337;
}

@media (max-width: 768px) {
  .ModalManager {
    padding: 0;
    align-items: stretch;
  }

  .Modal {
    width: 100%;
    min-height: 100dvh;
    margin: 0;
    border-radius: 0;
    transform: translateY(100dvh);
  }

  .Modal.in {
    transform: translateY(0);
  }

  .Modal-content {
    min-height: 100dvh;
    border-radius: 0;
  }

  .Modal-header {
    padding: 22px 20px 0;
    text-align: left;
  }

  .Modal-body {
    padding: 18px 20px 20px;
  }

  .Modal-footer {
    padding: 0 20px 24px;
  }

  .Modal-footer--split {
    flex-direction: column-reverse;
  }

  .Modal-footer--split .Button {
    width: 100%;
  }
}
</style>
