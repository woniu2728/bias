import {
  api } from '@bias/core'
import {
  extendForum,
  getUiCopy
} from '@bias/forum'
import {
  getSubscriptionActionDescription,
  getSubscriptionActionLabel,
  isDiscussionSubscribed,
  shouldFollowAfterReply,
} from './subscriptionRuntime.js'

export const extend = [
  extendForum(registerSubscriptionsForum),
]

function registerSubscriptionsForum(forum) {
  forum.navItem({
    key: 'following',
    moduleId: 'subscriptions',
    to: '/following',
    icon: 'fas fa-bell',
    label: '关注中',
    description: '查看你关注讨论的更新。',
    section: 'primary',
    order: 20,
    surfaces: ['discussion-sidebar', 'mobile-drawer'],
    isVisible: ({ authStore }) => Boolean(authStore?.user),
  })

  forum.notificationRenderer({
    type: 'discussionReply',
    key: 'discussionReply',
    moduleId: 'subscriptions',
    label: '讨论新回复',
    icon: 'fas fa-reply',
    navigationScope: 'post',
    groupLabel: '讨论互动',
    order: 10,
    getText(notification) {
      const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
      const discussionTitle = notification?.data?.discussion_title || ''
      return `${fromUser} 回复了你的讨论 "${discussionTitle}"`
    },
  })

  forum.emptyState({
    key: 'discussion-list-following-empty',
    moduleId: 'subscriptions',
    order: 10,
    surfaces: ['discussion-list-empty'],
    isVisible: ({ isFollowingPage }) => Boolean(isFollowingPage),
    resolve: () => ({
      text: '你还没有关注任何讨论。',
    }),
  })

  forum.uiCopy({
    key: 'discussion-list-following-hero-pill',
    moduleId: 'subscriptions',
    order: 479,
    surfaces: ['discussion-list-following-hero-pill'],
    resolve: () => ({
      text: '关注中',
    }),
  })

  forum.uiCopy({
    key: 'discussion-list-following-hero-title',
    moduleId: 'subscriptions',
    order: 479,
    surfaces: ['discussion-list-following-hero-title'],
    resolve: () => ({
      text: '关注的讨论',
    }),
  })

  forum.uiCopy({
    key: 'discussion-list-following-hero-description',
    moduleId: 'subscriptions',
    order: 479,
    surfaces: ['discussion-list-following-hero-description'],
    resolve: () => ({
      text: '这里会显示你已关注、并在后续收到新回复通知的讨论。',
    }),
  })

  forum.uiCopy({
    key: 'mobile-drawer-following',
    moduleId: 'subscriptions',
    order: 520,
    surfaces: ['mobile-drawer-following'],
    resolve: () => ({
      text: '关注中',
    }),
  })

  forum.discussionAction({
    key: 'toggle-subscription',
    moduleId: 'subscriptions',
    order: 20,
    surfaces: ['discussion-sidebar', 'discussion-menu', 'discussion-mobile-primary'],
    isVisible: ({ authStore, isSuspended }) => Boolean(authStore?.isAuthenticated) && !isSuspended,
    resolve: ({ pendingDiscussionActions, discussion }) => {
      const actionPending = Boolean(pendingDiscussionActions?.['toggle-subscription'])
      const isSubscribed = isDiscussionSubscribed(discussion)
      return {
        key: 'toggle-subscription',
        label: getUiCopy({
          surface: 'discussion-action-toggle-subscription-label',
          actionPending,
          isSubscribed,
        })?.text || getSubscriptionActionLabel(discussion, { pending: actionPending }),
        icon: isSubscribed ? 'fas fa-bell-slash' : 'far fa-star',
        description: getUiCopy({
          surface: 'discussion-action-toggle-subscription-description',
          isSubscribed,
        })?.text || getSubscriptionActionDescription(discussion),
        disabled: actionPending,
        disabledReason: actionPending
          ? (getUiCopy({
              surface: 'discussion-action-toggle-subscription-disabled',
            })?.text || '正在提交关注状态，请稍候。')
          : '',
        active: isSubscribed,
        order: 20,
      }
    },
  })

  forum.discussionActionHandler({
    key: 'toggle-subscription',
    moduleId: 'subscriptions',
    order: 10,
    handle: handleToggleSubscription,
  })

  forum.discussionStateBadge({
    key: 'subscribed',
    moduleId: 'subscriptions',
    order: 40,
    surfaces: ['discussion-list-item'],
    isVisible: ({ discussion }) => isDiscussionSubscribed(discussion),
    resolve: () => ({
      label: '已关注',
      tone: 'soft-primary',
    }),
  })

  forum.uiCopy({
    key: 'discussion-action-toggle-subscription-label',
    moduleId: 'subscriptions',
    order: 479,
    surfaces: ['discussion-action-toggle-subscription-label'],
    resolve: ({ actionPending, isSubscribed }) => ({
      text: actionPending ? '提交中...' : (isSubscribed ? '取消关注' : '关注讨论'),
    }),
  })

  forum.uiCopy({
    key: 'discussion-action-toggle-subscription-description',
    moduleId: 'subscriptions',
    order: 479,
    surfaces: ['discussion-action-toggle-subscription-description'],
    resolve: ({ isSubscribed }) => ({
      text: isSubscribed ? '停止接收这条讨论后续回复通知。' : '接收这条讨论后续回复通知。',
    }),
  })

  forum.uiCopy({
    key: 'discussion-action-toggle-subscription-disabled',
    moduleId: 'subscriptions',
    order: 479,
    surfaces: ['discussion-action-toggle-subscription-disabled'],
    resolve: () => ({
      text: '正在提交关注状态，请稍候。',
    }),
  })

  forum.stateBlock({
    key: 'discussion-sidebar-subscribed',
    moduleId: 'subscriptions',
    order: 20,
    surfaces: ['discussion-sidebar-action-notice'],
    isVisible: ({ authStore, discussion }) => Boolean(authStore?.isAuthenticated && isDiscussionSubscribed(discussion)),
    resolve: () => ({
      text: '你会收到这条讨论后续回复的通知。',
    }),
  })

  forum.runtime({
    key: 'follow-after-reply',
    moduleId: 'subscriptions',
    order: 10,
    onReplyCreated({ authStore }) {
      if (!shouldFollowAfterReply(authStore?.user)) {
        return null
      }
      return {
        discussionPatch: {
          is_subscribed: true,
        },
      }
    },
  })
}

async function handleToggleSubscription({
  discussion,
  patchDiscussion,
  setDiscussionActionPending,
  showActionError,
}) {
  if (!discussion?.id) {
    return
  }

  const isSubscribed = isDiscussionSubscribed(discussion)
  setDiscussionActionPending?.('toggle-subscription', true)
  try {
    if (isSubscribed) {
      await api.delete(`/discussions/${discussion.id}/subscribe`)
      patchDiscussion?.({ is_subscribed: false })
    } else {
      await api.post(`/discussions/${discussion.id}/subscribe`)
      patchDiscussion?.({ is_subscribed: true })
    }
  } catch (error) {
    console.error('更新关注状态失败:', error)
    await showActionError?.('更新关注', error)
  } finally {
    setDiscussionActionPending?.('toggle-subscription', false)
  }
}
