import { extendForum } from '@bias/core/forum'

export const extend = [
  extendForum(forum => forum.navItem({
    key: 'demo-notification',
    label: 'Demo Notification',
    href: '/demo-notification',
    icon: 'fas fa-puzzle-piece',
    section: 'primary',
    order: 1000,
  })),
]
