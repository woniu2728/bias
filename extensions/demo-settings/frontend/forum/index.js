import { extendForum } from '@bias/core/forum'

export const extend = [
  extendForum(forum => forum.navItem({
    key: 'demo-settings',
    label: 'Demo Settings',
    href: '/demo-settings',
    icon: 'fas fa-puzzle-piece',
    section: 'primary',
    order: 1000,
  })),
]
