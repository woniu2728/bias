import {
  ResourceNormalizer } from '@bias/core'
import { formatRelativeTime } from '@bias/core'
import {
  createUiTextCopy,
  extendForum,
  getUiCopy
} from '@bias/forum'
import { normalizeDiscussion, registerStartDiscussionProvider } from '@bias/discussions'
import { buildUserPath } from '@bias/users'
import DiscussionComposer from './DiscussionComposer.vue'
import {
  getDiscussionListFilterHeroDescriptionText,
  getDiscussionListFilterHeroTitleText,
  getDiscussionListFilterLabelText,
  resolveDiscussionListPageMetaDescription,
  resolveDiscussionListPageMetaTitle,
} from './discussionList.js'
import DiscussionGenericEventPostItem from './components/DiscussionGenericEventPostItem.vue'
import DiscussionHiddenPostItem from './components/DiscussionHiddenPostItem.vue'
import DiscussionLockedPostItem from './components/DiscussionLockedPostItem.vue'
import DiscussionPostItem from './components/DiscussionPostItem.vue'
import DiscussionRenamedPostItem from './components/DiscussionRenamedPostItem.vue'
import DiscussionStickyPostItem from './components/DiscussionStickyPostItem.vue'
import PostHiddenPostItem from './components/PostHiddenPostItem.vue'

export const extend = [
  new ResourceNormalizer()
    .add('discussions', normalizeDiscussion)
    .add('discussion', normalizeDiscussion),
  extendForum('discussions', registerDiscussionsForum),
]

function registerDiscussionsForum(forum) {
  registerDiscussionPostTypes(forum)
  registerDiscussionNavigation(forum)
  registerDiscussionNotifications(forum)
  registerDiscussionPresentation(forum)
  registerDiscussionStates(forum)
  registerDiscussionActions(forum)
  registerDiscussionComposer(forum)
  registerDiscussionListHero(forum)
  registerDiscussionCopy(forum)
}

function registerDiscussionPostTypes(forum) {
  forum
    .postType('comment', {
      label: '普通回复',
      component: DiscussionPostItem,
      isDefault: true,
      order: 10,
    })
    .postType('discussionRenamed', {
      label: '讨论改标题',
      component: DiscussionRenamedPostItem,
      order: 20,
    })
    .postType('discussionLocked', {
      label: '讨论锁定状态变更',
      component: DiscussionLockedPostItem,
      order: 30,
    })
    .postType('discussionSticky', {
      label: '讨论置顶状态变更',
      component: DiscussionStickyPostItem,
      order: 40,
    })
    .postType('discussionHidden', {
      label: '讨论隐藏状态变更',
      component: DiscussionHiddenPostItem,
      order: 60,
    })
    .postType('postHidden', {
      label: '回复隐藏状态变更',
      component: PostHiddenPostItem,
      order: 130,
    })
    .postType('event', {
      label: '系统事件',
      component: DiscussionGenericEventPostItem,
      order: 999,
    })
}

function registerDiscussionNavigation(forum) {
  forum
    .navSection({
      key: 'primary',
      title: '',
      order: 10,
    })
    .navItem({
      key: 'home',
      moduleId: 'discussions',
      to: '/',
      icon: 'far fa-comments',
      label: '全部讨论',
      description: '查看全站最新讨论流。',
      section: 'primary',
      order: 10,
      surfaces: ['primary-nav', 'discussion-sidebar', 'mobile-drawer'],
    })
    .headerItem({
      key: 'mobile-drawer-start-discussion',
      moduleId: 'discussions',
      placement: 'mobile-drawer-actions',
      order: 20,
      icon: 'fas fa-pen-to-square',
      label: '发起讨论',
      tone: 'primary',
      isVisible: ({ authStore }) => Boolean(authStore?.canStartDiscussion),
      onClick: ({ startDiscussion }) => startDiscussion?.({
        source: 'mobile-drawer',
      }),
    })
    .headerItem({
      key: 'mobile-header-start-discussion',
      moduleId: 'discussions',
      placement: 'mobile-header-right-action',
      order: 20,
      actionType: 'compose-discussion',
      icon: 'fas fa-pen-to-square',
      label: () => getUiCopy({
        surface: 'header-mobile-right-action-label',
        actionType: 'compose-discussion',
      })?.text || '发起讨论',
      isVisible: ({ authStore }) => Boolean(authStore?.isAuthenticated && authStore?.canStartDiscussion),
      onClick: ({ startDiscussion }) => startDiscussion?.({
        source: 'mobile-header',
      }),
    })
}

function registerDiscussionNotifications(forum) {
  forum
    .notificationRenderer({
      type: 'discussionCreated',
      key: 'discussionCreated',
      moduleId: 'discussions',
      label: '发起讨论',
      icon: 'fas fa-pen',
      navigationScope: 'discussion',
      groupLabel: '讨论动态',
      order: 110,
      getText(notification) {
        const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
        const discussionTitle = notification?.data?.discussion_title || ''
        return `${fromUser} 发起了新讨论 "${discussionTitle}"`
      },
    })
    .notificationRenderer({
      type: 'postCreated',
      key: 'postCreated',
      moduleId: 'posts',
      label: '发表回复',
      icon: 'fas fa-message',
      navigationScope: 'post',
      groupLabel: '讨论动态',
      order: 120,
      getText(notification) {
        const fromUser = notification?.from_user?.display_name || notification?.from_user?.username || '有人'
        return `${fromUser} 发表了新回复`
      },
    })
}

