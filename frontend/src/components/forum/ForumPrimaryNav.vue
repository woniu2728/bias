<template>
  <ForumNavList
    :sections="navSections"
    root-class="forum-primary-nav"
    section-title-class="forum-primary-nav__title"
    section-list-class="forum-primary-nav__section"
    item-wrapper-class="forum-primary-nav__itemWrap"
    item-class="forum-primary-nav__item"
    item-description-class="forum-primary-nav__description"
    item-badge-class="forum-primary-nav__badge"
  />
</template>

<script setup>
import { computed } from 'vue'
import ForumNavList from '@/components/forum/ForumNavList.vue'
import { getForumNavSections } from '@/forum/registry'

const props = defineProps({
  activeKey: {
    type: String,
    default: 'home'
  },
  authStore: {
    type: Object,
    required: true
  },
  showNotifications: {
    type: Boolean,
    default: true
  },
  notificationStore: {
    type: Object,
    default: null
  }
})

const navSections = computed(() => getForumNavSections({
  authStore: props.authStore,
  showNotifications: props.showNotifications,
  notificationStore: props.notificationStore,
}).map(section => ({
  ...section,
  items: section.items.map(item => ({
    ...item,
    active: props.activeKey === item.key,
  }))
})))
</script>

<style scoped>
.forum-primary-nav {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.forum-primary-nav__title {
  margin: 0 0 4px;
  padding: 0 12px;
  color: var(--forum-text-soft);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.forum-primary-nav__section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.forum-primary-nav__itemWrap {
  list-style: none;
}

.forum-primary-nav__item {
  padding: 10px 12px;
  border-radius: var(--forum-radius-sm);
  color: var(--forum-text-muted);
  text-decoration: none;
}

.forum-primary-nav__item:hover,
.forum-primary-nav__item.active {
  background: var(--forum-primary-color);
  color: var(--forum-text-inverse);
  text-decoration: none;
}

.forum-primary-nav__description {
  display: block;
  margin-left: 28px;
  margin-top: 2px;
  font-size: 12px;
  color: inherit;
  opacity: 0.78;
}

.forum-primary-nav__badge {
  margin-left: auto;
  background: rgba(231, 124, 47, 0.16);
  color: inherit;
}
</style>
