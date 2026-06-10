<template>
  <div class="discussion-list-item-stats">
    <span class="discussion-list-item-count" :class="{ 'discussion-list-item-count--unread': isUnread }">
      <i class="far fa-comment"></i>
      <span>{{ discussion.comment_count }}</span>
    </span>
  </div>
</template>

<script setup>
defineProps({
  discussion: {
    type: Object,
    required: true
  },
  isUnread: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.discussion-list-item-stats {
  width: 40px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.discussion-list-item-count {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--forum-text-soft);
  font-size: 14px;
  text-decoration: none;
}

.discussion-list-item-count:hover {
  color: var(--forum-text-color);
  text-decoration: none;
}

@media (max-width: 768px) {
  .discussion-list-item-stats {
    width: auto;
    position: absolute;
    top: 12px;
    right: 15px;
  }

  .discussion-list-item-count {
    min-width: 34px;
    justify-content: center;
    padding: 3px 8px;
    gap: 0;
    border-radius: 999px;
    background: #edf2f6;
    color: #647384;
    font-size: 12px;
    font-weight: 700;
  }

  .discussion-list-item-count i {
    display: none;
  }

  .discussion-list-item-count--unread {
    background: var(--forum-primary-color);
    color: #fff;
  }
}
</style>