function registerDiscussionPresentation(forum) {
  forum
    .discussionBadge({
      key: 'sticky',
      moduleId: 'discussions',
      order: 10,
      isVisible: ({ discussion }) => Boolean(discussion?.is_sticky),
      resolve: () => ({
        className: 'badge-pinned',
        icon: 'fas fa-thumbtack',
        title: '置顶',
      }),
    })
    .discussionBadge({
      key: 'locked',
      moduleId: 'discussions',
      order: 20,
      isVisible: ({ discussion }) => Boolean(discussion?.is_locked),
      resolve: () => ({
        className: 'badge-locked',
        icon: 'fas fa-lock',
        title: '锁定',
      }),
    })
    .discussionBadge({
      key: 'hidden',
      moduleId: 'discussions',
      order: 30,
      surfaces: ['hero'],
      isVisible: ({ discussion }) => Boolean(discussion?.is_hidden),
      resolve: () => ({
        className: 'badge-hidden',
        label: '隐藏',
      }),
    })
    .heroMeta({
      key: 'discussion-author',
      moduleId: 'discussions',
      order: 10,
      surfaces: ['discussion-hero'],
      isVisible: ({ discussion }) => Boolean(discussion?.user),
      resolve: ({ discussion }) => ({
        icon: 'far fa-user',
        text: discussion.user?.display_name || discussion.user?.username || '未知用户',
        to: buildUserPath(discussion.user),
      }),
    })
    .heroMeta({
      key: 'discussion-created-at',
      moduleId: 'discussions',
      order: 20,
      surfaces: ['discussion-hero'],
      isVisible: ({ discussion }) => Boolean(discussion?.created_at),
      resolve: ({ discussion }) => ({
        icon: 'far fa-clock',
        text: `发布于 ${formatRelativeTime(discussion.created_at)}`,
        title: discussion.created_at,
      }),
    })
    .heroMeta({
      key: 'discussion-last-posted-at',
      moduleId: 'discussions',
      order: 30,
      surfaces: ['discussion-hero'],
      isVisible: ({ discussion }) => Boolean(discussion?.last_posted_at),
      resolve: ({ discussion }) => ({
        icon: 'fas fa-reply',
        text: `最后回复 ${formatRelativeTime(discussion.last_posted_at)}`,
        title: discussion.last_posted_at,
      }),
    })
    .heroMeta({
      key: 'discussion-comment-count',
      moduleId: 'posts',
      order: 40,
      surfaces: ['discussion-hero'],
      isVisible: ({ discussion }) => Number(discussion?.comment_count || 0) > 0,
      resolve: ({ discussion }) => ({
        icon: 'far fa-comment',
        text: `${discussion.comment_count} 条回复`,
      }),
    })
    .discussionStateBadge({
      key: 'unread',
      moduleId: 'discussions',
      order: 30,
      surfaces: ['discussion-list-item'],
      isVisible: ({ discussion }) => Boolean(discussion?.is_unread && Number(discussion?.unread_count || 0) > 0),
      resolve: ({ discussion }) => ({
        label: `${discussion.unread_count} 条未读`,
        tone: 'primary',
      }),
    })
}

function registerDiscussionStates(forum) {
  forum
    .discussionReplyState({
      key: 'suspended',
      moduleId: 'discussions',
      order: 10,
      surfaces: ['discussion-reply'],
      isVisible: ({ authStore, isSuspended }) => Boolean(authStore?.isAuthenticated && isSuspended),
      resolve: ({ suspensionNotice }) => ({
        kind: 'notice',
        tone: 'warning',
        message: suspensionNotice,
      }),
    })
    .discussionReplyState({
      key: 'composer',
      moduleId: 'discussions',
      order: 20,
      surfaces: ['discussion-reply'],
      isVisible: ({ authStore, discussion }) => Boolean(authStore?.isAuthenticated && discussion?.can_reply),
      resolve: ({ hasActiveComposer }) => ({
        kind: 'composer',
        actionLabel: hasActiveComposer ? '继续编辑回复' : '发表回复',
        hint: hasActiveComposer ? '已有未发布内容' : '',
      }),
    })
    .discussionReplyState({
      key: 'locked',
      moduleId: 'discussions',
      order: 30,
      surfaces: ['discussion-reply'],
      isVisible: ({ discussion }) => Boolean(discussion?.is_locked),
      resolve: () => ({
        kind: 'notice',
        tone: 'warning',
        message: '此讨论已被锁定，无法回复',
      }),
    })
    .discussionReplyState({
      key: 'no-permission',
      moduleId: 'discussions',
      order: 60,
      surfaces: ['discussion-reply'],
      isVisible: ({ authStore }) => Boolean(authStore?.isAuthenticated),
      resolve: () => ({
        kind: 'notice',
        tone: 'warning',
        message: '当前没有在此讨论下回复的权限',
      }),
    })
    .discussionReplyState({
      key: 'guest',
      moduleId: 'discussions',
      order: 70,
      surfaces: ['discussion-reply'],
      resolve: () => ({
        kind: 'login',
        tone: 'warning',
        message: '后才能回复',
        linkLabel: '登录',
        to: '/login',
      }),
    })
    .emptyState({
      key: 'discussion-list-my-empty',
      moduleId: 'discussions',
      order: 20,
      surfaces: ['discussion-list-empty'],
      isVisible: ({ listFilter }) => listFilter === 'my',
      resolve: () => ({
        text: '你还没有发起任何讨论。',
      }),
    })
    .emptyState({
      key: 'discussion-list-unread-empty',
      moduleId: 'discussions',
      order: 30,
      surfaces: ['discussion-list-empty'],
      isVisible: ({ listFilter }) => listFilter === 'unread',
      resolve: () => ({
        text: '当前没有未读讨论。',
      }),
    })
    .emptyState({
      key: 'discussion-list-default-empty',
      moduleId: 'discussions',
      order: 50,
      surfaces: ['discussion-list-empty'],
      isVisible: () => true,
      resolve: () => ({
        text: '暂无讨论。',
      }),
    })
    .pageState({
      key: 'discussion-detail-loading',
      moduleId: 'discussions',
      order: 10,
      surfaces: ['discussion-detail-loading'],
      isVisible: ({ loading }) => Boolean(loading),
      resolve: () => ({
        text: '加载中...',
      }),
    })
    .pageState({
      key: 'discussion-detail-not-found',
      moduleId: 'discussions',
      order: 20,
      surfaces: ['discussion-detail-not-found'],
      isVisible: ({ loading, discussion }) => !loading && !discussion,
      resolve: () => ({
        text: '讨论不存在',
      }),
    })
    .stateBlock({
      key: 'discussion-list-loading',
      moduleId: 'discussions',
      order: 10,
      surfaces: ['discussion-list-loading'],
      isVisible: ({ loading }) => Boolean(loading),
      resolve: () => ({
        text: '正在加载讨论...',
      }),
    })
    .stateBlock({
      key: 'discussion-sidebar-active-draft',
      moduleId: 'posts',
      order: 10,
      surfaces: ['discussion-sidebar-action-notice'],
      isVisible: ({ authStore, hasActiveComposer }) => Boolean(authStore?.isAuthenticated && hasActiveComposer),
      resolve: () => ({
        text: getUiCopy({
          surface: 'discussion-sidebar-active-draft',
        })?.text || '当前讨论已有未发布回复草稿。',
      }),
    })
    .stateBlock({
      key: 'discussion-sidebar-locked',
      moduleId: 'discussions',
      order: 30,
      surfaces: ['discussion-sidebar-action-notice'],
      isVisible: ({ authStore, discussion }) => Boolean(authStore?.isAuthenticated && discussion?.is_locked),
      resolve: () => ({
        text: getUiCopy({
          surface: 'discussion-sidebar-locked',
        })?.text || '当前讨论已锁定，暂时无法继续回复。',
      }),
    })
    .stateBlock({
      key: 'discussion-sidebar-suspended',
      moduleId: 'users',
      order: 40,
      surfaces: ['discussion-sidebar-action-notice'],
      isVisible: ({ authStore, isSuspended }) => Boolean(authStore?.isAuthenticated && isSuspended),
      resolve: ({ suspensionNotice }) => ({
        tone: 'warning',
        text: suspensionNotice || '',
      }),
    })
}

