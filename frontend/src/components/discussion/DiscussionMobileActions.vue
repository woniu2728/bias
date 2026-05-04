<template>
  <div ref="rootEl" class="discussion-mobile-nav discussion-actions-scope" :class="{ 'is-open': showDiscussionMenu }">
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
import { ref } from 'vue'
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
  togglingSubscription: {
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
  menuItems: {
    type: Array,
    default: () => []
  }
})

defineEmits(['menu-action'])

const rootEl = ref(null)

function getRootEl() {
  return rootEl.value
}

defineExpose({
  getRootEl
})
</script>

<style scoped>
.discussion-mobile-nav {
  display: none;
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

@media (max-width: 768px) {
  .discussion-mobile-nav {
    display: block;
    margin: 0 15px;
  }

  .discussion-actions-menu--mobile {
    position: relative;
    left: auto;
    right: auto;
    top: auto;
    margin-top: 0;
  }
}
</style>
