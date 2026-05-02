<template>
  <article
    :id="`post-${post.number}`"
    class="post-item"
    :class="{ 'is-hidden': post.is_hidden, 'is-target': isTarget }"
  >
    <div class="post-container">
      <aside class="post-side">
        <router-link :to="buildUserPath(post.user)" class="post-avatar-link" :title="getUserDisplayName(post.user)">
          <div
            v-if="!post.user.avatar_url"
            class="post-avatar avatar-placeholder"
            :style="{ backgroundColor: getUserAvatarColor(post.user) }"
          >
            {{ getUserInitial(post.user) }}
          </div>
          <img
            v-else
            class="post-avatar"
            :src="post.user.avatar_url"
            :alt="getUserDisplayName(post.user)"
          />
          <span
            v-if="getUserPrimaryGroupIcon(post.user)"
            class="post-avatar-badge"
            :style="{ backgroundColor: getUserPrimaryGroupColor(post.user) }"
            :title="getUserPrimaryGroupLabel(post.user)"
          >
            <i :class="getUserPrimaryGroupIcon(post.user)"></i>
          </span>
        </router-link>
      </aside>

      <div class="post-main">
        <header class="post-header">
          <div class="post-header-main">
            <router-link :to="buildUserPath(post.user)" class="post-author">{{ getUserDisplayName(post.user) }}</router-link>
            <button
              type="button"
              class="post-meta-link post-number"
              :title="`跳转到第 ${post.number} 楼`"
              @click="$emit('jump-to-post', post.number)"
            >
              #{{ post.number }}
            </button>
            <time class="post-time" :datetime="post.created_at" :title="formatAbsoluteDate(post.created_at)">
              {{ formatDate(post.created_at) }}
            </time>
            <span v-if="post.edited_at" class="post-edited" :title="formatAbsoluteDate(post.edited_at)">已编辑</span>
            <span v-if="post.approval_status === 'pending'" class="post-status">待审核</span>
            <span v-else-if="post.approval_status === 'rejected'" class="post-status post-status--rejected">已拒绝</span>
            <span v-if="post.viewer_has_open_flag && !post.can_moderate_flags" class="post-status post-status--info">已举报</span>
            <span v-if="post.open_flag_count > 0 && post.can_moderate_flags" class="post-status post-status--warning">
              {{ post.open_flag_count }} 条举报待处理
            </span>
          </div>

        </header>

        <div class="post-body" v-html="post.content_html"></div>
        <aside class="post-actions" :class="{ 'is-open': isPostMenuOpen }">
          <button
            v-if="canLikePost(post)"
            type="button"
            class="post-action"
            :class="{ 'is-active': post.is_liked }"
            :disabled="likePending"
            @click="$emit('toggle-like', post)"
          >
            <i class="fas fa-thumbs-up"></i>
            <span>赞</span>
          </button>
          <button
            v-if="authStore.isAuthenticated && !discussion.is_locked && !isSuspended"
            type="button"
            class="post-action"
            @click="$emit('reply-to-post', post)"
          >
            <i class="fas fa-reply"></i>
            <span>回复</span>
          </button>
          <div v-if="hasPostControls(post)" class="post-controls" :class="{ 'is-open': isPostMenuOpen }">
            <button
              type="button"
              class="post-action post-action--icon"
              :aria-expanded="isPostMenuOpen"
              @click.stop="$emit('toggle-post-menu', post.id)"
            >
              <i class="fas fa-ellipsis-h"></i>
            </button>
            <div v-if="isPostMenuOpen" class="post-controls-menu">
              <button v-if="canEditPost(post)" type="button" @click="handleMenuAction('edit-post', post)">
                编辑
              </button>
              <button v-if="canDeletePost(post)" type="button" class="is-danger" @click="handleMenuAction('delete-post', post)">
                删除
              </button>
              <button v-if="canReportPost(post)" type="button" @click="handleMenuAction('open-report-modal', post)">
                举报
              </button>
            </div>
          </div>
        </aside>
        <div
          v-if="post.approval_status === 'pending' || post.approval_status === 'rejected'"
          class="post-review-banner"
          :class="{ 'post-review-banner--rejected': post.approval_status === 'rejected' }"
        >
          {{ post.approval_status === 'pending'
            ? '这条回复正在审核中，目前仅你和管理员可见。'
            : (post.approval_note || '这条回复未通过审核，请根据管理员反馈调整内容。') }}
          <div v-if="canModeratePendingPost(post)" class="review-action-row">
            <button type="button" class="review-action review-action--approve" @click="$emit('moderate-post', { post, action: 'approve' })">
              审核通过
            </button>
            <button type="button" class="review-action review-action--reject" @click="$emit('moderate-post', { post, action: 'reject' })">
              拒绝回复
            </button>
          </div>
          <div v-else-if="post.approval_status === 'rejected' && canEditPost(post)" class="review-action-row">
            <button type="button" class="review-action review-action--approve" @click="$emit('edit-post', post)">
              修改后重新提交
            </button>
          </div>
        </div>
        <div v-if="post.can_moderate_flags && post.open_flag_count > 0" class="post-flag-panel">
          <div class="post-flag-panel-header">
            <strong>前台举报处理</strong>
            <span>版主可直接在这里查看原因并关闭举报。</span>
          </div>
          <div class="post-flag-list">
            <article v-for="flag in post.open_flags" :key="flag.id" class="post-flag-item">
              <div class="post-flag-item-header">
                <span class="post-flag-reason">{{ flag.reason }}</span>
                <span class="post-flag-user">{{ flag.user?.display_name || flag.user?.username || '匿名用户' }}</span>
              </div>
              <p>{{ flag.message || '举报人未填写补充说明。' }}</p>
            </article>
          </div>
          <div class="post-flag-actions">
            <button
              type="button"
              class="post-flag-button post-flag-button--primary"
              :disabled="flagPending"
              @click="$emit('resolve-post-flags', { post, status: 'resolved' })"
            >
              {{ flagPending ? '处理中...' : '标记已处理' }}
            </button>
            <button
              type="button"
              class="post-flag-button"
              :disabled="flagPending"
              @click="$emit('resolve-post-flags', { post, status: 'ignored' })"
            >
              忽略举报
            </button>
          </div>
        </div>

        <footer v-if="post.like_count > 0" class="post-footer">
          <button
            v-if="canLikePost(post)"
            type="button"
            class="post-feedback"
            :class="{ 'is-active': post.is_liked }"
            :disabled="likePending"
            @click="$emit('toggle-like', post)"
          >
            <i class="fas fa-thumbs-up"></i>
            <span>{{ formatLikeSummary(post) }}</span>
          </button>
          <div
            v-else
            class="post-feedback"
            :class="{ 'is-active': post.is_liked }"
          >
            <i class="fas fa-thumbs-up"></i>
            <span>{{ formatLikeSummary(post) }}</span>
          </div>
        </footer>
      </div>
    </div>
  </article>
