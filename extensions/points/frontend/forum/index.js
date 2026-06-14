import {
  extendForum,
} from '@bias/forum'
import ProfilePointsSection from './ProfilePointsSection.vue'

export const extend = [
  extendForum('points', registerPointsForum),
]

function registerPointsForum(forum) {
  forum
    .profilePanel({
      key: 'points',
      moduleId: 'points',
      label: '积分',
      icon: 'fas fa-coins',
      order: 25,
      badge: ({ user }) => Number(user?.points_balance || 0),
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
        text: `${Number(user?.points_balance || 0)} 积分`,
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
