<template>
  <div class="profile-page">
    <ForumStateBlock v-if="loading" class="profile-state-block">{{ loadingStateText }}</ForumStateBlock>
    <ForumStateBlock v-else-if="!user" class="profile-state-block">{{ missingStateText }}</ForumStateBlock>
    <div v-else>
      <ProfileHero
        v-bind="heroBindings"
        @avatar-selected="heroEvents.avatarSelected"
        @open-settings="heroEvents.openSettings"
      />

      <div class="container">
        <div class="user-page-layout">
          <ProfileSidebar
            v-bind="sidebarBindings"
            @change-tab="sidebarEvents.changeTab"
          />

          <main class="user-content">
            <component
              :is="activePanelComponent"
              v-if="activePanelComponent"
              v-bind="activePanelProps"
              v-on="activePanelEvents"
              @update-edit-form="handleEditFormUpdate"
              @update-password-form="handlePasswordFormUpdate"
              @update-preference="handlePreferenceUpdate"
            />
          </main>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  useAuthStore } from '@bias/users'
import { useRouter,
  useRoute,
  useModalStore
} from '@bias/core'
import { ForumStateBlock,
  useForumStore
} from '@bias/forum'
import ProfileHero from './ProfileHero.vue'
import ProfileSidebar from './ProfileSidebar.vue'
import { useProfileViewModel } from './useProfileViewModel'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const forumStore = useForumStore()
const modalStore = useModalStore()
const {
  activePanelComponent,
  activePanelEvents,
  activePanelProps,
  handleEditFormUpdate,
  handlePasswordFormUpdate,
  handlePreferenceUpdate,
  heroBindings,
  heroEvents,
  loading,
  loadingStateText,
  missingStateText,
  sidebarBindings,
  sidebarEvents,
  user,
} = useProfileViewModel({
  authStore,
  forumStore,
  modalStore,
  route,
  router,
})
</script>

<style scoped>
.profile-page {
  background: #f5f8fa;
  min-height: calc(100vh - 56px);
}

.profile-state-block {
  max-width: 1200px;
  margin: 0 auto;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.user-page-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 25px;
  padding: 40px 0 30px 0;
  min-width: 0;
}

.user-content {
  min-width: 0;
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

@media (max-width: 768px) {
  .container {
    padding: 0 14px;
  }

  .user-page-layout {
    grid-template-columns: 1fr;
    gap: 14px;
    padding: 28px 0 22px;
  }
}
</style>
