<template>
  <section
    v-if="hero"
    class="discussion-list-hero"
    :class="hero.className"
    :style="hero.style"
  >
    <div class="discussion-list-hero-inner">
      <div v-if="hero.pill" class="discussion-list-hero-pill">
        <span
          v-if="hero.bulletColor"
          class="discussion-list-hero-bullet"
          :style="{ backgroundColor: hero.bulletColor }"
        ></span>
        <i v-else-if="hero.icon" :class="hero.icon"></i>
        {{ hero.pill }}
      </div>
      <h1>{{ hero.title }}</h1>
      <p v-if="hero.description">{{ hero.description }}</p>
    </div>
  </section>
</template>

<script setup>

import { toRef } from '@bias/core'
import { useDiscussionListHeroState } from '../useDiscussionListHeroState'

const props = defineProps({
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
  }
})

const {
  hero,
} = useDiscussionListHeroState({
  contextSubject: toRef(props, 'contextSubject'),
  discussionListContexts: toRef(props, 'discussionListContexts'),
  isFollowingPage: toRef(props, 'isFollowingPage'),
  listFilter: toRef(props, 'listFilter'),
})
</script>

<style scoped>
.discussion-list-hero-bullet {
  width: 12px;
  height: 12px;
  display: inline-block;
  border-radius: 999px;
  flex-shrink: 0;
  background: var(--discussion-list-hero-color);
}

.discussion-list-hero {
  --discussion-list-hero-color: var(--forum-primary-color);
  background: linear-gradient(135deg, color-mix(in srgb, var(--discussion-list-hero-color) 20%, white), #f8fbfd);
  border-bottom: 1px solid var(--forum-border-color);
}

.discussion-list-hero-inner {
  padding: 28px 26px;
}

.discussion-list-hero-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: #44515e;
  margin-bottom: 12px;
}

.discussion-list-hero h1 {
  font-size: 30px;
  font-weight: 300;
  color: #2f3c4d;
  margin-bottom: 8px;
}

.discussion-list-hero p {
  color: #61707f;
}

@media (max-width: 768px) {
  .discussion-list-hero-inner {
    padding: 18px 15px;
  }

  .discussion-list-hero h1 {
    font-size: 24px;
    line-height: 1.2;
    margin-bottom: 6px;
  }

  .discussion-list-hero p {
    font-size: 13px;
    line-height: 1.6;
  }
}
</style>
