import { extendForum } from '@bias/forum'

export const extend = [
  extendForum(registerRealtimeForum),
]

function registerRealtimeForum(forum) {
  forum.uiCopy({
    key: 'forum-realtime-status-reconnecting',
    moduleId: 'realtime',
    order: 645,
    surfaces: ['forum-realtime-status-reconnecting'],
    resolve: () => ({
      text: '论坛实时连接已断开，正在尝试重新连接...',
    }),
  })

  forum.uiCopy({
    key: 'forum-realtime-status-error',
    moduleId: 'realtime',
    order: 646,
    surfaces: ['forum-realtime-status-error'],
    resolve: () => ({
      text: '论坛实时连接暂时不可用，稍后会在下次页面交互时重试。',
    }),
  })
}
