import {
  extendForum,
} from '@bias/forum'
import ProfilePointsSection from './ProfilePointsSection.vue'
import {
  buildUserPointsPath,
  formatPointsBalance,
  formatPointsLabel,
} from './pointsRuntime.js'

export const extend = [
  extendForum('points', registerPointsForum),
]

function registerPointsForum(forum) {
  forum
    .headerItem({
      key: 'points-user-menu-balance',
      moduleId: 'points',
      placement: 'user-menu',
      order: 15,
      icon: 'fas fa-coins',
      label: ({ authStore }) => `积分 ${formatPointsBalance(authStore?.user)}`,
      to: ({ authStore }) => buildUserPointsPath(authStore?.user),
      isVisible: ({ authStore }) => Boolean(authStore?.user),
    })
    .headerItem({
      key: 'points-mobile-profile-balance',
      moduleId: 'points',
      placement: 'mobile-drawer-personal',
      order: 25,
      icon: 'fas fa-coins',
      label: ({ authStore }) => formatPointsLabel(authStore?.user),
      to: ({ authStore }) => buildUserPointsPath(authStore?.user),
      isVisible: ({ authStore }) => Boolean(authStore?.user),
    })
    .profilePanel({
      key: 'points',
      moduleId: 'points',
      label: '积分',
      icon: 'fas fa-coins',
      order: 25,
      badge: ({ user }) => formatPointsBalance(user),
      resolve: ({ user }) => ({
        component: ProfilePointsSection,
        componentProps: {
          user,
        },
      }),
    })
    .heroMeta({
      key: 'profile-points-balance',
      moduleId: 'points',
      order: 30,
      surfaces: ['profile-hero'],
      resolve: ({ user }) => ({
        icon: 'fas fa-coins',
        text: formatPointsLabel(user),
      }),
    })
    .uiCopy({
      key: 'points-profile-title',
      order: 10,
      surfaces: ['points-profile-title'],
      resolve: () => ({ text: '积分' }),
    })
    .uiCopy({
      key: 'points-profile-description',
      order: 20,
      surfaces: ['points-profile-description'],
      resolve: () => ({ text: '积分可通过发起讨论、发表回复和收到点赞获得，也可用于消耗型扩展能力。' }),
    })

  return forum
}
