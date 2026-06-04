import {
  registerEmptyState,
  registerForumNavItem,
  registerHeaderItem,
  registerNotificationRenderer,
  registerStateBlock,
  registerUiCopy,
} from '@/forum/registry'

export async function bootForumExtension() {
  registerNavigation()
  registerNotificationRenderers()
  registerNotificationStates()
  registerNotificationCopy()
}

function registerNavigation() {
  registerForumNavItem({
    key: 'notifications',
    moduleId: 'notifications',
    to: '/notifications',
    icon: 'fas fa-inbox',
    label: '通知',
    description: '查看回复、提及和审核通知。',
    section: 'personal',
    order: 40,
    badge: ({ notificationStore }) => {
      const count = Number(notificationStore?.unreadCount || 0)
      return count > 0 ? count : ''
    },
    isVisible: ({ showNotifications }) => Boolean(showNotifications),
  })

  registerHeaderItem({
    key: 'user-notifications-menu',
    moduleId: 'notifications',
    placement: 'user-menu',
    order: 20,
    icon: 'fas fa-bell',
    label: '通知',
    to: '/notifications',
    badge: ({ notificationStore }) => {
      const count = Number(notificationStore?.unreadCount || 0)
      return count > 0 ? count : ''
    },
    isVisible: ({ authStore }) => Boolean(authStore?.user),
    isActive: ({ route }) => route?.name === 'notifications',
  })

  registerHeaderItem({
    key: 'mobile-notifications',
    moduleId: 'notifications',
    placement: 'mobile-drawer-personal',
    order: 10,
    icon: 'fas fa-inbox',
    label: '通知',
    to: '/notifications',
    badge: ({ notificationStore }) => {
      const count = Number(notificationStore?.unreadCount || 0)
      return count > 0 ? count : ''
    },
    isVisible: ({ authStore }) => Boolean(authStore?.user),
    isActive: ({ route }) => route?.name === 'notifications',
  })
}

function registerNotificationRenderers() {
  registerNotificationRenderer({
    type: 'postReply',
    key: 'postReply',
    moduleId: 'notifications',
    label: '回复被回应',
    icon: 'fas fa-comment-dots',
    navigationScope: 'post',
    groupLabel: '互动反馈',
    order: 40,
    getText(notification) {
      const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
      return `${fromUser} 回复了你的帖子`
    },
  })

  registerNotificationRenderer({
    type: 'userSuspended',
    key: 'userSuspended',
    moduleId: 'notifications',
    label: '账号封禁通知',
    icon: 'fas fa-user-lock',
    navigationScope: 'profile',
    groupLabel: '账号状态',
    order: 90,
    getText(notification) {
      const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
      const message = notification?.data?.suspend_message ? `：${notification.data.suspend_message}` : ''
      return `${fromUser} 已封禁你的账号${message}`
    },
  })

  registerNotificationRenderer({
    type: 'userUnsuspended',
    key: 'userUnsuspended',
    moduleId: 'notifications',
    label: '账号解除封禁',
    icon: 'fas fa-user-check',
    navigationScope: 'profile',
    groupLabel: '账号状态',
    order: 100,
    getText(notification) {
      const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
      return `${fromUser} 已解除你的账号封禁`
    },
  })
}

