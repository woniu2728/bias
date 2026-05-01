<template>
  <DiscussionListHero :current-tag="currentTag" :is-following-page="isFollowingPage" />
  <DiscussionListToolbar
    :auth-store="authStore"
    :sort-by="sortBy"
    :marking-all-read="markingAllRead"
    :refreshing="refreshing"
    @change-sort="$emit('change-sort', $event)"
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