function registerDiscussionActions(forum) {
  forum
    .discussionAction({
      key: 'edit',
      moduleId: 'discussions',
      order: 30,
      surfaces: ['discussion-menu'],
      isVisible: ({ canEditDiscussion }) => Boolean(canEditDiscussion),
      resolve: () => ({
        key: 'edit',
        label: getUiCopy({
          surface: 'discussion-action-edit-label',
        })?.text || '编辑讨论',
        icon: 'fas fa-pen',
        description: getUiCopy({
          surface: 'discussion-action-edit-description',
        })?.text || '修改标题和正文。',
        order: 30,
      }),
    })
    .discussionAction({
      key: 'toggle-pin',
      moduleId: 'discussions',
      order: 40,
      surfaces: ['discussion-menu'],
      isVisible: ({ canModerateDiscussionSettings }) => Boolean(canModerateDiscussionSettings),
      resolve: ({ discussion }) => ({
        key: 'toggle-pin',
        label: getUiCopy({
          surface: 'discussion-action-toggle-pin-label',
          isSticky: discussion.is_sticky,
        })?.text || (discussion.is_sticky ? '取消置顶' : '置顶讨论'),
        icon: 'fas fa-thumbtack',
        description: getUiCopy({
          surface: 'discussion-action-toggle-pin-description',
          isSticky: discussion.is_sticky,
        })?.text || (discussion.is_sticky ? '把讨论恢复为普通排序。' : '把讨论固定到列表更靠前的位置。'),
        confirm: discussion.is_sticky ? null : {
          title: getUiCopy({
            surface: 'discussion-action-toggle-pin-confirm-title',
          })?.text || '置顶讨论',
          message: getUiCopy({
            surface: 'discussion-action-toggle-pin-confirm-message',
          })?.text || '确定将这条讨论置顶吗？',
          confirmText: getUiCopy({
            surface: 'discussion-action-toggle-pin-confirm-confirm',
          })?.text || '置顶讨论',
          cancelText: getUiCopy({
            surface: 'discussion-action-confirm-cancel',
          })?.text || '取消',
          tone: 'primary',
        },
        order: 40,
      }),
    })
    .discussionAction({
      key: 'toggle-lock',
      moduleId: 'discussions',
      order: 50,
      surfaces: ['discussion-menu'],
      isVisible: ({ canModerateDiscussionSettings }) => Boolean(canModerateDiscussionSettings),
      resolve: ({ discussion }) => ({
        key: 'toggle-lock',
        label: getUiCopy({
          surface: 'discussion-action-toggle-lock-label',
          isLocked: discussion.is_locked,
        })?.text || (discussion.is_locked ? '解除锁定' : '锁定讨论'),
        icon: discussion.is_locked ? 'fas fa-lock-open' : 'fas fa-lock',
        description: getUiCopy({
          surface: 'discussion-action-toggle-lock-description',
          isLocked: discussion.is_locked,
        })?.text || (discussion.is_locked ? '恢复普通用户回复能力。' : '阻止普通用户继续回复。'),
        confirm: discussion.is_locked ? null : {
          title: getUiCopy({
            surface: 'discussion-action-toggle-lock-confirm-title',
          })?.text || '锁定讨论',
          message: getUiCopy({
            surface: 'discussion-action-toggle-lock-confirm-message',
          })?.text || '确定锁定当前讨论并阻止普通用户继续回复吗？',
          confirmText: getUiCopy({
            surface: 'discussion-action-toggle-lock-confirm-confirm',
          })?.text || '锁定讨论',
          cancelText: getUiCopy({
            surface: 'discussion-action-confirm-cancel',
          })?.text || '取消',
          tone: 'warning',
        },
        order: 50,
      }),
    })
    .discussionAction({
      key: 'toggle-hide',
      moduleId: 'discussions',
      order: 60,
      surfaces: ['discussion-menu'],
      isVisible: ({ canModerateDiscussionSettings }) => Boolean(canModerateDiscussionSettings),
      resolve: ({ discussion }) => ({
        key: 'toggle-hide',
        label: getUiCopy({
          surface: 'discussion-action-toggle-hide-label',
          isHidden: discussion.is_hidden,
        })?.text || (discussion.is_hidden ? '恢复显示' : '隐藏讨论'),
        icon: discussion.is_hidden ? 'fas fa-eye' : 'fas fa-eye-slash',
        description: getUiCopy({
          surface: 'discussion-action-toggle-hide-description',
          isHidden: discussion.is_hidden,
        })?.text || (discussion.is_hidden ? '重新让讨论出现在前台列表。' : '临时从前台列表隐藏当前讨论。'),
        confirm: {
          title: getUiCopy({
            surface: 'discussion-action-toggle-hide-confirm-title',
            isHidden: discussion.is_hidden,
          })?.text || (discussion.is_hidden ? '恢复显示' : '隐藏讨论'),
          message: getUiCopy({
            surface: 'discussion-action-toggle-hide-confirm-message',
            isHidden: discussion.is_hidden,
          })?.text || (discussion.is_hidden ? '确定恢复显示当前讨论吗？' : '确定从前台列表隐藏当前讨论吗？'),
          confirmText: getUiCopy({
            surface: 'discussion-action-toggle-hide-confirm-confirm',
            isHidden: discussion.is_hidden,
          })?.text || (discussion.is_hidden ? '恢复显示' : '隐藏讨论'),
          cancelText: getUiCopy({
            surface: 'discussion-action-confirm-cancel',
          })?.text || '取消',
          tone: discussion.is_hidden ? 'primary' : 'warning',
        },
        order: 60,
      }),
    })
    .discussionAction({
      key: 'delete',
      moduleId: 'discussions',
      order: 70,
      surfaces: ['discussion-menu'],
      isVisible: ({ canModerateDiscussionSettings }) => Boolean(canModerateDiscussionSettings),
      resolve: () => ({
        key: 'delete',
        label: getUiCopy({
          surface: 'discussion-action-delete-label',
        })?.text || '删除讨论',
        icon: 'fas fa-trash',
        description: getUiCopy({
          surface: 'discussion-action-delete-description',
        })?.text || '永久删除当前讨论及其回复。',
        tone: 'danger',
        confirm: {
          title: getUiCopy({
            surface: 'discussion-action-delete-confirm-title',
          })?.text || '删除讨论',
          message: getUiCopy({
            surface: 'discussion-action-delete-confirm-message',
          })?.text || '确定要删除这个讨论吗？此操作不可恢复。',
          confirmText: getUiCopy({
            surface: 'discussion-action-delete-confirm-confirm',
          })?.text || '删除',
          cancelText: getUiCopy({
            surface: 'discussion-action-confirm-cancel',
          })?.text || '取消',
          tone: 'danger',
        },
        order: 70,
      }),
    })
}

