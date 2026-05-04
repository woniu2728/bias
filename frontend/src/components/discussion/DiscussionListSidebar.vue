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
      <ForumNavList
        :sections="baseNavSections"
        root-class="index-nav-sections"
        section-title-class="index-nav-title"
        section-list-class="index-nav-base-list"
        item-wrapper-class="index-nav-item-wrap"
        item-class="index-nav-base-link"
        item-description-class="index-nav-description"
        item-badge-class="index-nav-badge"
      />

      <ul v-if="hasSidebarTagNavigation" class="index-nav-tag-list">
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
import ForumNavList from '@/components/forum/ForumNavList.vue'
import { getForumNavSections } from '@/forum/registry'
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

const baseNavSections = computed(() => getForumNavSections({
  authStore: props.authStore,
  showNotifications: false,
  notificationStore: null,
}).map(section => ({
  ...section,
  title: section.key === 'primary' ? '' : section.title,
  items: section.items
    .filter(item => item.key !== 'notifications')
    .map(item => ({
      ...item,
      active: (
        (item.key === 'home' && props.isAllDiscussionsPage)
        || (item.key === 'following' && props.isFollowingPage)
        || (item.key === 'profile' && props.isOwnProfilePage)
      ),
    }))
})).filter(section => section.items.length > 0))

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

.index-nav-sections {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.index-nav-base-list,
.index-nav-tag-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.index-nav-list li {
  margin-bottom: 10px;
}

.index-nav-base-link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: var(--forum-radius-sm);
  color: var(--forum-text-muted);
  text-decoration: none;
}

.index-nav-base-link:hover,
.index-nav-base-link.active {
  background: var(--forum-primary-color);
  color: var(--forum-text-inverse);
  text-decoration: none;
}

.index-nav-description {
  display: block;
  margin-left: 28px;
  margin-top: 2px;
  font-size: 12px;
  color: inherit;
  opacity: 0.78;
}

.index-nav-badge {
  margin-left: auto;
  background: rgba(255, 255, 255, 0.18);
  color: inherit;
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
