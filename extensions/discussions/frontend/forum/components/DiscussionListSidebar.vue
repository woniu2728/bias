<template>
  <aside class="index-nav">
    <div class="index-nav-header">
      <DiscussionListSidebarStartButton
        v-if="showStartDiscussionButton"
        :context-subject="contextSubject"
        :start-discussion-button-style="startDiscussionButtonStyle"
        @click="$emit('start-discussion')"
      />
      <div v-else class="index-nav-header-spacer" aria-hidden="true"></div>
    </div>

    <nav class="index-nav-list">
      <ul class="index-nav-base-list">
        <li v-for="item in sidebarFilterItems" :key="item.code">
          <DiscussionListSidebarNavLink
            :to="item.to"
            :icon="item.icon"
            :label="item.label"
            :active="item.active"
          />
        </li>
        <li v-if="showProfileLink">
          <DiscussionListSidebarNavLink
            :to="buildUserPath(authStore.user)"
            icon="fas fa-user"
            :label="profileLinkLabel"
            :active="isOwnProfilePage"
          />
        </li>
      </ul>

      <template v-for="section in sidebarExtensionSections" :key="section.key">
        <div class="nav-separator"></div>
        <component
          :is="section.component"
          v-if="section.component"
          v-bind="section.componentProps"
        />
      </template>
    </nav>
  </aside>
</template>

<script setup>

import { toRef } from '@bias/core'
import DiscussionListSidebarNavLink from './DiscussionListSidebarNavLink.vue'
import DiscussionListSidebarStartButton from './DiscussionListSidebarStartButton.vue'
import { useDiscussionListSidebarState } from '../useDiscussionListSidebarState'

const props = defineProps({
  authStore: {
    type: Object,
    required: true
  },
  contextSubject: {
    type: Object,
    default: null
  },
  isOwnProfilePage: {
    type: Boolean,
    default: false
  },
  sidebarFilterItems: {
    type: Array,
    default: () => []
  },
  isTagsPage: {
    type: Boolean,
    default: false
  },
  sidebarExtensionSections: {
    type: Array,
    default: () => []
  },
  startDiscussionButtonStyle: {
    type: Object,
    default: () => ({})
  },
  buildUserPath: {
    type: Function,
    required: true
  },
})

const {
  profileLinkLabel,
  showProfileLink,
  showStartDiscussionButton,
} = useDiscussionListSidebarState({
  authStore: toRef(props, 'authStore'),
})

defineEmits(['start-discussion'])
</script>

<style scoped>
.index-nav {
  width: 240px;
  background: var(--forum-bg-elevated);
  border-right: 1px solid var(--forum-border-color);
  min-height: calc(100vh - 56px);
  position: sticky;
  top: 56px;
  align-self: flex-start;
}

.index-nav-header {
  padding: 18px 18px 12px;
}

.index-nav-header-spacer {
  min-height: 44px;
}

.index-nav-list {
  padding: 0 18px 24px;
}

.index-nav-base-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.index-nav-list li {
  margin-bottom: 10px;
}

.nav-separator {
  height: 1px;
  margin: 16px 0 14px;
  background: #e5ebf1;
}

@media (max-width: 768px) {
  .index-nav {
    display: none;
  }
}
</style>
