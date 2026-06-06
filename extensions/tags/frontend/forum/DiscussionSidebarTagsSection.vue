<template>
  <ul class="index-nav-tag-list">
    <li v-if="tagsIndexPath">
      <router-link :to="tagsIndexPath" class="nav-item" :class="{ active: isTagsPage }">
        <i :class="tagsIndexIcon"></i>
        <span>{{ tagsLinkLabel }}</span>
      </router-link>
    </li>
    <li v-for="tag in primaryTagItems" :key="`tag-${tag.id}`">
      <router-link
        :to="buildTagPath(tag)"
        class="nav-item tag-link"
        :class="{
          active: isSidebarTagActive(tag),
          'tag-link--child': Boolean(tag.parent_id)
        }"
        :style="getSidebarTagStyle(tag)"
        :title="tag.description || undefined"
      >
        <span class="tag-link-icon" :class="{ 'tag-link-icon--placeholder': !tag.icon }" aria-hidden="true">
          <i v-if="tag.icon" :class="tag.icon"></i>
          <span v-else class="tag-icon-box"></span>
        </span>
        <span class="tag-link-label">{{ tag.name }}</span>
      </router-link>
    </li>
    <li v-for="tag in secondaryTagItems" :key="`secondary-${tag.id}`">
      <router-link
        :to="buildTagPath(tag)"
        class="nav-item tag-link"
        :class="{ active: isSidebarTagActive(tag) }"
        :style="getSidebarTagStyle(tag)"
        :title="tag.description || undefined"
      >
        <span class="tag-link-icon" :class="{ 'tag-link-icon--placeholder': !tag.icon }" aria-hidden="true">
          <i v-if="tag.icon" :class="tag.icon"></i>
          <span v-else class="tag-icon-box"></span>
        </span>
        <span class="tag-link-label">{{ tag.name }}</span>
      </router-link>
    </li>
    <li v-if="showMoreTagsLink && tagsIndexPath">
      <router-link :to="tagsIndexPath" class="nav-item nav-item--muted">
        <i class="fas fa-ellipsis-h"></i>
        <span>{{ moreTagsLinkLabel }}</span>
      </router-link>
    </li>
  </ul>
</template>

<script setup>
import {
  computed,
  getUiCopy,
} from '@bias/forum'
import { buildTagPath } from './tagUtils.js'
import {
  buildDiscussionListPrimaryTagItems,
  buildDiscussionListSecondaryTagItems,
  findDiscussionListSidebarContextParent,
  isDiscussionSidebarTagActive,
} from './discussionListNavigation.js'

const props = defineProps({
  currentTag: { type: Object, default: null },
  currentTagSlug: { type: String, default: '' },
  flatTags: { type: Array, default: () => [] },
  isTagsPage: { type: Boolean, default: false },
  normalizedTags: { type: Array, default: () => [] },
  tagsIndexIcon: { type: String, default: 'fas fa-tags' },
  tagsIndexPath: { type: [String, Object], default: '/tags' },
})

const contextParent = computed(() => findDiscussionListSidebarContextParent(props.currentTagSlug, props.normalizedTags))
const primaryTagItems = computed(() => buildDiscussionListPrimaryTagItems(props.flatTags, contextParent.value))
const secondaryTagItems = computed(() => buildDiscussionListSecondaryTagItems(props.flatTags))
const showMoreTagsLink = computed(() => secondaryTagItems.value.length > 0)
const tagsLinkLabel = computed(() => getUiCopy({
  surface: 'discussion-list-sidebar-tags-link',
})?.text || '标签')
const moreTagsLinkLabel = computed(() => getUiCopy({
  surface: 'discussion-list-sidebar-more-tags-link',
})?.text || '更多标签')

function getSidebarTagStyle(tag) {
  return {
    '--tag-color': tag.color || '#6c7a89'
  }
}

function isSidebarTagActive(tag) {
  return isDiscussionSidebarTagActive({
    currentTag: props.currentTag,
    currentTagSlug: props.currentTagSlug,
    normalizedTags: props.normalizedTags,
    tag,
  })
}

</script>

<style scoped>
.index-nav-tag-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.index-nav-tag-list li {
  margin-bottom: 10px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0;
  color: #75808c;
  text-decoration: none;
  transition: color 0.15s ease;
  font-size: 13px;
  font-weight: normal;
  cursor: pointer;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
  border-radius: 3px;
  margin-bottom: 0;
  line-height: 20px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  user-select: none;
  box-shadow: none;
  min-height: 18px;
}

.nav-item:hover {
  background: none;
  color: var(--forum-primary-color);
  text-decoration: none;
}

.nav-item.active {
  background: none;
  color: inherit;
  font-weight: 700;
}

.nav-item i {
  width: 16px;
  text-align: center;
  font-size: 14px;
}

.nav-item--muted {
  color: #8a95a1;
}

.nav-item--muted:hover {
  color: var(--forum-primary-color);
}

.tag-link {
  --tag-color: #6c7a89;
  color: #75808c;
}

.tag-link:hover,
.tag-link.active {
  color: var(--tag-color);
}

.tag-link-icon {
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--tag-color);
  font-size: 14px;
}

.tag-link-icon--placeholder {
  color: transparent;
}

.tag-icon-box {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  background: var(--tag-color);
}

.tag-link-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tag-link--child {
  margin-left: 0;
}
</style>
