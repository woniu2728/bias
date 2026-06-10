<template>
  <aside class="sidebar">
    <DiscussionSidebarActions
      :discussion="discussion"
      :auth-store="authStore"
      :forum-store="forumStore"
      :is-suspended="isSuspended"
      :suspension-notice="suspensionNotice"
      :has-active-composer="hasActiveComposer"
      :can-show-discussion-menu="canShowDiscussionMenu"
      :can-edit-discussion="canEditDiscussion"
      :can-moderate-discussion-settings="canModerateDiscussionSettings"
      :show-discussion-menu="showDiscussionMenu"
      :menu-items="menuItems"
      :sidebar-action-items="sidebarActionItems"
      @sidebar-action="$emit('sidebar-action', $event)"
      @toggle-menu="$emit('toggle-menu')"
      @menu-action="$emit('menu-action', $event)"
    />

    <div v-if="authStore.isAuthenticated && isSuspended" class="sidebar-section sidebar-section--warning">
      <h3>{{ suspensionTitle }}</h3>
      <p class="subscription-copy">{{ suspensionNotice }}</p>
    </div>

    <DiscussionSidebarScrubber
      ref="scrubberRef"
      :scrubber-scrollbar-style="scrubberScrollbarStyle"
      :scrubber-before-percent="scrubberBeforePercent"
      :scrubber-after-percent="scrubberAfterPercent"
      :scrubber-handle-percent="scrubberHandlePercent"
      :scrubber-dragging="scrubberDragging"
      :unread-count="unreadCount"
      :unread-top-percent="unreadTopPercent"
      :unread-height-percent="unreadHeightPercent"
      :scrubber-position-text="scrubberPositionText"
      :scrubber-description="scrubberDescription"
      :max-post-number="maxPostNumber"
      @jump-to-post="$emit('jump-to-post', $event)"
      @scrubber-track-click="$emit('scrubber-track-click', $event)"
      @scrubber-handle-pointerdown="$emit('scrubber-handle-pointerdown', $event)"
    />
  </aside>
</template>

<script setup>

import {
  ref,
  computed } from '@bias/core'
import DiscussionSidebarActions from './DiscussionSidebarActions.vue'
import DiscussionSidebarScrubber from './DiscussionSidebarScrubber.vue'
import { getUiCopy
} from '@bias/forum'

defineProps({
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
  },
  scrubberScrollbarStyle: {
    type: Object,
    default: () => ({})
  },
  scrubberBeforePercent: {
    type: Number,
    default: 0
  },
  scrubberAfterPercent: {
    type: Number,
    default: 0
  },
  scrubberHandlePercent: {
    type: Number,
    default: 100
  },
  scrubberDragging: {
    type: Boolean,
    default: false
  },
  unreadCount: {
    type: Number,
    default: 0
  },
  unreadTopPercent: {
    type: Number,
    default: 0
  },
  unreadHeightPercent: {
    type: Number,
    default: 0
  },
  scrubberPositionText: {
    type: String,
    default: ''
  },
  scrubberDescription: {
    type: String,
    default: ''
  },
  maxPostNumber: {
    type: Number,
    default: 1
  }
})

defineEmits([
  'sidebar-action',
  'toggle-menu',
  'menu-action',
  'jump-to-post',
  'scrubber-track-click',
  'scrubber-handle-pointerdown'
])

const scrubberRef = ref(null)

function getScrubberPanelEl() {
  return scrubberRef.value?.getScrubberPanelEl?.() || null
}

function getScrubberTrackEl() {
  return scrubberRef.value?.getScrubberTrackEl?.() || null
}

defineExpose({
  getScrubberPanelEl,
  getScrubberTrackEl
})

const suspensionTitle = computed(() => getUiCopy({
  surface: 'discussion-sidebar-suspension-title',
})?.text || '账号状态')
</script>

<style scoped>
.sidebar {
  height: fit-content;
  position: sticky;
  top: 20px;
}

.sidebar-section {
  background: var(--forum-bg-elevated);
  padding: 20px;
  border-radius: var(--forum-radius-md);
  margin-bottom: 20px;
  box-shadow: var(--forum-shadow-sm);
}

.sidebar-section h3 {
  font-size: 16px;
  margin-bottom: 15px;
  color: var(--forum-text-color);
}

.sidebar-section--warning {
  background: var(--forum-accent-surface);
  border: 1px solid #fde7b2;
}

.subscription-copy {
  color: var(--forum-text-muted);
  line-height: 1.6;
  margin-bottom: 14px;
}
</style>
