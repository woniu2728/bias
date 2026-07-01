import { extendForum } from '@bias/core/forum'

export const extend = [
  extendForum(forum => forum.navItem({
    key: 'demo-admin-page',
    label: 'Demo Admin Page',
    href: '/demo-admin-page',
    icon: 'fas fa-puzzle-piece',
    section: 'primary',
    order: 1000,
  })),
]