function registerDiscussionComposer(forum) {
  registerStartDiscussionProvider({
    key: 'discussion-composer-start',
    moduleId: 'discussions',
    order: 10,
    start({
      authStore,
      composerStore,
      router,
      redirectToLogin = true,
      extensionState = {},
      source = 'unknown',
    }) {
      if (!authStore?.isAuthenticated) {
        if (redirectToLogin) {
          router?.push?.('/login')
        }
        return false
      }

      if (!authStore?.canStartDiscussion) return false

      composerStore?.openDiscussionComposer?.({
        extensions: extensionState,
        source,
      })
      return true
    },
  })

  forum
    .composerHost({
      key: 'discussion-composer',
      moduleId: 'discussions',
      order: 10,
      component: DiscussionComposer,
    })
    .composerTool({
      key: 'discussion-template',
      moduleId: 'discussions',
      order: 15,
      isVisible: ({ type }) => type === 'discussion',
      resolve: () => ({
        title: '插入讨论模板',
        icon: 'fas fa-clipboard-list',
        async run({ content, insertText, selectionStart, selectionEnd }) {
          const template = [
            '## 背景',
            '',
            '简要说明当前问题或主题背景。',
            '',
            '## 现象',
            '',
            '描述你观察到的结果、错误或争议点。',
            '',
            '## 期望',
            '',
            '说明希望获得的帮助、答案或改进方向。',
          ].join('\n')

          const prefix = content.trim() ? '\n\n' : ''
          const replacement = `${prefix}${template}`
          const cursor = selectionStart + replacement.length
          await insertText(replacement, {
            start: selectionStart,
            end: selectionEnd,
            cursor,
          })
        },
      }),
    })
    .composerSubmitGuard({
      key: 'discussion-start-permission',
      moduleId: 'discussions',
      order: 20,
      isVisible: ({ type, mode }) => type === 'discussion' && mode === 'create',
      check: ({ authStore }) => {
        if (authStore?.canStartDiscussion) return null
        return {
          tone: 'error',
          message: '当前账号没有发起讨论的权限。',
        }
      },
    })
    .composerSecondaryAction({
      key: 'save-discussion-draft',
      moduleId: 'discussions',
      order: 5,
      isVisible: ({ type, isEditing, hasDraftContent, submitting, uploading }) => {
        return type === 'discussion' && !isEditing && Boolean(hasDraftContent) && !submitting && !uploading
      },
      resolve: () => ({
        label: '保存草稿',
        onClick: async ({ composerStore }) => {
          window.dispatchEvent(new CustomEvent('bias:composer-save-request', {
            detail: {
              composerType: 'discussion',
              requestId: composerStore?.current?.requestId || 0,
            },
          }))
        },
      }),
    })
    .composerSecondaryAction({
      key: 'clear-discussion-draft',
      moduleId: 'discussions',
      order: 10,
      isVisible: ({ type, isEditing, hasDraftContent }) => type === 'discussion' && !isEditing && Boolean(hasDraftContent),
      resolve: ({ draftSavedAt }) => ({
        label: '清除草稿',
        action: 'clear-draft',
        confirm: draftSavedAt ? {
          title: '清除讨论草稿',
          message: '确定要清除当前讨论草稿吗？',
          confirmText: '清除草稿',
          cancelText: '取消',
          tone: 'danger',
        } : null,
      }),
    })
    .composerStatusItem({
      key: 'discussion-editing',
      moduleId: 'discussions',
      order: 20,
      isVisible: ({ type, isEditing, minimized }) => type === 'discussion' && Boolean(isEditing) && !minimized,
      resolve: () => ({
        label: '状态',
        value: '编辑讨论',
      }),
    })
    .composerDraftMeta({
      key: 'discussion-draft-saved-at',
      moduleId: 'discussions',
      order: 30,
      isVisible: ({ type, draftSavedAt, minimized }) => type === 'discussion' && Boolean(draftSavedAt) && !minimized,
      resolve: ({ draftSavedAt, formatDraftTime }) => ({
        label: '草稿',
        value: `保存于 ${formatDraftTime?.(draftSavedAt) || draftSavedAt}`,
      }),
    })
}

