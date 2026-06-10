<template>
  <article class="tag-tile" :style="{ '--tag-color': tag.color }">
    <router-link :to="buildTagPath(tag)" class="tag-main">
      <div class="tag-header">
        <span class="tag-badge" :style="{ backgroundColor: tag.color }"></span>
        <h2>{{ tag.name }}</h2>
      </div>
      <p class="tag-description">
        {{ tag.description || '这个标签还没有填写描述。' }}
      </p>
      <div v-if="tag.children.length" class="tag-children">
        <TagBadge
          v-for="child in tag.children"
          :key="child.id"
          :tag="child"
          :to="buildTagPath(child)"
          variant="soft"
          show-dot
        />
      </div>
    </router-link>

    <router-link
      v-if="tag.last_posted_discussion"
      :to="buildDiscussionPath(tag.last_posted_discussion.id)"
      class="tag-last-discussion"
    >
      <span class="tag-last-title">{{ tag.last_posted_discussion.title }}</span>
      <span class="tag-last-time">{{ formatRelativeTime(tag.last_posted_discussion.last_posted_at) }}</span>
    </router-link>
    <div v-else class="tag-last-discussion tag-last-discussion-empty">
      {{ lastDiscussionEmptyText }}
    </div>
  </article>
</template>

<script setup>
import {
  computed,
  formatRelativeTime } from '@bias/core'
import { getEmptyState
} from '@bias/forum'
import { buildDiscussionPath } from '@bias/discussions'
import TagBadge from './TagBadge.vue'
import { buildTagPath } from './tagUtils.js'

const props = defineProps({
  tag: {
    type: Object,
    required: true,
  },
})

const lastDiscussionEmptyText = computed(() => {
  const emptyState = getEmptyState({
    surface: 'tag-last-discussion-empty',
    tag: props.tag,
  })

  return emptyState?.text || '暂无讨论'
})
</script>

<style scoped>
.tag-tile {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 20px;
  background: var(--forum-bg-elevated);
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  overflow: hidden;
  box-shadow: var(--forum-shadow-sm);
}

.tag-main {
  padding: 22px 24px;
  color: inherit;
}

.tag-main:hover {
  text-decoration: none;
}

.tag-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.tag-badge {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--tag-color) 14%, white);
}

.tag-header h2 {
  font-size: 20px;
  font-weight: 500;
  color: var(--forum-text-color);
}

.tag-description {
  color: var(--forum-text-muted);
  line-height: 1.6;
}

.tag-children {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
}

.tag-last-discussion {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 22px 24px;
  background: var(--forum-bg-elevated-strong);
  border-left: 1px solid var(--forum-border-soft);
}

.tag-last-title {
  color: var(--forum-text-color);
  line-height: 1.5;
}

.tag-last-time,
.tag-last-discussion-empty {
  color: var(--forum-text-soft);
  font-size: 13px;
  margin-top: 8px;
}

@media (max-width: 900px) {
  .tag-tile {
    grid-template-columns: 1fr;
  }

  .tag-last-discussion {
    border-left: none;
    border-top: 1px solid #edf2f6;
  }
}
</style>
