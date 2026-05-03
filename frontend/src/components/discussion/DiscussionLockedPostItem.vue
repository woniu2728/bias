<template>
  <article
    :id="`post-${post.number}`"
    class="event-post-item"
    :class="{ 'is-target': isTarget }"
  >
    <div class="event-post-card" :class="{ 'event-post-card--locked': isLocked }">
      <div class="event-post-icon" aria-hidden="true">
        <i :class="isLocked ? 'fas fa-lock' : 'fas fa-lock-open'"></i>
      </div>
      <div class="event-post-content">
        <div class="event-post-line">
          <strong>{{ actorName }}</strong>
          <span>{{ isLocked ? '锁定了该讨论' : '解锁了该讨论' }}</span>
        </div>
        <div class="event-post-meta">
          <button
            type="button"
            class="event-post-number"
            :title="`跳转到第 ${post.number} 楼`"
            @click="$emit('jump-to-post', post.number)"
          >
            #{{ post.number }}
          </button>
          <time :datetime="post.created_at" :title="formatAbsoluteDate(post.created_at)">
            {{ formatDate(post.created_at) }}
          </time>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  post: { type: Object, required: true },
  isTarget: { type: Boolean, default: false },
  getUserDisplayName: { type: Function, required: true },
  formatAbsoluteDate: { type: Function, required: true },
  formatDate: { type: Function, required: true }
})

defineEmits(['jump-to-post'])

const actorName = computed(() => props.getUserDisplayName(props.post.user))
const isLocked = computed(() => Boolean(props.post.event_data?.is_locked))
</script>

<style scoped>
.event-post-item {
  padding: 18px 0;
}

.event-post-item.is-target .event-post-card {
  box-shadow: 0 0 0 2px rgba(231, 124, 47, 0.18);
}

.event-post-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-left: 72px;
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, #f5f8fc 0%, #fbfdff 100%);
  border: 1px solid rgba(132, 156, 187, 0.24);
}

.event-post-card--locked {
  background: linear-gradient(180deg, #fff7f0 0%, #fffdf9 100%);
  border-color: rgba(204, 145, 96, 0.3);
}

.event-post-icon {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(88, 112, 145, 0.12);
  color: #4b6286;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.event-post-card--locked .event-post-icon {
  background: rgba(199, 130, 53, 0.14);
  color: #9a5f1f;
}

.event-post-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.event-post-line {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  color: var(--forum-text-muted);
  line-height: 1.7;
}

.event-post-line strong {
  color: var(--forum-text-color);
}

.event-post-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
}

.event-post-number {
  border: 0;
  background: transparent;
  color: inherit;
  padding: 0;
  cursor: pointer;
}

.event-post-number:hover {
  color: var(--forum-text-muted);
}

@media (max-width: 768px) {
  .event-post-card {
    margin-left: 0;
  }
}
</style>