function registerDiscussionListHero(forum) {
  forum.discussionListHero({
    key: 'discussion-list-filter-hero',
    moduleId: 'discussions',
    order: 100,
    surfaces: ['discussion-list-hero'],
    isVisible: ({ activeFilterCode, contextSubject }) => !contextSubject && String(activeFilterCode || 'all') !== 'all',
    resolve: ({ activeFilterCode }) => ({
      pill: getUiCopy({
        surface: 'discussion-list-filter-hero-pill',
        listFilter: activeFilterCode,
      })?.text || getDiscussionListFilterLabelText(activeFilterCode),
      title: getUiCopy({
        surface: 'discussion-list-filter-hero-title',
        listFilter: activeFilterCode,
      })?.text || getDiscussionListFilterHeroTitleText(activeFilterCode),
      description: getUiCopy({
        surface: 'discussion-list-filter-hero-description',
        listFilter: activeFilterCode,
      })?.text || getDiscussionListFilterHeroDescriptionText(activeFilterCode),
      icon: resolveDiscussionListFilterHeroIcon(activeFilterCode),
      style: {
        '--discussion-list-hero-color': 'var(--forum-primary-color)',
      },
    }),
  })
}

function resolveDiscussionListFilterHeroIcon(filterCode) {
  switch (String(filterCode || 'all').trim()) {
    case 'unread':
      return 'fas fa-inbox'
    case 'my':
      return 'fas fa-user-pen'
    default:
      return 'fas fa-bell'
  }
}

function registerDiscussionCopy(forum) {
  for (const definition of discussionCopyDefinitions()) {
    forum.uiCopy({
      moduleId: 'discussions',
      ...definition,
    })
  }
}