</template>

<script setup>
const props = defineProps({
  post: { type: Object, required: true },
  discussion: { type: Object, required: true },
  authStore: { type: Object, required: true },
  isTarget: { type: Boolean, default: false },
  isSuspended: { type: Boolean, default: false },
  isPostMenuOpen: { type: Boolean, default: false },
  likePending: { type: Boolean, default: false },
  flagPending: { type: Boolean, default: false },
  canLikePost: { type: Function, required: true },
  canEditPost: { type: Function, required: true },
  canDeletePost: { type: Function, required: true },
  canReportPost: { type: Function, required: true },
  canModeratePendingPost: { type: Function, required: true },
  hasPostControls: { type: Function, required: true },
  buildUserPath: { type: Function, required: true },
  getUserDisplayName: { type: Function, required: true },
  getUserAvatarColor: { type: Function, required: true },
  getUserInitial: { type: Function, required: true },
  getUserPrimaryGroupIcon: { type: Function, required: true },
  getUserPrimaryGroupColor: { type: Function, required: true },
  getUserPrimaryGroupLabel: { type: Function, required: true },
  formatAbsoluteDate: { type: Function, required: true },
  formatDate: { type: Function, required: true },
  formatLikeSummary: { type: Function, required: true },
})

const emit = defineEmits([
  'jump-to-post',
  'toggle-like',
  'reply-to-post',
  'toggle-post-menu',
  'edit-post',
  'delete-post',
  'open-report-modal',
  'moderate-post',
  'resolve-post-flags',
  'close-post-menu',
])