function registerNotificationStates() {
  registerEmptyState({
    key: 'notifications-page-unread-empty',
    moduleId: 'notifications',
    order: 10,
    surfaces: ['notifications-page-empty'],
    isVisible: ({ notifications, unreadOnly }) => Array.isArray(notifications) && notifications.length === 0 && Boolean(unreadOnly),
    resolve: () => ({ text: '当前没有未读通知' }),
  })

  registerEmptyState({
    key: 'notifications-page-filter-empty',
    moduleId: 'notifications',
    order: 20,
    surfaces: ['notifications-page-empty'],
    isVisible: ({ notifications, activeType }) => Array.isArray(notifications) && notifications.length === 0 && Boolean(activeType),
    resolve: () => ({ text: '当前筛选下暂无通知' }),
  })

  registerEmptyState({
    key: 'notifications-page-default-empty',
    moduleId: 'notifications',
    order: 30,
    surfaces: ['notifications-page-empty'],
    isVisible: ({ notifications }) => Array.isArray(notifications) && notifications.length === 0,
    resolve: () => ({ text: '暂无通知' }),
  })

  registerEmptyState({
    key: 'notifications-menu-empty',
    moduleId: 'notifications',
    order: 40,
    surfaces: ['notifications-menu-empty'],
    isVisible: ({ notifications }) => Array.isArray(notifications) && notifications.length === 0,
    resolve: () => ({ text: '暂无通知' }),
  })

  registerStateBlock({
    key: 'notifications-page-loading',
    moduleId: 'notifications',
    order: 20,
    surfaces: ['notifications-page-loading'],
    isVisible: ({ loading }) => Boolean(loading),
    resolve: () => ({ text: '正在加载通知...' }),
  })

  registerStateBlock({
    key: 'notifications-menu-loading',
    moduleId: 'notifications',
    order: 30,
    surfaces: ['notifications-menu-loading'],
    isVisible: ({ loading }) => Boolean(loading),
    resolve: () => ({ text: '加载中...' }),
  })
}

