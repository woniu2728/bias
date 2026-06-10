<template>
  <div ref="rootEl" class="discussion-mobile-nav discussion-actions-scope" :class="{ 'is-open': showDiscussionMenu }">
    <div class="discussion-mobile-bar">
      <button
        type="button"
        class="discussion-mobile-action discussion-mobile-action--reply"
        :disabled="replyAction.disabled"
        :title="replyAction.title"
        @click="handleReplyAction"
      >
        <i :class="replyAction.icon"></i>
        <span>{{ replyAction.label }}</span>
      </button>

      <button
        v-if="secondaryAction"
        type="button"
        class="discussion-mobile-action"
        :class="{ 'is-active': secondaryAction.active }"
        :disabled="secondaryAction.disabled"
        :title="secondaryAction.disabledReason || secondaryAction.description || ''"
        @click="$emit('secondary-action', secondaryAction.key)"
      >
        <i :class="secondaryAction.icon"></i>
        <span>{{ secondaryAction.label }}</span>
      </button>

      <button
        type="button"
        class="discussion-mobile-action"
        :title="positionActionTitle"
        @click="togglePositionPanel"
      >
        <i class="fas fa-grip-lines"></i>
        <span>{{ positionActionLabel }}</span>
      </button>

      <button
        type="button"
        class="discussion-mobile-action"
        :title="shareTitle"
        @click="$emit('share-discussion')"
      >
        <i class="fas fa-arrow-up-from-bracket"></i>
        <span>{{ shareLabel }}</span>
      </button>

      <button
        v-if="menuItems.length"
        type="button"
        class="discussion-mobile-action"
        :class="{ 'is-active': showDiscussionMenu }"
        :title="moreTitle"
        @click="$emit('toggle-menu')"
      >
        <i class="fas fa-ellipsis"></i>
        <span>{{ moreLabel }}</span>
      </button>
    </div>

    <div v-if="showPositionPanel" class="discussion-actions-menu discussion-actions-menu--mobile discussion-actions-menu--scrubber">
      <div class="discussion-mobile-scrubber">
        <div class="discussion-mobile-scrubber__meta">
          <strong>{{ scrubberPositionText }}</strong>
          <span>{{ scrubberDescription }}</span>
        </div>
        <p v-if="unreadCount" class="discussion-mobile-scrubber__unread">
          未读从第 {{ unreadStartPostNumber }} 楼开始，共 {{ unreadCount }} 条
        </p>
        <div class="discussion-mobile-scrubber__actions">
          <button type="button" class="discussion-mobile-chip" @click="jumpToStart">原帖</button>
          <button type="button" class="discussion-mobile-chip" :disabled="!unreadStartPostNumber" @click="jumpToUnread">未读</button>
          <button type="button" class="discussion-mobile-chip" @click="jumpToCurrent">当前</button>
          <button type="button" class="discussion-mobile-chip" @click="jumpToEnd">现在</button>
        </div>
        <form class="discussion-mobile-scrubber__form" @submit.prevent="submitPositionJump">
          <input
            v-model="positionInput"
            class="discussion-mobile-scrubber__input"
            type="number"
            min="1"
            :max="maxPostNumber"
            inputmode="numeric"
            placeholder="输入楼层"
          />
          <button type="submit" class="discussion-mobile-scrubber__submit">跳转</button>
        </form>
      </div>
    </div>

    <div v-if="showDiscussionMenu" class="discussion-actions-menu discussion-actions-menu--mobile">
      <ForumActionMenu
        :items="menuItems"
        container-class="discussion-actions-menu-list"
        item-class="discussion-actions-menu-item"
        @select="$emit('menu-action', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import {
  ref,
  computed } from '@bias/core'
import { ForumActionMenu
} from '@bias/forum'
import { getUiCopy } from '@bias/forum'

