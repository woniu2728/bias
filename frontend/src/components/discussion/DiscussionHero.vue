<template>
  <div class="discussion-header" :style="discussionHeaderStyle">
    <div class="discussion-badges">
      <span v-if="discussion.is_sticky" class="badge badge-pinned">置顶</span>
      <span v-if="discussion.is_locked" class="badge badge-locked">锁定</span>
      <span v-if="discussion.is_hidden" class="badge badge-hidden">隐藏</span>
      <span v-if="discussion.approval_status === 'pending'" class="badge badge-pending">待审核</span>
    </div>
    <h1>{{ discussion.title }}</h1>
    <div v-if="discussion.tags && discussion.tags.length" class="discussion-tags">
      <router-link
        v-for="tag in discussion.tags"
        :key="tag.id"
        class="tag"
        :to="buildTagPath(tag)"
        :style="{ backgroundColor: tag.color }"
      >
        {{ tag.name }}
      </router-link>
    </div>
    <div
      v-if="discussion.approval_status === 'pending' || discussion.approval_status === 'rejected'"
      class="discussion-review-banner"
      :class="{ 'discussion-review-banner--rejected': discussion.approval_status === 'rejected' }"
    >
      <strong>{{ discussion.approval_status === 'pending' ? '讨论正在审核中' : '讨论审核未通过' }}</strong>
      <p>
        {{ discussion.approval_status === 'pending'
          ? '这条讨论当前仅你和管理员可见，审核通过后才会出现在论坛列表中。'
          : (discussion.approval_note || '管理员拒绝了这条讨论，请根据反馈调整后重新发布。') }}
      </p>
      <div v-if="canModeratePendingDiscussion" class="review-action-row">
        <button type="button" class="review-action review-action--approve" @click="$emit('moderate-discussion', 'approve')">
          审核通过
        </button>
        <button type="button" class="review-action review-action--reject" @click="$emit('moderate-discussion', 'reject')">
          拒绝讨论
        </button>
      </div>
      <div v-else-if="discussion.approval_status === 'rejected' && canEditDiscussion" class="review-action-row">
        <button type="button" class="review-action review-action--approve" @click="$emit('edit-discussion')">
          修改后重新提交
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  discussion: {
    type: Object,
    required: true
  },
  discussionHeaderStyle: {
    type: Object,
    default: () => ({})
  },
  canModeratePendingDiscussion: {
    type: Boolean,
    default: false
  },
  canEditDiscussion: {
    type: Boolean,
    default: false
  },
  buildTagPath: {
    type: Function,
    required: true
  }
})

defineEmits(['moderate-discussion', 'edit-discussion'])
</script>

<style scoped>
.discussion-header {
  margin-bottom: var(--forum-space-7);
  padding-bottom: var(--forum-space-5);
  border-bottom: 2px solid var(--forum-border-soft);
}

.discussion-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 15px;
}

.badge {
  padding: var(--forum-space-1) var(--forum-space-3);
  border-radius: var(--forum-radius-sm);
  font-size: var(--forum-font-size-xs);
  font-weight: 600;
}

.badge-pinned {
  background: var(--forum-warning-color);
  color: var(--forum-text-inverse);
}

.badge-locked {
  background: var(--forum-text-soft);
  color: var(--forum-text-inverse);
}

.badge-hidden {
  background: var(--forum-danger-color);
  color: var(--forum-text-inverse);
}

.badge-pending {
  background: var(--forum-warning-bg-strong);
  color: var(--forum-warning-color);
}

.discussion-header h1 {
  font-size: var(--forum-font-size-3xl);
  color: var(--forum-text-color);
  margin-bottom: 15px;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.discussion-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.discussion-review-banner {
  margin-top: 16px;
  padding: 14px 16px;
  border: 1px solid var(--forum-warning-border-strong);
  border-radius: var(--forum-radius-md);
  background: var(--forum-warning-bg);
  color: var(--forum-warning-color);
}

.discussion-review-banner strong {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
}

.discussion-review-banner p {
  margin: 0;
  line-height: 1.7;
  font-size: 13px;
}

.review-action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

.review-action {
  border: 0;
  border-radius: var(--forum-radius-pill);
  min-height: 34px;
  padding: 0 14px;
  font-size: var(--forum-font-size-sm);
  font-weight: 700;
  cursor: pointer;
}

.review-action--approve {
  background: var(--forum-success-color);
  color: var(--forum-text-inverse);
}

.review-action--reject {
  background: var(--forum-bg-elevated);
  color: var(--forum-danger-color);
  box-shadow: inset 0 0 0 1px rgba(154, 75, 75, 0.22);
}

.discussion-review-banner--rejected {
  border-color: var(--forum-danger-border);
  background: var(--forum-danger-bg);
  color: var(--forum-danger-color);
}

.tag {
  display: inline-flex;
  min-width: 0;
  max-width: 220px;
  padding: var(--forum-space-1) var(--forum-space-3);
  border-radius: var(--forum-radius-sm);
  color: var(--forum-text-inverse);
  font-size: var(--forum-font-size-sm);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag:hover {
  text-decoration: none;
  filter: brightness(0.96);
}

@media (max-width: 768px) {
  .discussion-header {
    margin: 0 0 14px;
    padding: 18px 18px 22px;
    border-bottom: 0;
    background: linear-gradient(180deg, var(--discussion-hero-color) 0%, var(--discussion-hero-color-dark) 100%);
    text-align: center;
  }

  .discussion-badges,
  .discussion-tags {
    flex-wrap: wrap;
    justify-content: center;
  }

  .discussion-badges {
    margin-bottom: 12px;
  }

  .discussion-header h1 {
    font-size: 24px;
    line-height: 1.24;
    margin-bottom: 10px;
    color: var(--discussion-hero-contrast);
  }

  .tag {
    max-width: min(78vw, 260px);
    padding: 5px 12px;
    font-size: 12px;
    background: rgba(255, 255, 255, 0.96) !important;
    color: var(--discussion-hero-color-dark);
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18);
  }

  .discussion-badges .badge {
    background: rgba(255, 255, 255, 0.22);
    color: var(--discussion-hero-contrast);
    border: 1px solid rgba(255, 255, 255, 0.24);
  }
}
</style>