function registerNotificationCopy() {
  const copies = [
    ['notification-filter-all-label', 479, () => '全部通知'],
    ['notification-view-mode-timeline', 479, () => '时间流'],
    ['notification-view-mode-grouped', 479, () => '按讨论分组'],
    ['notification-confirm-cancel', 479, () => '取消'],
    ['notification-confirm-mark-all-title', 479, ({ hasActiveFilter }) => (hasActiveFilter ? '标记当前筛选结果为已读' : '全部标记为已读')],
    [
      'notification-confirm-mark-all-message',
      479,
      ({ hasActiveFilter, unreadCount }) => (hasActiveFilter
        ? `确定将当前筛选结果中的 ${unreadCount} 条未读通知标记为已读吗？`
        : `确定将当前 ${unreadCount} 条未读通知标记为已读吗？`),
    ],
    ['notification-confirm-mark-all-confirm', 479, () => '标记已读'],
    ['notification-alert-mark-all-success-title', 479, () => '已全部标记为已读'],
    ['notification-alert-mark-all-success-message', 479, ({ hasActiveFilter }) => (hasActiveFilter ? '当前筛选范围内的未读通知已更新为已读。' : '当前页面的未读通知已更新为已读。')],
    ['notification-alert-action-failed-title', 479, () => '操作失败'],
    ['notification-confirm-clear-read-title', 479, ({ hasActiveFilter }) => (hasActiveFilter ? '清除当前筛选中的已读通知' : '清除当前页已读通知')],
    [
      'notification-confirm-clear-read-message',
      479,
      ({ hasActiveFilter, readCount }) => (hasActiveFilter
        ? `确定清除当前筛选结果中的 ${readCount} 条已读通知吗？`
        : `确定清除当前页中的 ${readCount} 条已读通知吗？`),
    ],
    ['notification-confirm-clear-read-confirm', 479, () => '清除已读'],
    ['notification-alert-clear-read-success-title', 479, () => '已清除已读通知'],
    ['notification-alert-clear-read-success-message', 479, () => '当前范围内的已读通知已清除。'],
    ['notification-confirm-mark-group-title', 479, () => '标记该讨论通知为已读'],
    ['notification-confirm-mark-group-message', 479, ({ groupTitle, unreadCount }) => `确定将“${groupTitle}”下的 ${unreadCount} 条未读通知标记为已读吗？`],
    ['notification-confirm-clear-group-title', 479, () => '清除该讨论中的已读通知'],
    ['notification-confirm-clear-group-message', 479, ({ groupTitle, readCount }) => `确定清除“${groupTitle}”下的 ${readCount} 条已读通知吗？`],
    ['notification-confirm-delete-title', 479, () => '删除通知'],
    ['notification-confirm-delete-message', 479, () => '确定要删除这条通知吗？'],
    ['notification-confirm-delete-confirm', 479, () => '删除'],
    ['notification-alert-delete-failed-title', 479, () => '删除失败'],
    ['notification-error-retry-message', 479, () => '请稍后重试'],
    ['notification-load-error', 479, () => '加载通知失败，请稍后重试'],
    ['notification-summary-count', 479, ({ unreadOnly, count }) => (unreadOnly ? `${Number(count || 0)} 未读` : String(Number(count || 0)))],
    ['notification-type-count', 479, ({ total, unread }) => (Number(unread || 0) > 0 ? `${Number(total || 0)} / ${Number(unread || 0)} 未读` : String(Number(total || 0)))],
    ['notifications-menu-action-failed-title', 479, () => '操作失败'],
    ['notifications-menu-action-retry-message', 479, () => '请稍后重试'],
    ['notification-page-hero-title', 940, () => '通知'],
    ['notification-page-hero-pill', 950, () => '消息中心'],
    ['notification-page-hero-description', 960, () => '这里会显示回复、提及、点赞、审核和账号状态相关通知。'],
    ['notification-page-mark-all', 970, ({ marking, hasActiveFilter }) => (marking ? '处理中...' : (hasActiveFilter ? '当前筛选标记已读' : '全部标记为已读'))],
    ['notification-page-clear-read', 980, ({ marking, hasActiveFilter }) => (marking ? '处理中...' : (hasActiveFilter ? '当前筛选清除已读' : '当前页清除已读'))],
    ['notification-page-unread-toggle', 990, ({ unreadOnly }) => (unreadOnly ? '查看全部通知' : '仅看未读')],
    ['notification-page-preferences-link', 1000, () => '通知偏好前往个人设置'],
    ['notification-page-filter-description', 1010, () => '按通知类型筛选消息流，方便集中处理提及、点赞、审核和账号状态通知。'],
    ['notification-page-open-discussion', 1020, () => '打开讨论'],
    ['notification-page-mark-group-read', 1030, () => '整组标记已读'],
    ['notification-page-clear-group-read', 1040, () => '整组清理已读'],
    ['notification-page-group-count', 1050, ({ count }) => `${Number(count || 0)} 条通知`],
    ['notification-page-active-filter-label', 1055, ({ label }) => label || '全部通知'],
    ['notifications-menu-title', 1210, () => '通知'],
    ['notifications-menu-mark-all', 1220, ({ markingAllRead }) => (markingAllRead ? '正在标记已读...' : '全部标记为已读')],
    ['notifications-menu-clear-read', 1230, ({ clearingRead }) => (clearingRead ? '正在清除已读...' : '清除已读通知')],
    ['notifications-menu-open-page', 1240, () => '查看全部通知'],
    ['notifications-menu-mark-all-success', 1245, () => '已全部标记为已读'],
    ['notifications-menu-mark-all-error', 1246, () => '全部标记已读失败'],
    ['notifications-menu-clear-read-confirm-title', 1247, () => '清除已读通知'],
    ['notifications-menu-clear-read-confirm-message', 1248, () => '确定要清除所有已读通知吗？未读通知会保留。'],
    ['notifications-menu-clear-read-confirm-confirm', 1249, () => '清除'],
    ['notifications-menu-clear-read-success', 1249, () => '已清除已读通知'],
    ['notifications-menu-clear-read-error', 1249, () => '清除已读通知失败'],
    ['notifications-menu-summary-count', 1249, ({ unread, total }) => (Number(unread || 0) > 0 ? `${Number(unread || 0)} 未读` : String(Number(total || 0)))],
    ['notification-card-mark-read', 1250, () => '标记为已读'],
    ['notification-card-delete', 1260, () => '删除通知'],
  ]

  for (const [key, order, resolveText] of copies) {
    registerUiCopy({
      key,
      moduleId: 'notifications',
      order,
      surfaces: [key],
      resolve: context => ({ text: resolveText(context || {}) }),
    })
  }
}
