<template>
  <DiscussionListHero :current-tag="currentTag" :is-following-page="isFollowingPage" />
  <DiscussionListToolbar
    :auth-store="authStore"
    :sort-by="sortBy"
    :sort-options="sortOptions"
    :list-filter="listFilter"
    :filter-options="filterOptions"
    :search-query="searchQuery"
    :marking-all-read="markingAllRead"
    :refreshing="refreshing"
    @change-sort="$emit('change-sort', $event)"
    @change-filter="$emit('change-filter', $event)"
    @change-search="$emit('change-search', $event)"
    @mark-all-read="$emit('mark-all-read')"
    @refresh="$emit('refresh')"
  />
</template>

<script setup>
import DiscussionListHero from '@/components/discussion/DiscussionListHero.vue'
import DiscussionListToolbar from '@/components/discussion/DiscussionListToolbar.vue'

defineProps({
  authStore: {
    type: Object,
    required: true
  },
  currentTag: {
    type: Object,
    default: null
  },
  isFollowingPage: {
    type: Boolean,
    default: false
  },
  sortBy: {
    type: String,
    default: 'latest'
  },
  sortOptions: {
    type: Array,
    default: () => []
  },
  listFilter: {
    type: String,
    default: 'all'
  },
  filterOptions: {
    type: Array,
    default: () => []
  },
  searchQuery: {
    type: String,
    default: ''
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

defineEmits(['change-sort', 'change-filter', 'change-search', 'mark-all-read', 'refresh'])
</script>
