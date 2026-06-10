<template>
  <div class="sidebar-section sidebar-section--actions discussion-actions-scope">
    <button
      v-if="primaryAction"
      type="button"
      class="discussion-primary-action"
      :disabled="primaryAction.disabled"
      :title="primaryAction.disabledReason || primaryAction.description || ''"
      @click="$emit('sidebar-action', primaryAction.key)"
    >
      <i v-if="primaryAction.icon" :class="primaryAction.icon"></i>
      {{ primaryAction.label }}
    </button>

    <div v-if="secondaryAction" class="discussion-secondary-row">
      <button
        type="button"
        class="discussion-follow-action"
        :class="{
          'is-active': secondaryAction.active,
          'is-standalone': !canShowDiscussionMenu
        }"
        :disabled="secondaryAction.disabled"
        :title="secondaryAction.disabledReason || secondaryAction.description || ''"
        @click="$emit('sidebar-action', secondaryAction.key)"
      >
        <i v-if="secondaryAction.icon" :class="secondaryAction.icon"></i>
        {{ secondaryAction.label }}
      </button>
      <button
        v-if="canShowDiscussionMenu"
        type="button"
        class="discussion-menu-toggle"
        :class="{ 'is-active': showDiscussionMenu }"
        @click="$emit('toggle-menu')"
      >
        <i class="fas fa-chevron-down"></i>
      </button>
    </div>

    <div
      v-if="showDiscussionMenu && canShowDiscussionMenu"
      class="discussion-actions-menu"
    >
      <ForumActionMenu
        :items="menuItems"
        container-class="discussion-actions-menu-list"
        item-class="discussion-actions-menu-item"
        @select="$emit('menu-action', $event)"
      />
    </div>

    <p
      v-if="actionNotice"
      class="discussion-action-copy"
      :class="{ 'discussion-action-copy--warning': actionNotice.tone === 'warning' }"
    >
      {{ actionNotice.text || actionNotice.message }}
    </p>
  </div>
</template>

<script setup>
import { computed } from '@bias/core'
import { ForumActionMenu } from '@bias/forum'
import { getStateBlock } from '@bias/forum'

const props = defineProps({
  discussion: {
    type: Object,
    required: true
  },
  authStore: {
    type: Object,
    required: true
  },
  forumStore: {
    type: Object,
    default: null
  },
  isSuspended: {
    type: Boolean,
    default: false
  },
  suspensionNotice: {
    type: String,
    default: ''
  },
  hasActiveComposer: {
    type: Boolean,
    default: false
  },
  canShowDiscussionMenu: {
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
  showDiscussionMenu: {
    type: Boolean,
    default: false
  },
  menuItems: {
    type: Array,
    default: () => []
  },
  sidebarActionItems: {
    type: Array,
    default: () => []
  }
})

defineEmits([
  'sidebar-action',
  'toggle-menu',
  'menu-action'
])

const primaryAction = computed(() => props.sidebarActionItems[0] || null)
const secondaryAction = computed(() => props.sidebarActionItems[1] || null)
const actionNotice = computed(() => getStateBlock({
  surface: 'discussion-sidebar-action-notice',
  authStore: props.authStore,
  discussion: props.discussion,
  forumStore: props.forumStore,
  hasActiveComposer: props.hasActiveComposer,
  isSuspended: props.isSuspended,
  suspensionNotice: props.suspensionNotice,
}))
</script>

<style scoped>
.sidebar-section {
  background: var(--forum-bg-elevated);
  padding: 20px;
  border-radius: var(--forum-radius-md);
  margin-bottom: 20px;
  box-shadow: var(--forum-shadow-sm);
}

.sidebar-section--actions {
  position: relative;
  padding: 16px;
}

.discussion-primary-action {
  width: 100%;
  border: 0;
  border-radius: var(--forum-radius-md);
  padding: 12px 16px;
  background: var(--forum-accent-color);
  color: var(--forum-text-inverse);
  font-size: 15px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
}

.discussion-primary-action:hover {
  filter: brightness(0.96);
}

.discussion-primary-action:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.discussion-secondary-row {
  display: flex;
  margin-top: 12px;
}

.discussion-follow-action,
.discussion-menu-toggle {
  border: 0;
  background: var(--forum-bg-subtle);
  color: var(--forum-text-muted);
  cursor: pointer;
  height: 44px;
}

.discussion-follow-action {
  flex: 1;
  border-radius: var(--forum-radius-md) 0 0 var(--forum-radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}

.discussion-follow-action.is-standalone {
  border-radius: var(--forum-radius-md);
}

.discussion-follow-action.is-active {
  color: var(--forum-text-color);
}

.discussion-menu-toggle {
  width: 48px;
  border-left: 1px solid var(--forum-border-color);
  border-radius: 0 var(--forum-radius-md) var(--forum-radius-md) 0;
}

.discussion-follow-action:hover,
.discussion-menu-toggle:hover,
.discussion-menu-toggle.is-active {
  background: #e3ebf4;
}

.discussion-follow-action:disabled,
.discussion-menu-toggle:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.discussion-actions-menu {
  position: absolute;
  left: 16px;
  right: 16px;
  top: 72px;
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

.discussion-action-copy {
  margin: 12px 0 0;
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
  line-height: 1.6;
}

.discussion-action-copy--warning {
  color: var(--forum-warning-color);
}
</style>
