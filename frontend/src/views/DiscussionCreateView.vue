<template>
  <div class="discussion-create-redirect">
    <div class="redirect-card">
      <div class="redirect-spinner"></div>
      <h1>正在打开讨论编辑器...</h1>
      <p>Bias 已切换为 Flarum 风格的浮层 composer。</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const composerStore = useComposerStore()

onMounted(() => {
  if (!authStore.isAuthenticated) {
    router.replace('/login')
    return
  }

  if (authStore.canStartDiscussion) {
    composerStore.openDiscussionComposer({
      tagId: typeof route.query.tag === 'string' ? route.query.tag : '',
      source: 'route'
    })
  }

  router.replace(typeof route.query.returnTo === 'string' ? route.query.returnTo : '/')
})
</script>

<style scoped>
.discussion-create-redirect {
  min-height: calc(100vh - 200px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  background: #f5f8fa;
}

.redirect-card {
  width: min(420px, 100%);
  padding: 32px 28px;
  border-radius: 12px;
  background: white;
  border: 1px solid #dbe2ea;
  text-align: center;
  box-shadow: 0 18px 38px rgba(31, 45, 61, 0.08);
}

.redirect-card h1 {
  margin: 0 0 10px;
  font-size: 24px;
  font-weight: 400;
  color: #2f3c4d;
}

.redirect-card p {
  margin: 0;
  color: #6a7988;
}

.redirect-spinner {
  width: 28px;
  height: 28px;
  margin: 0 auto 16px;
  border-radius: 50%;
  border: 3px solid #dbe2ea;
  border-top-color: var(--forum-primary-color);
  animation: spin 0.9s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
