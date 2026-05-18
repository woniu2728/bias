import { computed } from 'vue'
import {
  formatMonth,
  formatRelativeTime
} from '../utils/forum.js'
import {
  getUserPrimaryGroupColor,
  getUserPrimaryGroupIcon,
  getUserPrimaryGroupLabel,
} from '../utils/userPrimaryGroup.js'
import { resolveProfileOnlineState } from '../utils/profileOnlineState.js'

export function createProfilePresentation({
  formatMonthText = formatMonth,
  formatRelativeText = formatRelativeTime,
  getPrimaryGroupColor = getUserPrimaryGroupColor,
  getPrimaryGroupIcon = getUserPrimaryGroupIcon,
  getPrimaryGroupLabel = getUserPrimaryGroupLabel,
  isUserOnline = () => false,
  user,
}) {
  const isOnline = computed(() => {
    return resolveProfileOnlineState({
      userId: user.value?.id,
      lastSeenAt: user.value?.last_seen_at,
      isUserOnline,
    })
  })

  function formatDate(dateString) {
    return formatRelativeText(dateString)
  }

  function formatJoinDate(dateString) {
    return formatMonthText(dateString)
  }

  function formatLastSeen(dateString) {
    if (!dateString) return '从未'

    const date = new Date(dateString)
    const now = new Date()
    const diff = now - date
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)

    if (minutes < 1) return '刚刚活跃'
    if (minutes < 60) return `${minutes}分钟前活跃`
    if (hours < 24) return `${hours}小时前活跃`
    if (days < 30) return `${days}天前活跃`

    return date.toLocaleDateString('zh-CN')
  }

  return {
    isOnline,
    getUserPrimaryGroupIcon: getPrimaryGroupIcon,
    getUserPrimaryGroupColor(userValue) {
      return getPrimaryGroupColor(userValue, '#4d698e')
    },
    getUserPrimaryGroupLabel: getPrimaryGroupLabel,
    formatDate,
    formatJoinDate,
    formatLastSeen
  }
}

export function useProfilePresentation(user, options = {}) {
  return createProfilePresentation({
    user,
    ...options,
  })
}
