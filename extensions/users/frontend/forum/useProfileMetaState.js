import {
  watch,
  computed } from '@bias/core'
import { getPageState
} from '@bias/forum'
import { getUserBadges, resolveProfileMetaPayload } from '@bias/users'

export function createProfileMetaState({
  authStore,
  forumStore,
  getPageStateBlock = getPageState,
  getBadges = getUserBadges,
  loading,
  user,
  resolveMetaPayload = resolveProfileMetaPayload,
}) {
  const userBadges = computed(() => {
    if (!user.value) return []

    return getBadges({
      user: user.value,
      authStore,
    })
  })

  const loadingStateText = computed(() => {
    const pageStateBlock = getPageStateBlock({
      surface: 'profile-loading',
      loading: loading.value,
      user: user.value,
    })

    return pageStateBlock?.text || '加载中...'
  })

  const missingStateText = computed(() => {
    const pageStateBlock = getPageStateBlock({
      surface: 'profile-not-found',
      loading: loading.value,
      user: user.value,
    })

    return pageStateBlock?.text || '用户不存在'
  })

  watch(
    user,
    value => {
      const payload = resolveMetaPayload(value)
      if (!payload) return
      forumStore.setPageMeta(payload)
    },
    { immediate: true }
  )

  return {
    loadingStateText,
    missingStateText,
    userBadges,
  }
}

export function useProfileMetaState(options) {
  return createProfileMetaState(options)
}
