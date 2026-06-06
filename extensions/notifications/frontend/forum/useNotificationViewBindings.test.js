import test from 'node:test'
import assert from 'node:assert/strict'
import { ref } from '@bias/forum'
import { createNotificationViewBindings } from './useNotificationViewBindings.js'

test('notification view bindings expose sidebar, hero, filter and list props', () => {
  const bindings = createNotificationViewBindings({
    activeNotificationLabel: ref('全部通知'),
    activeType: ref(''),
    authStore: { isAuthenticated: true, canStartDiscussion: true },
    changePage() {},
    changeType() {},
    changeViewMode() {},
    clearGroupReadNotifications() {},
    clearGroupReadText: ref('整组清理已读'),
    clearReadButtonText: ref('清除已读'),
    clearReadNotifications() {},
    currentPage: ref(2),
    deleteNotification() {},
    emptyStateText: ref('暂无通知'),
    filterDescriptionText: ref('按通知类型筛选'),
    filteredReadCount: ref(1),
    filteredUnreadCount: ref(2),
    formatDate: value => value,
    getNotificationAvatarColor: () => '#000',
    getNotificationAvatarInitial: () => 'A',
    getNotificationIconClass: () => 'icon',
    getNotificationMessageHtml: () => '<p>hi</p>',
    getNotificationPresentation: () => ({ messageHtml: '<p>hi</p>' }),
    getUserDisplayName: () => 'alice',
    groupedNotifications: ref([{ key: 'discussion-1', items: [] }]),
    groupCountText: count => `${count} 条通知`,
    handleNotificationClick() {},
    handleStartDiscussion() {},
    heroDescriptionText: ref('通知说明'),
    heroPillText: ref('消息中心'),
    heroTitleText: ref('通知'),
    loadError: ref(''),
    loading: ref(false),
    loadingStateText: ref('加载中...'),
    markAllAsRead() {},
    markAllButtonText: ref('全部标记为已读'),
    markAsRead() {},
    marking: ref(false),
    markGroupAsRead() {},
    markGroupReadText: ref('整组标记已读'),
    notificationStore: { unreadCount: 3 },
    notificationTypeItems: ref([{ value: '', label: '全部通知' }]),
    notifications: ref([{ id: 1 }]),
    openDiscussionText: ref('打开讨论'),
    preferencesLinkText: ref('通知偏好前往个人设置'),
    router: { push() {} },
    toggleUnreadOnly() {},
    totalPages: ref(4),
    unreadToggleText: ref('仅看未读'),
    viewMode: ref('timeline'),
    viewModeItems: ref([{ value: 'timeline', label: '时间线' }]),
  })

  assert.deepEqual(bindings.sidebarBindings.value, {
    authStore: { isAuthenticated: true, canStartDiscussion: true },
    notificationStore: { unreadCount: 3 },
    showStartDiscussionButton: true,
  })
  assert.equal(bindings.heroBindings.value.title, '通知')
  assert.equal(bindings.filterCardBindings.value.activeNotificationLabel, '全部通知')
  assert.equal(bindings.listBindings.value.currentPage, 2)
  assert.deepEqual(bindings.listBindings.value.notifications, [{ id: 1 }])
})

test('notification view bindings expose stable events including discussion open', () => {
  const calls = []
  const bindings = createNotificationViewBindings({
    activeNotificationLabel: ref('全部通知'),
    activeType: ref(''),
    authStore: { isAuthenticated: false, canStartDiscussion: false },
    changePage(page) {
      calls.push(['page', page])
    },
    changeType(type) {
      calls.push(['type', type])
    },
    changeViewMode(mode) {
      calls.push(['view', mode])
    },
    clearGroupReadNotifications(group) {
      calls.push(['clear-group', group.key])
    },
    clearGroupReadText: ref('整组清理已读'),
    clearReadButtonText: ref('清除已读'),
    clearReadNotifications() {
      calls.push('clear-read')
    },
    currentPage: ref(1),
    deleteNotification(notification) {
      calls.push(['delete', notification.id])
    },
    emptyStateText: ref('暂无通知'),
    filterDescriptionText: ref('按通知类型筛选'),
    filteredReadCount: ref(0),
    filteredUnreadCount: ref(0),
    formatDate: value => value,
    getNotificationAvatarColor: () => '#000',
    getNotificationAvatarInitial: () => 'A',
    getNotificationIconClass: () => 'icon',
    getNotificationMessageHtml: () => '<p>hi</p>',
    getNotificationPresentation: () => ({ messageHtml: '<p>hi</p>' }),
    getUserDisplayName: () => 'alice',
    groupedNotifications: ref([]),
    groupCountText: count => `${count} 条通知`,
    handleNotificationClick(notification) {
      calls.push(['click', notification.id])
    },
    handleStartDiscussion() {
      calls.push('start')
    },
    heroDescriptionText: ref('通知说明'),
    heroPillText: ref('消息中心'),
    heroTitleText: ref('通知'),
    loadError: ref(''),
    loading: ref(false),
    loadingStateText: ref('加载中...'),
    markAllAsRead() {
      calls.push('mark-all')
    },
    markAllButtonText: ref('全部标记为已读'),
    markAsRead(notification) {
      calls.push(['mark-read', notification.id])
    },
    marking: ref(false),
    markGroupAsRead(group) {
      calls.push(['mark-group', group.key])
    },
    markGroupReadText: ref('整组标记已读'),
    notificationStore: { unreadCount: 0 },
    notificationTypeItems: ref([]),
    notifications: ref([]),
    openDiscussionText: ref('打开讨论'),
    preferencesLinkText: ref('通知偏好前往个人设置'),
    router: {
      push(path) {
        calls.push(['push', path])
      },
    },
    toggleUnreadOnly() {
      calls.push('toggle-unread')
    },
    totalPages: ref(1),
    unreadToggleText: ref('仅看未读'),
    viewMode: ref('timeline'),
    viewModeItems: ref([]),
  })

  bindings.sidebarEvents.startDiscussion()
  bindings.heroEvents.markAllAsRead()
  bindings.heroEvents.clearReadNotifications()
  bindings.heroEvents.toggleUnreadOnly()
  bindings.filterCardEvents.changeType('mentions')
  bindings.filterCardEvents.changeViewMode('grouped')
  bindings.listEvents.changePage(3)
  bindings.listEvents.markAsRead({ id: 7 })
  bindings.listEvents.handleNotificationClick({ id: 8 })
  bindings.listEvents.deleteNotification({ id: 9 })
  bindings.listEvents.markGroupAsRead({ key: 'discussion-1' })
  bindings.listEvents.clearGroupReadNotifications({ key: 'discussion-2' })
  bindings.listEvents.openDiscussion(12)

  assert.deepEqual(calls, [
    'start',
    'mark-all',
    'clear-read',
    'toggle-unread',
    ['type', 'mentions'],
    ['view', 'grouped'],
    ['page', 3],
    ['mark-read', 7],
    ['click', 8],
    ['delete', 9],
    ['mark-group', 'discussion-1'],
    ['clear-group', 'discussion-2'],
    ['push', '/d/12'],
  ])
})