const props = defineProps({
  discussion: {
    type: Object,
    required: true
  },
  authStore: {
    type: Object,
    required: true
  },
  isSuspended: {
    type: Boolean,
    default: false
  },
  showDiscussionMenu: {
    type: Boolean,
    default: false
  },
  canReplyFromMenu: {
    type: Boolean,
    default: false
  },
  hasActiveComposer: {
    type: Boolean,
    default: false
  },
  canEditDiscussion: {
    type: Boolean,
    default: false
  },
  canModerateDiscussionSettings: {
    type: Boolean,
    default: false
  },
  scrubberPositionText: {
    type: String,
    default: ''
  },
  scrubberDescription: {
    type: String,
    default: ''
  },
  unreadCount: {
    type: Number,
    default: 0
  },
  unreadStartPostNumber: {
    type: Number,
    default: null
  },
  maxPostNumber: {
    type: Number,
    default: 1
  },
  menuItems: {
    type: Array,
    default: () => []
  },
  secondaryAction: {
    type: Object,
    default: null
  }
})

const emit = defineEmits([
  'menu-action',
  'jump-to-post',
  'open-composer',
  'open-login-for-reply',
  'secondary-action',
  'share-discussion',
  'toggle-menu',
])

const rootEl = ref(null)
const showPositionPanel = ref(false)
const positionInput = ref('')

const replyAction = computed(() => {
  if (props.authStore?.isAuthenticated && props.canReplyFromMenu) {
    return {
      icon: 'fas fa-reply',
      label: props.hasActiveComposer
        ? getUiCopy({ surface: 'discussion-mobile-action-continue-reply' })?.text || '继续回复'
        : getUiCopy({ surface: 'discussion-mobile-action-reply' })?.text || '回复',
      title: props.hasActiveComposer
        ? getUiCopy({ surface: 'discussion-mobile-action-continue-reply-description' })?.text || '继续当前未发布的回复草稿。'
        : getUiCopy({ surface: 'discussion-mobile-action-reply-description' })?.text || '在当前讨论中开始撰写回复。',
      disabled: false,
      action: 'reply'
    }
  }

  return {
    icon: 'fas fa-right-to-bracket',
    label: getUiCopy({ surface: 'discussion-mobile-action-login' })?.text || '登录后回复',
    title: getUiCopy({ surface: 'discussion-mobile-action-login-description' })?.text || '登录后才可以参与当前讨论。',
    disabled: false,
    action: 'login'
  }
})

const secondaryAction = computed(() => {
  return props.secondaryAction || null
})

const shareLabel = computed(() => getUiCopy({
  surface: 'discussion-mobile-action-share',
})?.text || '分享')
const shareTitle = computed(() => getUiCopy({
  surface: 'discussion-mobile-action-share-description',
})?.text || '分享当前讨论链接。')
const moreLabel = computed(() => getUiCopy({
  surface: 'discussion-mobile-action-more',
})?.text || '更多')
const moreTitle = computed(() => getUiCopy({
  surface: 'discussion-mobile-action-more-description',
})?.text || '查看更多讨论操作。')
const positionActionLabel = computed(() => getUiCopy({
  surface: 'discussion-mobile-action-position',
})?.text || '楼层')
const positionActionTitle = computed(() => getUiCopy({
  surface: 'discussion-mobile-action-position-description',
})?.text || '打开轻量楼层跳转。')

function handleReplyAction() {
  if (replyAction.value.action === 'reply') {
    emit('open-composer')
    return
  }

  emit('open-login-for-reply')
}

function togglePositionPanel() {
  showPositionPanel.value = !showPositionPanel.value
  if (showPositionPanel.value) {
    positionInput.value = String(sanitizePostNumber(props.unreadStartPostNumber || props.maxPostNumber || 1))
  }
}

function closePositionPanel() {
  showPositionPanel.value = false
}

function emitJump(number) {
  emit('jump-to-post', sanitizePostNumber(number))
  closePositionPanel()
}

