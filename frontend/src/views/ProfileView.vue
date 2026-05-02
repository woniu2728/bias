<template>
  <div class="profile-page">
    <ForumStateBlock v-if="loading" class="profile-state-block">加载中...</ForumStateBlock>
    <ForumStateBlock v-else-if="!user" class="profile-state-block">用户不存在</ForumStateBlock>
    <div v-else>
      <ProfileHero
        :user="user"
        :is-own-profile="isOwnProfile"
        :is-online="isOnline"
        :avatar-uploading="avatarUploading"
        :avatar-input-ref="avatarInput"
        :format-join-date="formatJoinDate"
        :format-last-seen="formatLastSeen"
        :get-user-avatar-color="getUserAvatarColor"
        :get-user-primary-group-icon="getUserPrimaryGroupIcon"
        :get-user-primary-group-color="getUserPrimaryGroupColor"
        :get-user-primary-group-label="getUserPrimaryGroupLabel"
        @avatar-selected="handleAvatarSelected"
        @open-settings="switchTab('settings')"
      />

      <div class="container">
        <div class="user-page-layout">
          <ProfileSidebar
            :active-tab="activeTab"
            :is-own-profile="isOwnProfile"
            :user="user"
            @change-tab="switchTab"
          />

          <main class="user-content">
            <ProfileDiscussionSection
              v-if="activeTab === 'discussions'"
              :discussions="discussions"
              :loading="loadingDiscussions"
              :is-own-profile="isOwnProfile"
              :build-discussion-path="buildDiscussionPath"
              :format-date="formatDate"
            />

            <ProfilePostSection
              v-if="activeTab === 'posts'"
              :posts="posts"
              :loading="loadingPosts"
              :is-own-profile="isOwnProfile"
              :build-discussion-path="buildDiscussionPath"
              :format-date="formatDate"
            />

            <ProfileSettingsSection
              v-if="activeTab === 'settings' && isOwnProfile"
              :user="user"
              :edit-form="editForm"
              :preferences="preferences"
              :saving="saving"
              :settings-success="settingsSuccess"
              :settings-error="settingsError"
              :loading-preferences="loadingPreferences"
              :saving-preferences="savingPreferences"
              :preferences-success="preferencesSuccess"
              :preferences-error="preferencesError"
              @save-profile="saveProfile"
              @save-preferences="savePreferences"
            />

            <ProfileSecuritySection
              v-if="activeTab === 'security' && isOwnProfile"
              :user="user"
              :password-form="passwordForm"
              :verification-sending="verificationSending"
              :verification-success="verificationSuccess"
              :verification-error="verificationError"
              :changing-password="changingPassword"
              :password-success="passwordSuccess"
              :password-error="passwordError"
              @resend-verification="resendVerificationEmail"
              @change-password="changePassword"
            />
          </main>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useForumStore } from '@/stores/forum'
import { useModalStore } from '@/stores/modal'
import ForumStateBlock from '@/components/forum/ForumStateBlock.vue'
import ProfileDiscussionSection from '@/components/profile/ProfileDiscussionSection.vue'
import ProfileHero from '@/components/profile/ProfileHero.vue'
import ProfilePostSection from '@/components/profile/ProfilePostSection.vue'
import ProfileSecuritySection from '@/components/profile/ProfileSecuritySection.vue'
import ProfileSettingsSection from '@/components/profile/ProfileSettingsSection.vue'
import ProfileSidebar from '@/components/profile/ProfileSidebar.vue'
import { useProfilePage } from '@/composables/useProfilePage'
import { useProfilePresentation } from '@/composables/useProfilePresentation'
import {
  buildDiscussionPath,
  getUserAvatarColor,
} from '@/utils/forum'

const route = useRoute()
const authStore = useAuthStore()
const forumStore = useForumStore()
const modalStore = useModalStore()
const {
  user,
  discussions,
  posts,
  loading,
  loadingDiscussions,
  loadingPosts,
  activeTab,
  saving,
  avatarUploading,
  avatarInput,
  settingsSuccess,
  settingsError,
  verificationSending,
  verificationSuccess,
  verificationError,
  changingPassword,
  passwordSuccess,
  passwordError,
  loadingPreferences,
  savingPreferences,
  preferencesSuccess,
  preferencesError,
  editForm,
  passwordForm,
  preferences,
  isOwnProfile,
  switchTab,
  saveProfile,
  savePreferences,
  resendVerificationEmail,
  changePassword,
  handleAvatarSelected
} = useProfilePage({
  authStore,
  modalStore,
  route
})
const {
  isOnline,
  getUserPrimaryGroupIcon,
  getUserPrimaryGroupColor,
  getUserPrimaryGroupLabel,
  formatDate,
  formatJoinDate,
  formatLastSeen
} = useProfilePresentation(user)

watch(
  user,
  value => {
    if (!value) return
    const displayName = value.display_name || value.username
    const bio = String(value.bio || '').replace(/\s+/g, ' ').trim()
    forumStore.setPageMeta({
      title: `${displayName} 的主页`,
      description: bio || `${displayName} 在论坛发布了 ${value.discussion_count || 0} 个讨论和 ${value.comment_count || 0} 条回复。`,
      canonicalUrl: `/u/${value.username || value.id}`,
    })
  },
  { immediate: true }
)

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
}

.user-content {
  background: white;
  border: 1px solid #e3e8ed;
  border-radius: 3px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

@media (max-width: 768px) {
  .user-page-layout {
    grid-template-columns: 1fr;
  }
}
</style>
