import {
  computed } from '@bias/core'
import { getHeroMetaItems,
  getUiCopy
} from '@bias/forum'

export function createProfileHeroState({
  avatarUploading,
  formatJoinDate,
  formatLastSeen,
  getHeroMeta = getHeroMetaItems,
  getText = getUiCopy,
  isOnline,
  user,
  userBadges,
}) {
  const normalizedBadges = computed(() => Array.isArray(userBadges.value) ? userBadges.value : [])
  const primaryGroupBadge = computed(() => normalizedBadges.value.find(item => item.variant === 'group') || null)
  const inlineBadges = computed(() => normalizedBadges.value.filter(item => item.variant !== 'group'))

  const heroMetaItems = computed(() => getHeroMeta({
    user: user.value,
    isOnline: isOnline.value,
    formatJoinDate,
    formatLastSeen,
    surface: 'profile-hero',
  }))

  const avatarUploadText = computed(() => getText({
    surface: 'profile-hero-avatar-upload',
    uploading: avatarUploading.value,
  })?.text || (avatarUploading.value ? '上传中...' : '更换头像'))

  const settingsButtonText = computed(() => getText({
    surface: 'profile-hero-settings-button',
  })?.text || '设置')

  return {
    avatarUploadText,
    heroMetaItems,
    inlineBadges,
    primaryGroupBadge,
    settingsButtonText,
  }
}

export function useProfileHeroState(options) {
  return createProfileHeroState(options)
}
