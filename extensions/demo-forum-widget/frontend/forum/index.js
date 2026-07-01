import { extendForum } from '@bias/core/forum'

export const extend = [
  extendForum(forum => {
    forum.navItem({
      key: 'demo-forum-widget',
      label: 'Demo Widget',
      href: '/demo-forum-widget',
      icon: 'fas fa-puzzle-piece',
      section: 'primary',
      order: 1000,
    })
    forum.feedbackNote({
      key: 'demo-forum-widget-note',
      surfaces: ['discussion-list-empty-state'],
      tone: 'info',
      message: 'Demo Forum Widget 演示通过 forum.feedbackNote 注入前台反馈信息。',
    })
  }),
]