function handleMenuAction(eventName, payload) {
  emit(eventName, payload)
  emit('close-post-menu')
}
</script>

<style scoped>
.post-item {
  position: relative;
  padding: 22px 0 24px;
  transition: opacity 0.2s, transform 0.2s;
}

.post-item::after {
  content: '';
  display: block;
  width: calc(100% - 84px);
  height: 1px;
  margin-left: auto;
  background: var(--forum-border-color);
}

.post-item:last-of-type::after {
  display: none;
}

.post-item.is-hidden {
  opacity: 0.52;
}

.post-item.is-target .post-main {
  background: var(--forum-accent-surface);
  box-shadow: 0 0 0 2px rgba(231, 124, 47, 0.18);
  border-radius: var(--forum-radius-md);
  margin: -12px -16px 0 0;
  padding: 12px 16px 16px;
}

.post-container {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 0;
}

.post-side {
  padding-top: 2px;
}

.post-avatar-link {
  display: inline-flex;
  position: relative;
  text-decoration: none;
}

.post-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  object-fit: cover;
  display: block;
}

.avatar-placeholder.post-avatar {
  background: var(--forum-primary-color);
  color: var(--forum-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
}

.post-avatar-badge {
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 22px;
  height: 22px;
  border-radius: var(--forum-radius-pill);
  border: 2px solid var(--forum-bg-elevated);
  box-shadow: 0 10px 18px rgba(17, 33, 52, 0.18);
  color: var(--forum-text-inverse);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.post-avatar-badge i {
  font-size: 10px;
}

.post-main {
  position: relative;
  min-width: 0;
  padding-top: 2px;
}

.post-header {
  margin-bottom: 15px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.post-header-main {
  min-width: 0;
  flex: 1 1 auto;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-md);
}

.post-author {
  color: var(--forum-text-color);
  font-weight: 700;
  font-size: 15px;
  min-width: 0;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.post-author:hover {
  text-decoration: none;
  color: var(--forum-primary-color);
}

.post-meta-link,
.post-time,
.post-edited {
  color: var(--forum-text-soft);
  font-size: var(--forum-font-size-sm);
}

.post-meta-link {
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
}

.post-meta-link:hover,
.post-time:hover {
  color: var(--forum-text-muted);
}

.post-edited {
  cursor: default;
}

.post-status {
  color: var(--forum-warning-color);
  background: var(--forum-warning-bg-strong);
  border-radius: var(--forum-radius-pill);
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 700;
}

.post-status--info {
  color: var(--forum-info-color);
  background: var(--forum-info-bg);
}

.post-status--warning {
  color: #9a5520;
  background: #fff1df;
}

.post-status--rejected {
  color: var(--forum-danger-color);
  background: var(--forum-danger-bg);
}

.post-body {
  position: relative;
  overflow: auto;
  overflow-wrap: break-word;
  word-break: break-word;
  color: var(--forum-text-color);
  font-size: var(--forum-font-size-md);
  line-height: 1.7;
}

.post-body :deep(p),
.post-body :deep(ul),
.post-body :deep(ol),
.post-body :deep(blockquote) {
  margin-bottom: 1em;
}

.post-body :deep(a) {
  border-bottom: 1px solid var(--forum-border-color);
  font-weight: 600;
}

.post-body :deep(a:hover),
.post-body :deep(a:focus),
.post-body :deep(a:active) {
  text-decoration: none;
  border-color: var(--forum-primary-color);
}

.post-body :deep(blockquote) {
  margin: 1em 0;
  border: 0;
  border-top: 2px dotted var(--forum-bg-canvas);
  border-bottom: 2px dotted var(--forum-bg-canvas);
  border-radius: var(--forum-radius-md);
  padding: 8px 15px;
  background: var(--forum-bg-subtle);
  color: var(--forum-text-muted);
}

.post-body :deep(code) {
  font-family: source-code-pro, Monaco, Consolas, 'Courier New', monospace;
  padding: 5px;
  border-radius: var(--forum-radius-sm);
  background: var(--forum-code-bg);
  color: var(--forum-text-muted);
  line-height: 1.3;
  font-size: 90%;
}

.post-body :deep(pre) {
  border: 0;
  padding: 0;
  border-radius: var(--forum-radius-md);
  background: var(--forum-code-bg-dark);
  color: var(--forum-bg-subtle);
  font-size: 90%;
  overflow-wrap: normal;
}

.post-body :deep(pre code) {
  display: block;
  padding: 1em;
  border-radius: 0;
  background: none;
  color: inherit;
  line-height: inherit;
  font-size: 100%;
  overflow-x: auto;
  max-height: max(50vh, 250px);
  word-break: normal;
}

.post-body :deep(h1),
.post-body :deep(h2),
.post-body :deep(h3),
.post-body :deep(h4),
.post-body :deep(h5),
.post-body :deep(h6) {
  margin-top: 1em;
  margin-bottom: 16px;
  font-weight: 700;
}

.post-body :deep(*:first-child) {
  margin-top: 0 !important;
}

.post-body :deep(img),
.post-body :deep(iframe) {
  max-width: 100%;
  height: auto;
}

.post-review-banner {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: var(--forum-radius-md);
  background: var(--forum-warning-bg);
  color: var(--forum-warning-color);
  font-size: 13px;
  line-height: 1.6;
}

.post-review-banner--rejected {
  background: var(--forum-danger-bg);
  color: var(--forum-danger-color);
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

.post-flag-panel {
  margin-top: 16px;
  padding: 14px 16px;
  border: 1px solid var(--forum-warning-border);
  border-radius: 12px;
  background: linear-gradient(180deg, var(--forum-accent-surface), var(--forum-accent-bg));
}

.post-flag-panel-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 12px;
  margin-bottom: 12px;
}

.post-flag-panel-header strong {
  color: #7f4a1f;
  font-size: 13px;
}

.post-flag-panel-header span {
  color: #9a6d46;
  font-size: 12px;
}

.post-flag-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.post-flag-item {
  padding: 10px 12px;
  border-radius: var(--forum-radius-md);
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(205, 170, 137, 0.34);
}

.post-flag-item-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 6px 12px;
  margin-bottom: 6px;
}

.post-flag-reason {
  color: #6f4523;
  font-size: 12px;
  font-weight: 700;
}

.post-flag-user {
  color: #8b6a4e;
  font-size: 12px;
}

.post-flag-item p {
  margin: 0;
  color: #6f5a47;
  font-size: 13px;
  line-height: 1.6;
}

.post-flag-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.post-flag-button {
  border: 0;
  border-radius: var(--forum-radius-pill);
  min-height: 34px;
  padding: 0 14px;
  background: rgba(255, 255, 255, 0.85);
  color: #72563c;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.post-flag-button:hover {
  background: var(--forum-bg-elevated);
}

.post-flag-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.post-flag-button--primary {
  background: var(--forum-accent-color);
  color: var(--forum-text-inverse);
}

.post-flag-button--primary:hover {
  filter: brightness(0.96);
}

.post-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  position: absolute;
  top: -4px;
  right: 0;
  opacity: 0;
  transition: opacity 0.2s;
}

.post-item:hover .post-actions,
.post-item:focus-within .post-actions,
.post-actions.is-open {
  opacity: 1;
}

.post-action {
  border: 0;
  background: transparent;
  color: var(--forum-text-soft);
  padding: 6px 8px;
  border-radius: var(--forum-radius-sm);
  font-size: var(--forum-font-size-sm);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.post-action:hover {
  background: var(--forum-bg-subtle);
  color: var(--forum-text-muted);
}

.post-action:disabled,
.post-feedback:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.post-action.is-active,
.post-feedback.is-active {
  color: var(--forum-accent-color);
}

.post-action--icon {
  padding-left: 7px;
  padding-right: 7px;
}

.post-controls {
  position: relative;
}

.post-controls-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 138px;
  padding: 8px;
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  background: var(--forum-bg-elevated);
  box-shadow: var(--forum-shadow-md);
  z-index: 8;
}

.post-controls-menu button {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--forum-text-muted);
  text-align: left;
  padding: 9px 10px;
  border-radius: var(--forum-radius-sm);
  font-size: var(--forum-font-size-sm);
  cursor: pointer;
}

