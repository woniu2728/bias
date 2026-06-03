<template>
  <div class="home">
    <div class="bias-container">
      <ForumHeroPanel
        :title="heroBindings.title"
        :description="heroBindings.description"
        :variant="heroBindings.variant"
      />
      <div class="quick-actions">
        <router-link to="/discussions" class="action-btn primary">
          <span class="icon">💬</span>
          <span>{{ actionBindings.browseDiscussionsText }}</span>
        </router-link>
        <button v-if="actionBindings.canStartDiscussion" type="button" class="action-btn" @click="actionEvents.startDiscussion">
          <span class="icon">✏️</span>
          <span>{{ actionBindings.startDiscussionText }}</span>
        </button>
        <router-link v-else to="/register" class="action-btn">
          <span class="icon">👤</span>
          <span>{{ actionBindings.registerAccountText }}</span>
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import ForumHeroPanel from '@/components/forum/ForumHeroPanel.vue'
import { useAuthStore } from '@/stores/auth'
import { useComposerStore } from '@/stores/composer'
import { useHomeViewModel } from '@/composables/useHomeViewModel'

const authStore = useAuthStore()
const composerStore = useComposerStore()
const router = useRouter()
const {
  actionBindings,
  actionEvents,
  heroBindings,
} = useHomeViewModel({
  authStore,
  composerStore,
  router,
})
</script>

<style scoped>
.home {
  min-height: calc(100vh - 200px);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--forum-bg-canvas);
}

.bias-container {
  text-align: center;
  max-width: 600px;
  padding: var(--forum-space-8);
}

.quick-actions {
  display: flex;
  gap: 15px;
  justify-content: center;
  flex-wrap: wrap;
  margin-top: 32px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 15px 30px;
  background: var(--forum-bg-elevated);
  border: 1px solid var(--forum-border-color);
  border-radius: var(--forum-radius-md);
  color: var(--forum-text-color);
  font-size: 16px;
  transition: all 0.2s;
  text-decoration: none;
  box-shadow: var(--forum-shadow-sm);
}

.action-btn:hover {
  border-color: var(--forum-border-strong);
  box-shadow: var(--forum-shadow-md);
  text-decoration: none;
}

.action-btn.primary {
  background: #4d698e;
  color: var(--forum-text-inverse);
  border-color: #4d698e;
}

.action-btn.primary:hover {
  background: var(--forum-primary-strong);
  border-color: var(--forum-primary-strong);
}

.icon {
  font-size: 20px;
}
</style>
