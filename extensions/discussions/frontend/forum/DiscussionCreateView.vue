<template>
  <div class="discussion-create-redirect">
    <ForumStateBlock class="redirect-card">
      <div class="redirect-spinner"></div>
      <h1>{{ cardBindings.title }}</h1>
      <p>{{ cardBindings.description }}</p>
    </ForumStateBlock>
  </div>
</template>

<script setup>
import {
  useAuthStore } from '@bias/users'
import { useRouter,
  useRoute } from '@bias/core'
import { ForumStateBlock,
  useComposerStore
} from '@bias/forum'
import { useDiscussionCreateViewModel } from './useDiscussionCreateViewModel'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()
const { cardBindings } = useDiscussionCreateViewModel({
  authStore,
  composerStore,
  route,
  router,
})
</script>

<style scoped>
.discussion-create-redirect {
  min-height: calc(100vh - 200px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  background: var(--forum-bg-canvas);
}

.redirect-card {
  width: min(420px, 100%);
  text-align: center;
}

.redirect-card h1 {
  margin: 0 0 10px;
  font-size: 24px;
  font-weight: 400;
  color: var(--forum-text-color);
}

.redirect-card p {
  margin: 0;
  color: var(--forum-text-muted);
}

.redirect-spinner {
  width: 28px;
  height: 28px;
  margin: 0 auto 16px;
  border-radius: 50%;
  border: 3px solid var(--forum-border-color);
  border-top-color: var(--forum-primary-color);
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
