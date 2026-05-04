<template>
  <div class="sidebar-section sidebar-section--actions discussion-actions-scope">
    <button
      v-if="authStore.isAuthenticated"
      type="button"
      class="discussion-primary-action"
      :disabled="discussion.is_locked || isSuspended"
      @click="$emit('primary-action')"
    >
      <i class="fas fa-reply"></i>
      {{ hasActiveComposer ? '继续回复' : '回复' }}
    </button>
    <button
      v-else
      type="button"
      class="discussion-primary-action"
      @click="$emit('login-action')"
    >
      <i class="fas fa-sign-in-alt"></i>
      登录后回复
    </button>

    <div v-if="authStore.isAuthenticated && !isSuspended" class="discussion-secondary-row">
      <button
        type="button"
        class="discussion-follow-action"
        :class="{
          'is-active': discussion.is_subscribed,
          'is-standalone': !canShowDiscussionMenu
        }"
        :disabled="togglingSubscription"
        @click="$emit('toggle-subscription')"
      >
        <i :class="discussion.is_subscribed ? 'fas fa-bell-slash' : 'far fa-star'"></i>
        {{ togglingSubscription ? '提交中...' : (discussion.is_subscribed ? '取消关注' : '关注') }}
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

    <p v-if="authStore.isAuthenticated && hasActiveComposer" class="discussion-action-copy">
      当前讨论已有未发布回复草稿。
    </p>
    <p v-else-if="authStore.isAuthenticated && discussion.is_subscribed" class="discussion-action-copy">
      你会收到这条讨论后续回复的通知。
    </p>
    <p v-else-if="authStore.isAuthenticated && discussion.is_locked" class="discussion-action-copy">
      当前讨论已锁定，暂时无法继续回复。
    </p>
    <p v-else-if="authStore.isAuthenticated && isSuspended" class="discussion-action-copy discussion-action-copy--warning">
      {{ suspensionNotice }}
    </p>
  </div>
</template>

<script setup>
import ForumActionMenu from '@/components/forum/ForumActionMenu.vue'

defineProps({
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
  togglingSubscription: {
    type: Boolean,
    default: false
  },
  menuItems: {
    type: Array,
    default: () => []
  }
})

defineEmits([
  'primary-action',
  'login-action',
  'toggle-subscription',
  'toggle-menu',
  'menu-action'
])
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
