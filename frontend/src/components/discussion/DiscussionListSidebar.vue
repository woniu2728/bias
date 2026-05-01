<template>
  <aside class="index-nav">
    <div class="index-nav-header">
      <DiscussionListSidebarStartButton
        v-if="showStartDiscussionButton"
        :current-tag="currentTag"
        :start-discussion-button-style="startDiscussionButtonStyle"
        @click="$emit('start-discussion')"
      />
      <div v-else class="index-nav-header-spacer" aria-hidden="true"></div>
    </div>

    <nav class="index-nav-list">
      <ul>
        <li>
          <DiscussionListSidebarNavLink to="/" icon="far fa-comments" label="全部讨论" :active="isAllDiscussionsPage" />
        </li>
        <li v-if="authStore.user">
          <DiscussionListSidebarNavLink to="/following" icon="fas fa-bell" label="关注中" :active="isFollowingPage" />
        </li>
        <li v-if="authStore.user">
          <DiscussionListSidebarNavLink
            :to="buildUserPath(authStore.user)"
            icon="fas fa-user"
            label="我的主页"
            :active="isOwnProfilePage"
          />
        </li>
        <li v-if="hasSidebarTagNavigation" class="nav-separator" aria-hidden="true"></li>
        <li v-if="hasSidebarTagNavigation">
          <DiscussionListSidebarNavLink to="/tags" icon="fas fa-th-large" label="标签" :active="isTagsPage" />
        </li>
        <li v-for="tag in sidebarPrimaryTagItems" :key="`tag-${tag.id}`">
          <DiscussionListSidebarTagLink
            :tag="tag"
            :build-tag-path="buildTagPath"
            :get-sidebar-tag-style="getSidebarTagStyle"
            :is-active="isSidebarTagActive(tag)"
            :is-child="Boolean(tag.parent_id)"
          />
        </li>
        <li v-for="tag in sidebarSecondaryTagItems" :key="`secondary-${tag.id}`">
          <DiscussionListSidebarTagLink
            :tag="tag"
            :build-tag-path="buildTagPath"
            :get-sidebar-tag-style="getSidebarTagStyle"
            :is-active="isSidebarTagActive(tag)"
          />
        </li>
        <li v-if="showMoreTagsLink">
          <DiscussionListSidebarNavLink to="/tags" icon="fas fa-ellipsis-h" label="更多标签" class="nav-item--muted" />
        </li>
      </ul>
    </nav>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import DiscussionListSidebarNavLink from '@/components/discussion/DiscussionListSidebarNavLink.vue'
import DiscussionListSidebarStartButton from '@/components/discussion/DiscussionListSidebarStartButton.vue'
import DiscussionListSidebarTagLink from '@/components/discussion/DiscussionListSidebarTagLink.vue'

const props = defineProps({
  authStore: {
    type: Object,
    required: true
  },
  currentTag: {
    type: Object,
    default: null
  },
  isAllDiscussionsPage: {
    type: Boolean,
    default: false
  },
  isFollowingPage: {
    type: Boolean,
    default: false
  },
  isOwnProfilePage: {
    type: Boolean,
    default: false
  },
  isTagsPage: {
    type: Boolean,
    default: false
  },
  hasSidebarTagNavigation: {
    type: Boolean,
    default: false
  },
  sidebarPrimaryTagItems: {
    type: Array,
    default: () => []
  },
  sidebarSecondaryTagItems: {
    type: Array,
    default: () => []
  },
  showMoreTagsLink: {
    type: Boolean,
    default: false
  },
  startDiscussionButtonStyle: {
    type: Object,
    default: () => ({})
  },
  buildUserPath: {
    type: Function,
    required: true
  },
  buildTagPath: {
    type: Function,
    required: true
  },
  isSidebarTagActive: {
    type: Function,
    required: true
  },
  getSidebarTagStyle: {
    type: Function,
    required: true
  }
})
const showStartDiscussionButton = computed(() => {
  if (props.authStore.isRestoringSession && props.authStore.isAuthenticated && !props.authStore.user) {
    return false
  }

  return !props.authStore.isAuthenticated || props.authStore.canStartDiscussion
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

.index-nav-list ul {
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

.nav-item--muted {
  color: #8a95a1;
}

.nav-item--muted:hover {
  color: var(--forum-primary-color);
}

@media (max-width: 768px) {
  .index-nav {
    display: none;
  }
}
</style>
