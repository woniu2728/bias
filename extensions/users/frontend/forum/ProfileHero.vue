<template>
  <div class="user-hero" :style="{ backgroundColor: user.color || '#4d698e' }">
    <div class="hero-background">
      <div class="profile-hero-container">
        <div class="user-card">
          <div class="user-avatar">
            <label
              v-if="isOwnProfile"
              class="avatar-uploader"
              :class="{ disabled: avatarUploading }"
            >
              <input
                :ref="avatarInputRef"
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp"
                class="avatar-input"
                @change="$emit('avatar-selected', $event)"
              />
              <span class="avatar-upload-badge">
                {{ avatarUploadText }}
              </span>
            </label>
            <img
              v-if="user.avatar_url"
              :src="user.avatar_url"
              :alt="user.username"
              class="avatar-large avatar-image"
            />
            <div v-else class="avatar-large" :style="{ backgroundColor: getUserAvatarColor(user) }">
              {{ user.username.charAt(0).toUpperCase() }}
            </div>
            <span
              v-if="primaryGroupBadge"
              class="avatar-group-badge"
              :style="{ backgroundColor: primaryGroupBadge.color || getUserPrimaryGroupColor(user) }"
              :title="primaryGroupBadge.label || getUserPrimaryGroupLabel(user)"
            >
              <i :class="primaryGroupBadge.icon || getUserPrimaryGroupIcon(user)"></i>
            </span>
          </div>
          <div class="user-info-wrapper">
            <h1 class="user-identity">{{ user.display_name || user.username }}</h1>
            <ul v-if="inlineBadges.length" class="user-badges">
              <li
                v-for="badge in inlineBadges"
                :key="badge.key"
                class="badge"
                :class="badge.className"
              >
                <i v-if="badge.icon" :class="badge.icon"></i>
                {{ badge.label }}
              </li>
            </ul>
            <ul v-if="heroMetaItems.length" class="user-info">
              <li
                v-for="item in heroMetaItems"
                :key="item.key"
                class="user-info-item"
                :class="item.className"
              >
                <i v-if="item.icon" :class="item.iconClassName || item.icon"></i>
                <span :title="item.title || item.text || ''">{{ item.text }}</span>
              </li>
            </ul>
          </div>
          <div class="user-card-controls">
            <button v-if="isOwnProfile" type="button" class="btn-control" @click="$emit('open-settings')">
              <i class="fas fa-sliders-h"></i>
              {{ settingsButtonText }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>

import { toRef } from '@bias/core'
import { useProfileHeroState } from './useProfileHeroState'

const props = defineProps({
  user: {
    type: Object,
    required: true
  },
  isOwnProfile: {
    type: Boolean,
    default: false
  },
  isOnline: {
    type: Boolean,
    default: false
  },
  avatarUploading: {
    type: Boolean,
    default: false
  },
  avatarInputRef: {
    type: Object,
    default: null
  },
  formatJoinDate: {
    type: Function,
    required: true
  },
  formatLastSeen: {
    type: Function,
    required: true
  },
  getUserAvatarColor: {
    type: Function,
    required: true
  },
  getUserPrimaryGroupIcon: {
    type: Function,
    required: true
  },
  getUserPrimaryGroupColor: {
    type: Function,
    required: true
  },
  getUserPrimaryGroupLabel: {
    type: Function,
    required: true
  },
  userBadges: {
    type: Array,
    default: () => []
  }
})

const {
  avatarUploadText,
  heroMetaItems,
  inlineBadges,
  primaryGroupBadge,
  settingsButtonText,
} = useProfileHeroState({
  avatarUploading: toRef(props, 'avatarUploading'),
  formatJoinDate: props.formatJoinDate,
  formatLastSeen: props.formatLastSeen,
  isOnline: toRef(props, 'isOnline'),
  user: toRef(props, 'user'),
  userBadges: toRef(props, 'userBadges'),
})

defineEmits(['avatar-selected', 'open-settings'])
</script>

<style scoped>
.user-hero {
  color: white;
  position: relative;
  margin-bottom: -20px;
}

.hero-background {
  background: linear-gradient(rgba(0, 0, 0, 0.1), rgba(0, 0, 0, 0.2));
  padding: 40px 0 60px 0;
}

.profile-hero-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.user-card {
  display: flex;
  align-items: flex-start;
  gap: 20px;
  min-width: 0;
}

.user-avatar {
  flex-shrink: 0;
  position: relative;
}

.avatar-large {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.25);
  border: 3px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  font-weight: 600;
  color: white;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.avatar-image {
  object-fit: cover;
  background: rgba(255, 255, 255, 0.18);
}

.avatar-group-badge {
  position: absolute;
  right: -2px;
  top: -2px;
  z-index: 1;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.92);
  color: white;
  box-shadow: 0 8px 18px rgba(18, 29, 41, 0.22);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.avatar-group-badge i {
  font-size: 13px;
}

.avatar-uploader {
  position: absolute;
  right: -8px;
  bottom: -6px;
  z-index: 2;
  cursor: pointer;
}

.avatar-uploader.disabled {
  cursor: default;
}

.avatar-input {
  display: none;
}

.avatar-upload-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 76px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(47, 60, 77, 0.88);
  color: white;
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 8px 20px rgba(21, 32, 43, 0.2);
}

.user-info-wrapper {
  flex: 1;
  min-width: 0;
  padding-top: 8px;
}

.user-identity {
  font-size: 32px;
  font-weight: 300;
  margin: 0 0 10px 0;
  display: block;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  color: white;
  overflow-wrap: anywhere;
}

.user-badges {
  list-style: none;
  padding: 0;
  margin: 0 0 12px 0;
  display: flex;
  gap: 6px;
}

.user-badges li {
  display: inline-block;
}

.badge-admin {
  background: rgba(231, 76, 60, 0.95);
  color: white;
  padding: 4px 12px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.user-info {
  list-style: none;
  padding: 0;
  margin: 0;
  font-size: 13px;
  opacity: 0.95;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  color: white;
}

.user-info li {
  display: inline-block;
  margin-right: 18px;
  overflow-wrap: anywhere;
}

.user-info-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.user-info i {
  margin-right: 6px;
}

.user-info-item :deep(.hero-meta-icon.fa-circle) {
  font-size: 8px;
  vertical-align: middle;
  margin-right: 0;
}

.user-info-item :deep(.hero-meta-icon--online.fa-circle) {
  color: #2ecc71;
}

.user-card-controls {
  display: flex;
  align-items: flex-start;
  padding-top: 8px;
}

.btn-control {
  background: rgba(255, 255, 255, 0.15);
  border: 2px solid rgba(255, 255, 255, 0.4);
  color: white;
  padding: 9px 18px;
  border-radius: 3px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.btn-control:hover {
  background: rgba(255, 255, 255, 0.25);
  border-color: rgba(255, 255, 255, 0.6);
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

.btn-control i {
  font-size: 13px;
}

@media (max-width: 768px) {
  .user-card {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .user-info-wrapper {
    text-align: center;
    width: 100%;
  }

  .user-badges {
    justify-content: center;
    flex-wrap: wrap;
  }

  .user-info li {
    display: block;
    margin: 6px 0 0;
  }

  .avatar-group-badge {
    width: 24px;
    height: 24px;
  }

  .avatar-group-badge i {
    font-size: 11px;
  }
}
</style>