function jumpToStart() {
  emitJump(1)
}

function jumpToUnread() {
  if (!props.unreadStartPostNumber) return
  emitJump(props.unreadStartPostNumber)
}

function jumpToCurrent() {
  emitJump(extractCurrentPostNumber())
}

function jumpToEnd() {
  emitJump(props.maxPostNumber)
}

function submitPositionJump() {
  emitJump(positionInput.value)
}

function extractCurrentPostNumber() {
  const match = String(props.scrubberPositionText || '').match(/^(\d+)/)
  return match ? Number(match[1]) : 1
}

function sanitizePostNumber(value) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return 1
  return Math.max(1, Math.min(Number(props.maxPostNumber || 1), Math.floor(parsed)))
}

function getRootEl() {
  return rootEl.value
}

defineExpose({
  closePositionPanel,
  getRootEl
})
</script>

<style scoped>
.discussion-mobile-nav {
  display: none;
}

.discussion-mobile-bar {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  padding: 12px 15px;
  border-top: 1px solid var(--forum-border-color);
  border-bottom: 1px solid var(--forum-border-color);
  background:
    linear-gradient(180deg, rgba(244, 248, 252, 0.98), rgba(255, 255, 255, 0.98));
}

.discussion-mobile-action {
  min-height: 58px;
  padding: 8px 6px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  background: rgba(255, 255, 255, 0.92);
  color: var(--forum-text-muted);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
}

.discussion-mobile-action i {
  font-size: 15px;
}

.discussion-mobile-action--reply {
  background: var(--forum-accent-color);
  border-color: var(--forum-accent-color);
  color: var(--forum-text-inverse);
}

.discussion-mobile-action.is-active {
  color: var(--forum-text-color);
  border-color: rgba(77, 105, 142, 0.28);
  background: rgba(225, 234, 244, 0.9);
}

.discussion-mobile-action:disabled {
  opacity: 0.6;
}

.discussion-actions-menu {
  padding: 8px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-md);
  z-index: 5;
}

.discussion-actions-menu-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.discussion-actions-menu--scrubber {
  padding: 14px 15px 16px;
}

.discussion-mobile-scrubber {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.discussion-mobile-scrubber__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.discussion-mobile-scrubber__meta strong {
  color: var(--forum-text-color);
  font-size: 14px;
}

.discussion-mobile-scrubber__meta span,
.discussion-mobile-scrubber__unread {
  color: var(--forum-text-soft);
  font-size: 12px;
  line-height: 1.5;
}

.discussion-mobile-scrubber__unread {
  margin: 0;
}

.discussion-mobile-scrubber__actions {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.discussion-mobile-chip {
  min-height: 38px;
  border: 1px solid var(--forum-border-color);
  border-radius: 999px;
  background: var(--forum-bg-subtle);
  color: var(--forum-text-color);
  font-size: 12px;
  font-weight: 700;
}

.discussion-mobile-chip:disabled {
  opacity: 0.5;
}

.discussion-mobile-scrubber__form {
  display: flex;
  gap: 8px;
}

.discussion-mobile-scrubber__input {
  flex: 1;
  min-width: 0;
  min-height: 40px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  padding: 0 12px;
  background: var(--forum-bg-elevated);
  color: var(--forum-text-color);
}

.discussion-mobile-scrubber__submit {
  min-width: 72px;
  min-height: 40px;
  border: 0;
  border-radius: var(--forum-radius-md);
  background: var(--forum-accent-color);
  color: var(--forum-text-inverse);
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 768px) {
  .discussion-mobile-nav {
    display: block;
    margin: 0;
  }

  .discussion-actions-menu--mobile {
    position: relative;
    left: auto;
    right: auto;
    top: auto;
    margin: 0 15px;
    border-top: 0;
    border-top-left-radius: 0;
    border-top-right-radius: 0;
    box-shadow: var(--forum-shadow-sm);
  }
}
</style>
