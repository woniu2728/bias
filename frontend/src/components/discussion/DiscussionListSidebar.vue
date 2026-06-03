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

      <template v-if="hasSidebarTagNavigation">
        <div class="nav-separator"></div>

        <ul class="index-nav-tag-list">
          <li v-if="tagsIndexPath">
            <DiscussionListSidebarNavLink
              :to="tagsIndexPath"
              :icon="tagsIndexIcon"
              :label="tagsLinkLabel"
              :active="isTagsPage"
            />
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
          <li v-if="showMoreTagsLink && tagsIndexPath">
            <DiscussionListSidebarNavLink
              :to="tagsIndexPath"
              icon="fas fa-ellipsis-h"
              :label="moreTagsLinkLabel"
              class="nav-item--muted"
            />
          </li>
        </ul>
      </template>
    </nav>
  </aside>
</template>

<script setup>
import { computed, toRef } from 'vue'
import DiscussionListSidebarNavLink from '@/components/discussion/DiscussionListSidebarNavLink.vue'
import DiscussionListSidebarStartButton from '@/components/discussion/DiscussionListSidebarStartButton.vue'
import DiscussionListSidebarTagLink from '@/components/discussion/DiscussionListSidebarTagLink.vue'
import { useDiscussionListSidebarState } from '@/composables/useDiscussionListSidebarState'
import { getForumNavItems } from '@/forum/registry'

const props = defineProps({
  authStore: {
    type: Object,
    required: true
  },
  currentTag: {
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

const {
  moreTagsLinkLabel,
  profileLinkLabel,
  showProfileLink,
  showStartDiscussionButton,
  tagsLinkLabel,
} = useDiscussionListSidebarState({
  authStore: toRef(props, 'authStore'),
})
const tagsNavItem = computed(() => getForumNavItems({
  authStore: props.authStore,
  surface: 'discussion-sidebar',
}).find(item => item.key === 'tags') || null)
const tagsIndexPath = computed(() => tagsNavItem.value?.to || '')
const tagsIndexIcon = computed(() => tagsNavItem.value?.icon || 'fas fa-th-large')

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

.index-nav-base-list,
.index-nav-tag-list {
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