.post-controls-menu button:hover {
  background: var(--forum-bg-subtle);
}

.post-controls-menu button.is-danger {
  color: var(--forum-danger-color);
}

.post-controls-menu button.is-danger:hover {
  background: var(--forum-danger-soft);
}

.post-footer {
  display: inline-block;
  margin-top: 12px;
  margin-bottom: 2px;
}

.post-feedback {
  border: 0;
  background: transparent;
  color: var(--forum-text-soft);
  padding: 0;
  font-size: var(--forum-font-size-sm);
  display: inline-flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
}

.post-feedback:hover {
  color: var(--forum-text-muted);
}

@media (max-width: 768px) {
  .post-item {
    padding: 16px 0 18px;
  }

  .post-item::after {
    width: 100%;
    margin-left: 0;
  }

  .post-item.is-target .post-main {
    margin: -10px -12px 0;
    padding: 10px 12px 14px;
  }

  .post-container {
    grid-template-columns: 42px minmax(0, 1fr);
    gap: 10px;
  }

  .post-side {
    padding-top: 4px;
  }

  .post-avatar {
    width: 32px;
    height: 32px;
  }

  .avatar-placeholder.post-avatar {
    font-size: 14px;
  }

  .post-avatar-badge {
    width: 16px;
    height: 16px;
    right: -2px;
    bottom: -2px;
    border-width: 1.5px;
  }

  .post-avatar-badge i {
    font-size: 8px;
  }

  .post-header {
    margin-bottom: 12px;
    padding-right: 0;
  }

  .post-header-main {
    gap: 6px 8px;
    font-size: 12px;
  }

  .post-author {
    font-size: 14px;
    max-width: min(58vw, 220px);
  }

  .post-meta-link,
  .post-time,
  .post-edited {
    font-size: 12px;
  }

  .post-status {
    padding: 2px 7px;
    font-size: 10px;
  }

  .post-actions {
    position: relative;
    top: auto;
    right: auto;
    opacity: 1;
    justify-content: flex-end;
    margin-top: 14px;
    gap: 8px;
  }

  .post-action {
    min-width: 44px;
    justify-content: center;
    min-height: 40px;
    padding: 0 12px;
    border-radius: 3px;
    background: transparent;
    border: 1px solid var(--forum-border-color);
    color: var(--forum-text-muted);
  }

  .post-action span {
    display: none;
  }

  .post-action--icon {
    min-width: 40px;
    width: 44px;
    padding-left: 0;
    padding-right: 0;
  }

  .post-controls {
    min-width: 0;
  }

  .post-controls-menu {
    min-width: 150px;
    right: 0;
  }

  .post-body {
    font-size: 13px;
  }

  .post-footer {
    margin-top: 10px;
    margin-bottom: 0;
  }
}
</style>