function discussionCopyDefinitions() {
  return [
    createUiTextCopy('discussion-create-title', 10, '正在打开讨论编辑器...'),
    createUiTextCopy('discussion-create-description', 20, '系统会自动切换到浮层编辑器。'),
    createUiTextCopy('home-hero-title', 479, 'Bias'),
    createUiTextCopy('home-hero-description', 479, '基于 Django 和 Vue 3 的现代化论坛'),
    createUiTextCopy('home-browse-discussions', 479, '浏览讨论'),
    createUiTextCopy('home-start-discussion', 479, '发起讨论'),
    createUiTextCopy('home-register-account', 479, '注册账号'),
    {
      key: 'start-discussion-button',
      order: 479,
      surfaces: ['start-discussion-button'],
      resolve: ({ hasContextSubject, subjectName }) => ({
        text: hasContextSubject && subjectName ? `在 ${subjectName} 下发起讨论` : '发起讨论',
      }),
    },
    createUiTextCopy('discussion-action-confirm-cancel', 479, '取消'),
    createUiTextCopy('discussion-action-confirm-default', 479, '继续'),
    {
      key: 'discussion-action-reply-label',
      order: 479,
      surfaces: ['discussion-action-reply-label'],
      resolve: ({ hasActiveComposer }) => ({
        text: hasActiveComposer ? '继续回复' : '回复讨论',
      }),
    },
    {
      key: 'discussion-action-reply-description',
      order: 479,
      surfaces: ['discussion-action-reply-description'],
      resolve: ({ hasActiveComposer }) => ({
        text: hasActiveComposer ? '继续当前未发布的回复草稿。' : '在当前讨论中开始撰写回复。',
      }),
    },
    createUiTextCopy('discussion-action-login-label', 479, '登录后回复'),
    createUiTextCopy('discussion-action-login-description', 479, '登录后才可以参与当前讨论。'),
    createUiTextCopy('discussion-action-edit-label', 479, '编辑讨论'),
    createUiTextCopy('discussion-action-edit-description', 479, '修改标题和正文。'),
    {
      key: 'discussion-action-toggle-pin-label',
      order: 479,
      surfaces: ['discussion-action-toggle-pin-label'],
      resolve: ({ isSticky }) => ({
        text: isSticky ? '取消置顶' : '置顶讨论',
      }),
    },
    {
      key: 'discussion-action-toggle-pin-description',
      order: 479,
      surfaces: ['discussion-action-toggle-pin-description'],
      resolve: ({ isSticky }) => ({
        text: isSticky ? '把讨论恢复为普通排序。' : '把讨论固定到列表更靠前的位置。',
      }),
    },
    createUiTextCopy('discussion-action-toggle-pin-confirm-title', 479, '置顶讨论'),
    createUiTextCopy('discussion-action-toggle-pin-confirm-message', 479, '确定将这条讨论置顶吗？'),
    createUiTextCopy('discussion-action-toggle-pin-confirm-confirm', 479, '置顶讨论'),
    {
      key: 'discussion-action-toggle-lock-label',
      order: 479,
      surfaces: ['discussion-action-toggle-lock-label'],
      resolve: ({ isLocked }) => ({
        text: isLocked ? '解除锁定' : '锁定讨论',
      }),
    },
    {
      key: 'discussion-action-toggle-lock-description',
      order: 479,
      surfaces: ['discussion-action-toggle-lock-description'],
      resolve: ({ isLocked }) => ({
        text: isLocked ? '恢复普通用户回复能力。' : '阻止普通用户继续回复。',
      }),
    },
    createUiTextCopy('discussion-action-toggle-lock-confirm-title', 479, '锁定讨论'),
    createUiTextCopy('discussion-action-toggle-lock-confirm-message', 479, '确定锁定当前讨论并阻止普通用户继续回复吗？'),
    createUiTextCopy('discussion-action-toggle-lock-confirm-confirm', 479, '锁定讨论'),
    {
      key: 'discussion-action-toggle-hide-label',
      order: 479,
      surfaces: ['discussion-action-toggle-hide-label'],
      resolve: ({ isHidden }) => ({
        text: isHidden ? '恢复显示' : '隐藏讨论',
      }),
    },
    {
      key: 'discussion-action-toggle-hide-description',
      order: 479,
      surfaces: ['discussion-action-toggle-hide-description'],
      resolve: ({ isHidden }) => ({
        text: isHidden ? '重新让讨论出现在前台列表。' : '临时从前台列表隐藏当前讨论。',
      }),
    },
    {
      key: 'discussion-action-toggle-hide-confirm-title',
      order: 479,
      surfaces: ['discussion-action-toggle-hide-confirm-title'],
      resolve: ({ isHidden }) => ({
        text: isHidden ? '恢复显示' : '隐藏讨论',
      }),
    },
    {
      key: 'discussion-action-toggle-hide-confirm-message',
      order: 479,
      surfaces: ['discussion-action-toggle-hide-confirm-message'],
      resolve: ({ isHidden }) => ({
        text: isHidden ? '确定恢复显示当前讨论吗？' : '确定从前台列表隐藏当前讨论吗？',
      }),
    },
    {
      key: 'discussion-action-toggle-hide-confirm-confirm',
      order: 479,
      surfaces: ['discussion-action-toggle-hide-confirm-confirm'],
      resolve: ({ isHidden }) => ({
        text: isHidden ? '恢复显示' : '隐藏讨论',
      }),
    },
    createUiTextCopy('discussion-action-delete-label', 479, '删除讨论'),
    createUiTextCopy('discussion-action-delete-description', 479, '永久删除当前讨论及其回复。'),
    createUiTextCopy('discussion-action-delete-confirm-title', 479, '删除讨论'),
    createUiTextCopy('discussion-action-delete-confirm-message', 479, '确定要删除这个讨论吗？此操作不可恢复。'),
    createUiTextCopy('discussion-action-delete-confirm-confirm', 479, '删除'),
    createUiTextCopy('discussion-sidebar-active-draft', 479, '当前讨论已有未发布回复草稿。'),
    createUiTextCopy('discussion-sidebar-locked', 479, '当前讨论已锁定，暂时无法继续回复。'),
    createUiTextCopy('discussion-sidebar-suspension-title', 479, '账号状态'),
    createUiTextCopy('discussion-sidebar-scrubber-start', 479, '原帖'),
    createUiTextCopy('discussion-sidebar-scrubber-end', 479, '现在'),
    createUiTextCopy('discussion-detail-suspension-alert-title', 479, '账号已被封禁'),
    {
      key: 'discussion-detail-suspension-notice',
      order: 479,
      surfaces: ['discussion-detail-suspension-notice'],
      resolve: ({ user, fallbackMessage, suspendedUntilText }) => {
        if (!user?.is_suspended) {
          return { text: '' }
        }

        if (user.suspend_message) {
          return {
            text: suspendedUntilText
              ? `账号已被封禁至 ${suspendedUntilText}。${user.suspend_message}`
              : `账号当前已被封禁。${user.suspend_message}`,
          }
        }

        return {
          text: suspendedUntilText
            ? `账号已被封禁至 ${suspendedUntilText}，${fallbackMessage}`
            : `账号当前已被封禁，${fallbackMessage}`,
        }
      },
    },
    {
      key: 'discussion-detail-action-error-title',
      order: 479,
      surfaces: ['discussion-detail-action-error-title'],
      resolve: ({ actionLabel }) => ({
        text: actionLabel ? `${actionLabel}失败` : '操作失败',
      }),
    },
    createUiTextCopy('discussion-detail-action-retry-message', 479, '请稍后重试'),
    createUiTextCopy('discussion-detail-unknown-time', 479, '未知时间'),
    {
      key: 'forum-action-menu-item-title',
      order: 479,
      surfaces: ['forum-action-menu-item-title'],
      resolve: ({ disabledReason }) => ({
        text: disabledReason || '',
      }),
    },
    {
      key: 'header-mobile-page-title',
      order: 479,
      surfaces: ['header-mobile-page-title'],
      resolve: ({ routeName, forumTitle, listFilter }) => ({
        text: routeName === 'home'
          ? getDiscussionListFilterLabelText(listFilter)
          : routeName === 'following'
            ? getDiscussionListFilterLabelText('following')
            : ({
              profile: '个人主页',
              'user-profile': '个人主页',
              search: '搜索结果',
              'discussion-detail': '讨论详情',
              login: '登录',
              register: '注册',
            })[routeName] || forumTitle || 'Bias',
      }),
    },
    {
      key: 'header-mobile-left-action-label',
      order: 479,
      surfaces: ['header-mobile-left-action-label'],
      resolve: ({ leftAction }) => ({
        text: leftAction === 'back' ? '返回上一页' : '打开导航菜单',
      }),
    },
    createUiTextCopy('discussion-list-sidebar-profile-link', 479, '我的主页'),
    {
      key: 'header-mobile-right-action-label',
      order: 479,
      surfaces: ['header-mobile-right-action-label'],
      resolve: ({ actionType }) => ({
        text: actionType === 'discussion-menu'
          ? '讨论操作菜单'
          : actionType === 'login'
            ? '登录'
            : '发起讨论',
      }),
    },
    {
      key: 'discussion-list-default-filter-label',
      order: 479,
      surfaces: ['discussion-list-default-filter-label'],
      resolve: ({ code }) => ({
        text: getDiscussionListFilterLabelText(code),
      }),
    },
    {
      key: 'discussion-list-action-failed-title',
      order: 479,
      surfaces: ['discussion-list-action-failed-title'],
      resolve: ({ actionType }) => ({
        text: actionType === 'refresh'
          ? '刷新失败'
          : actionType === 'mark-all-read'
            ? '标记已读失败'
            : actionType === 'load-more'
              ? '加载更多失败'
              : '操作失败',
      }),
    },
    createUiTextCopy('discussion-list-action-retry-message', 479, '请稍后重试'),
    {
      key: 'discussion-list-filter-hero-pill',
      order: 479,
      surfaces: ['discussion-list-filter-hero-pill'],
      resolve: ({ listFilter }) => ({
        text: getDiscussionListFilterLabelText(listFilter),
      }),
    },
    {
      key: 'discussion-list-filter-hero-title',
      order: 479,
      surfaces: ['discussion-list-filter-hero-title'],
      resolve: ({ listFilter }) => ({
        text: getDiscussionListFilterHeroTitleText(listFilter),
      }),
    },
    {
      key: 'discussion-list-filter-hero-description',
      order: 479,
      surfaces: ['discussion-list-filter-hero-description'],
      resolve: ({ listFilter }) => ({
        text: getDiscussionListFilterHeroDescriptionText(listFilter),
      }),
    },
    {
      key: 'discussion-list-page-meta-title',
      order: 479,
      surfaces: ['discussion-list-page-meta-title'],
      resolve: ({ listFilter, subjectName, searchQuery, hasSearchQuery }) => ({
        text: resolveDiscussionListPageMetaTitle({
          filterCode: listFilter,
          subjectName,
          searchQuery: hasSearchQuery ? searchQuery : '',
        }),
      }),
    },
    {
      key: 'discussion-list-page-meta-description',
      order: 479,
      surfaces: ['discussion-list-page-meta-description'],
      resolve: ({ listFilter, subjectName, subjectDescription, searchQuery, hasSearchQuery }) => ({
        text: resolveDiscussionListPageMetaDescription({
          filterCode: listFilter,
          subjectName,
          subjectDescription,
          searchQuery: hasSearchQuery ? searchQuery : '',
        }),
      }),
    },
    {
      key: 'discussion-event-post-number-title',
      order: 479,
      surfaces: ['discussion-event-post-number-title'],
      resolve: ({ postNumber }) => ({
        text: `跳转到第 ${postNumber} 楼`,
      }),
    },
    {
      key: 'discussion-event-target-post-number-title',
      order: 479,
      surfaces: ['discussion-event-target-post-number-title'],
      resolve: ({ targetPostNumber }) => ({
        text: `跳转到相关的第 ${targetPostNumber} 楼`,
      }),
    },
    {
      key: 'discussion-event-hidden-label',
      order: 479,
      surfaces: ['discussion-event-hidden-label'],
      resolve: ({ isHidden }) => ({
        text: isHidden ? '隐藏了该讨论' : '恢复显示该讨论',
      }),
    },
    {
      key: 'discussion-event-locked-label',
      order: 479,
      surfaces: ['discussion-event-locked-label'],
      resolve: ({ isLocked }) => ({
        text: isLocked ? '锁定了该讨论' : '解锁了该讨论',
      }),
    },
    {
      key: 'discussion-event-sticky-label',
      order: 479,
      surfaces: ['discussion-event-sticky-label'],
      resolve: ({ isSticky }) => ({
        text: isSticky ? '置顶了该讨论' : '取消了该讨论的置顶状态',
      }),
    },
    createUiTextCopy('discussion-event-renamed-from-label', 479, '将讨论标题从'),
    createUiTextCopy('discussion-event-renamed-to-label', 479, '改为'),
    createUiTextCopy('discussion-event-renamed-old-title-fallback', 479, '旧标题'),
    createUiTextCopy('discussion-event-renamed-new-title-fallback', 479, '新标题'),
    createUiTextCopy('discussion-generic-event-fallback-label', 479, '系统事件'),
    {
      key: 'discussion-post-number-title',
      order: 479,
      surfaces: ['discussion-post-number-title'],
      resolve: ({ postNumber }) => ({
        text: `跳转到第 ${postNumber} 楼`,
      }),
    },
    createUiTextCopy('discussion-post-edited-label', 479, '已编辑'),
    createUiTextCopy('discussion-post-reply-action', 479, '回复'),
    {
      key: 'discussion-list-item-created-at',
      order: 479,
      surfaces: ['discussion-list-item-created-at'],
      resolve: ({ relativeTime }) => ({
        text: `发起于 ${relativeTime}`,
      }),
    },
    {
      key: 'discussion-list-item-last-posted-at',
      order: 479,
      surfaces: ['discussion-list-item-last-posted-at'],
      resolve: ({ relativeTime }) => ({
        text: `最后回复 ${relativeTime}`,
      }),
    },
    createUiTextCopy('mobile-drawer-start-discussion', 500, '发起讨论'),
    createUiTextCopy('mobile-drawer-all-discussions', 510, '全部讨论'),
    createUiTextCopy('discussion-composer-title-placeholder', 580, '讨论标题'),
    createUiTextCopy('discussion-composer-content-placeholder', 590, '输入讨论内容... 支持 Markdown、@用户名 和代码块'),
    {
      key: 'discussion-composer-submit',
      order: 610,
      surfaces: ['discussion-composer-submit'],
      resolve: ({ submitting, uploading, isEditingDiscussion }) => ({
        text: submitting
          ? (isEditingDiscussion ? '保存中...' : '发布中...')
          : (uploading ? '上传中...' : (isEditingDiscussion ? '保存讨论' : '发布讨论')),
      }),
    },
    {
      key: 'discussion-composer-status-text',
      order: 611,
      surfaces: ['discussion-composer-status-text'],
      resolve: ({ hasDraftSavedAt, draftSavedAtText, isEditingDiscussion, selectedExtensionLabel }) => {
        if (hasDraftSavedAt) {
          return {
            text: `草稿保存于 ${draftSavedAtText}`,
          }
        }

        if (isEditingDiscussion) {
          return {
            text: '修改后将保存讨论内容。',
          }
        }

        if (selectedExtensionLabel) {
          return {
            text: `将发布到 ${selectedExtensionLabel}`,
          }
        }

        return {
          text: '支持 Markdown，可最小化继续编辑。',
        }
      },
    },
    {
      key: 'discussion-composer-minimized-summary',
      order: 612,
      surfaces: ['discussion-composer-minimized-summary'],
      resolve: ({ isEditingDiscussion, selectedExtensionLabel }) => ({
        text: isEditingDiscussion ? '编辑讨论' : (selectedExtensionLabel ? `新讨论 · ${selectedExtensionLabel}` : '发起讨论'),
      }),
    },
    {
      key: 'discussion-composer-heading',
      order: 613,
      surfaces: ['discussion-composer-heading'],
      resolve: ({ isEditingDiscussion }) => ({
        text: isEditingDiscussion ? '编辑讨论' : '发起讨论',
      }),
    },
    createUiTextCopy('discussion-composer-close-title', 614, '关闭发帖编辑器'),
    createUiTextCopy('discussion-composer-close-message', 615, '确定要关闭发帖编辑器吗？当前内容会保留在本地草稿中。'),
    createUiTextCopy('discussion-composer-close-confirm', 616, '关闭'),
    createUiTextCopy('discussion-composer-close-cancel', 617, '继续编辑'),
    {
      key: 'discussion-composer-draft-restored',
      order: 618,
      surfaces: ['discussion-composer-draft-restored'],
      resolve: ({ hasDraftSavedAt, draftSavedAtText }) => ({
        text: hasDraftSavedAt
          ? `已恢复你在 ${draftSavedAtText} 保存的讨论草稿。`
          : '已恢复本地讨论草稿。',
      }),
    },
    createUiTextCopy('discussion-composer-draft-restore-error', 619, '讨论草稿恢复失败，已保留当前编辑内容。'),
    createUiTextCopy('discussion-composer-draft-emptied', 620, '草稿已清空'),
    createUiTextCopy('discussion-composer-draft-saved', 621, '讨论草稿已保存。'),
    createUiTextCopy('discussion-composer-clear-draft-title', 622, '清除讨论草稿'),
    createUiTextCopy('discussion-composer-clear-draft-message', 623, '确定要清除当前讨论草稿吗？'),
    createUiTextCopy('discussion-composer-clear-draft-confirm', 624, '清除'),
    createUiTextCopy('discussion-composer-clear-draft-cancel', 625, '取消'),
    createUiTextCopy('discussion-composer-draft-cleared-local', 626, '已清除本地草稿。'),
    createUiTextCopy('discussion-composer-unsaved-exit-message', 626, '你有未发布的讨论内容。确定要离开当前页面吗？'),
    createUiTextCopy('discussion-composer-updated-title', 629, '讨论已更新'),
    createUiTextCopy('discussion-composer-updated-message', 630, '新的讨论内容已经保存。'),
    createUiTextCopy('discussion-detail-load-previous', 1130, '加载前面的回复'),
    createUiTextCopy('discussion-detail-load-more', 1160, '加载更多回复'),
    createUiTextCopy('discussion-detail-load-posts-loading', 1150, '正在加载回复...'),
    createUiTextCopy('discussion-detail-unread-divider', 1160, '从这里开始是未读回复'),
    {
      key: 'discussion-list-toolbar-mark-read',
      order: 1190,
      surfaces: ['discussion-list-toolbar-mark-read'],
      resolve: ({ markingAllRead }) => ({
        text: markingAllRead ? '正在标记已读...' : '全部标记为已读',
      }),
    },
    {
      key: 'discussion-list-toolbar-refresh',
      order: 1200,
      surfaces: ['discussion-list-toolbar-refresh'],
      resolve: ({ refreshing }) => ({
        text: refreshing ? '正在刷新...' : '刷新',
      }),
    },
    {
      key: 'discussion-list-toolbar-sort-label',
      order: 1200,
      surfaces: ['discussion-list-toolbar-sort-label'],
      resolve: ({ code }) => ({
        text: code === 'newest' ? '新主题' : code === 'top' ? '热门' : '最新活跃',
      }),
    },
    createUiTextCopy('discussion-list-refreshing', 1200, '正在刷新讨论'),
    createUiTextCopy('discussion-list-load-more', 1200, '加载更多讨论'),
    createUiTextCopy('discussion-list-loading-more', 1200, '正在加载讨论...'),
    {
      key: 'discussion-reply-typing-notice',
      order: 1321,
      surfaces: ['discussion-reply-typing-notice'],
      resolve: ({ count, usernames }) => {
        const normalizedNames = Array.isArray(usernames)
          ? usernames.map(value => String(value || '').trim()).filter(Boolean)
          : []

        if (!normalizedNames.length || !count) {
          return { text: '' }
        }
        if (count === 1) {
          return { text: `${normalizedNames[0]} 正在输入...` }
        }
        if (count === 2) {
          return { text: `${normalizedNames[0]}、${normalizedNames[1]} 正在输入...` }
        }
        return { text: `${normalizedNames[0]} 等 ${count} 人正在输入...` }
      },
    },
  ]
}
