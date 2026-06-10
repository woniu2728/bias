<template>
  <DiscussionListHero
    :context-subject="contextSubject"
    :discussion-list-contexts="discussionListContexts"
    :is-following-page="isFollowingPage"
    :list-filter="listFilter"
  />
  <DiscussionListToolbar
    :auth-store="authStore"
    :sort-by="sortBy"
    :sort-options="sortOptions"
    :marking-all-read="markingAllRead"
    :refreshing="refreshing"
    @change-sort="$emit('change-sort', $event)"
    @mark-all-read="$emit('mark-all-read')"
    @refresh="$emit('refresh')"
  />
</template>

<script setup>
import DiscussionListHero from './DiscussionListHero.vue'
import DiscussionListToolbar from './DiscussionListToolbar.vue'

defineProps({
  authStore: {
    type: Object,
    required: true
  },
  contextSubject: {
    type: Object,
    default: null
  },
  discussionListContexts: {
    type: Array,
    default: () => []
  },
  isFollowingPage: {
    type: Boolean,
    default: false
  },
  listFilter: {
    type: String,
    default: 'all'
  },
  sortBy: {
    type: String,
    default: 'latest'
  },
  sortOptions: {
    type: Array,
    default: () => []
  },
  markingAllRead: {
    type: Boolean,
    default: false
  },
  refreshing: {
    type: Boolean,
    default: false
  }
})

defineEmits(['change-sort', 'mark-all-read', 'refresh'])
</script>
