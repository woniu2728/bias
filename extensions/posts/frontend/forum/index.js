import {
  createUiTextCopy,
  extendForum,
  getUiCopy
} from '@bias/forum'
import { ResourceNormalizer } from '@bias/core'
import { normalizePost } from '@bias/posts'
import PostComposer from './PostComposer.vue'

export const extend = [
  new ResourceNormalizer()
    .add('posts', normalizePost)
    .add('post', normalizePost),
  extendForum('posts', registerPostsForum),
]

function registerPostsForum(forum) {
  registerDiscussionReplyActions(forum)
  registerPostActions(forum)
  registerPostComposer(forum)
  registerPostsCopy(forum)
}

function registerDiscussionReplyActions(forum) {
  forum
    .discussionAction({
      key: 'reply',
      moduleId: 'posts',
      order: 10,
      surfaces: ['discussion-sidebar', 'discussion-menu'],
      isVisible: ({ canReplyFromMenu }) => Boolean(canReplyFromMenu),
      resolve: ({ hasActiveComposer }) => ({
        key: 'reply',
        label: getUiCopy({
          surface: 'discussion-action-reply-label',
          hasActiveComposer,
        })?.text || (hasActiveComposer ? '继续回复' : '回复讨论'),
        icon: 'fas fa-reply',
        description: getUiCopy({
          surface: 'discussion-action-reply-description',
          hasActiveComposer,
        })?.text || (hasActiveComposer ? '继续当前未发布的回复草稿。' : '在当前讨论中开始撰写回复。'),
        order: 10,
      }),
    })
    .discussionAction({
      key: 'login',
      moduleId: 'posts',
      order: 10,
      surfaces: ['discussion-sidebar', 'discussion-menu'],
      isVisible: ({ canReplyFromMenu }) => !canReplyFromMenu,
      resolve: () => ({
        key: 'login',
        label: getUiCopy({
          surface: 'discussion-action-login-label',
        })?.text || '登录后回复',
        icon: 'fas fa-sign-in-alt',
        description: getUiCopy({
          surface: 'discussion-action-login-description',
        })?.text || '登录后才可以参与当前讨论。',
        order: 10,
      }),
    })
}

function registerPostActions(forum) {
  forum
    .postAction({
      key: 'edit-post',
      moduleId: 'posts',
      order: 10,
      surfaces: ['post-menu'],
      isVisible: ({ post, canEditPost }) => Boolean(canEditPost(post)),
      resolve: () => ({
        key: 'edit-post',
        label: getUiCopy({
          surface: 'post-action-edit-label',
        })?.text || '编辑',
        icon: 'fas fa-pen',
        description: getUiCopy({
          surface: 'post-action-edit-description',
        })?.text || '修改这条回复内容。',
        order: 10,
      }),
    })
    .postAction({
      key: 'delete-post',
      moduleId: 'posts',
      order: 20,
      surfaces: ['post-menu'],
      isVisible: ({ post, canDeletePost }) => Boolean(canDeletePost(post)),
      resolve: () => ({
        key: 'delete-post',
        label: getUiCopy({
          surface: 'post-action-delete-label',
        })?.text || '删除',
        icon: 'fas fa-trash',
        description: getUiCopy({
          surface: 'post-action-delete-description',
        })?.text || '永久删除这条回复。',
        tone: 'danger',
        confirm: {
          title: getUiCopy({
            surface: 'post-action-delete-confirm-title',
          })?.text || '删除回复',
          message: getUiCopy({
            surface: 'post-action-delete-confirm-message',
          })?.text || '确定要删除这条回复吗？此操作不可恢复。',
          confirmText: getUiCopy({
            surface: 'post-action-delete-confirm-confirm',
          })?.text || '删除',
          cancelText: getUiCopy({
            surface: 'discussion-action-confirm-cancel',
          })?.text || '取消',
          tone: 'danger',
        },
        order: 20,
      }),
    })
    .postAction({
      key: 'toggle-hide-post',
      moduleId: 'posts',
      order: 25,
      surfaces: ['post-menu'],
      isVisible: ({ post, canModeratePostVisibility }) => Boolean(canModeratePostVisibility?.(post)),
      resolve: ({ post }) => ({
        key: 'toggle-hide-post',
        label: getUiCopy({
          surface: 'post-action-toggle-hide-label',
          isHidden: post.is_hidden,
        })?.text || (post.is_hidden ? '恢复显示' : '隐藏回复'),
        icon: post.is_hidden ? 'fas fa-eye' : 'fas fa-eye-slash',
        description: getUiCopy({
          surface: 'post-action-toggle-hide-description',
          isHidden: post.is_hidden,
        })?.text || (post.is_hidden ? '重新让这条回复在前台可见。' : '临时从前台隐藏这条回复。'),
        confirm: {
          title: getUiCopy({
            surface: 'post-action-toggle-hide-confirm-title',
            isHidden: post.is_hidden,
          })?.text || (post.is_hidden ? '恢复显示' : '隐藏回复'),
          message: getUiCopy({
            surface: 'post-action-toggle-hide-confirm-message',
            isHidden: post.is_hidden,
            postNumber: post.number,
          })?.text || (post.is_hidden ? `确定恢复显示 #${post.number} 吗？` : `确定隐藏 #${post.number} 吗？`),
          confirmText: getUiCopy({
            surface: 'post-action-toggle-hide-confirm-confirm',
            isHidden: post.is_hidden,
          })?.text || (post.is_hidden ? '恢复显示' : '隐藏回复'),
          cancelText: getUiCopy({
            surface: 'discussion-action-confirm-cancel',
          })?.text || '取消',
          tone: post.is_hidden ? 'primary' : 'warning',
        },
        order: 25,
      }),
    })
}

function registerPostComposer(forum) {
  forum
    .composerHost({
      key: 'post-composer',
      moduleId: 'posts',
      order: 20,
      component: PostComposer,
    })
    .composerSecondaryAction({
      key: 'save-post-draft',
      moduleId: 'posts',
      order: 5,
      isVisible: ({ type, isEditing, hasDraftContent, submitting, uploading }) => {
        return type === 'post' && !isEditing && Boolean(hasDraftContent) && !submitting && !uploading
      },
      resolve: () => ({
        label: '保存草稿',
        onClick: async ({ composerStore }) => {
          window.dispatchEvent(new CustomEvent('bias:composer-save-request', {
            detail: {
              composerType: 'post',
              requestId: composerStore?.current?.requestId || 0,
            },
          }))
        },
      }),
    })
    .composerSecondaryAction({
      key: 'clear-post-draft',
      moduleId: 'posts',
      order: 10,
      isVisible: ({ type, isEditing, hasDraftContent }) => type === 'post' && !isEditing && Boolean(hasDraftContent),
      resolve: ({ draftSavedAt }) => ({
        label: '清除草稿',
        action: 'clear-draft',
        confirm: draftSavedAt ? {
          title: '清除回复草稿',
          message: '确定要清除当前回复草稿吗？',
          confirmText: '清除草稿',
          cancelText: '取消',
          tone: 'danger',
        } : null,
      }),
    })
    .composerSecondaryAction({
      key: 'cancel-post-edit',
      moduleId: 'posts',
      order: 20,
      isVisible: ({ type, isEditing }) => type === 'post' && Boolean(isEditing),
      resolve: () => ({
        label: '取消编辑',
        action: 'cancel-edit',
        confirm: {
          title: '取消编辑',
          message: '确定放弃当前回复编辑内容吗？未保存修改将丢失。',
          confirmText: '放弃修改',
          cancelText: '继续编辑',
          tone: 'warning',
        },
      }),
    })
    .composerStatusItem({
      key: 'post-editing',
      moduleId: 'posts',
      order: 10,
      isVisible: ({ type, isEditing, minimized }) => type === 'post' && Boolean(isEditing) && !minimized,
      resolve: ({ postNumber }) => ({
        label: '状态',
        value: postNumber ? `编辑 #${postNumber}` : '编辑回复',
      }),
    })
    .composerStatusItem({
      key: 'post-target',
      moduleId: 'posts',
      order: 20,
      isVisible: ({ type, discussionTitle, minimized }) => type === 'post' && Boolean(discussionTitle) && !minimized,
      resolve: ({ discussionTitle, username }) => ({
        label: '讨论',
        value: username ? `${discussionTitle} · @${username}` : discussionTitle,
      }),
    })
    .composerDraftMeta({
      key: 'post-draft-saved-at',
      moduleId: 'posts',
      order: 30,
      isVisible: ({ type, draftSavedAt, isEditing, minimized }) => {
        return type === 'post' && !isEditing && Boolean(draftSavedAt) && !minimized
      },
      resolve: ({ draftSavedAt, formatDraftTime }) => ({
        label: '草稿',
        value: `保存于 ${formatDraftTime?.(draftSavedAt) || draftSavedAt}`,
      }),
    })
}

function registerPostsCopy(forum) {
  for (const definition of postsCopyDefinitions()) {
    forum.uiCopy({
      moduleId: 'posts',
      ...definition,
    })
  }
}

function postsCopyDefinitions() {
  return [
    createUiTextCopy('post-action-edit-label', 479, '编辑'),
    createUiTextCopy('post-action-edit-description', 479, '修改这条回复内容。'),
    createUiTextCopy('post-action-delete-label', 479, '删除'),
    createUiTextCopy('post-action-delete-description', 479, '永久删除这条回复。'),
    createUiTextCopy('post-action-delete-confirm-title', 479, '删除回复'),
    createUiTextCopy('post-action-delete-confirm-message', 479, '确定要删除这条回复吗？此操作不可恢复。'),
    createUiTextCopy('post-action-delete-confirm-confirm', 479, '删除'),
    {
      key: 'post-action-toggle-hide-label',
      order: 479,
      surfaces: ['post-action-toggle-hide-label'],
      resolve: ({ isHidden }) => ({
        text: isHidden ? '恢复显示' : '隐藏回复',
      }),
    },
    {
      key: 'post-action-toggle-hide-description',
      order: 479,
      surfaces: ['post-action-toggle-hide-description'],
      resolve: ({ isHidden }) => ({
        text: isHidden ? '重新让这条回复在前台可见。' : '临时从前台隐藏这条回复。',
      }),
    },
    {
      key: 'post-action-toggle-hide-confirm-title',
      order: 479,
      surfaces: ['post-action-toggle-hide-confirm-title'],
      resolve: ({ isHidden }) => ({
        text: isHidden ? '恢复显示' : '隐藏回复',
      }),
    },
    {
      key: 'post-action-toggle-hide-confirm-message',
      order: 479,
      surfaces: ['post-action-toggle-hide-confirm-message'],
      resolve: ({ isHidden, postNumber }) => ({
        text: isHidden ? `确定恢复显示 #${postNumber} 吗？` : `确定隐藏 #${postNumber} 吗？`,
      }),
    },
    {
      key: 'post-action-toggle-hide-confirm-confirm',
      order: 479,
      surfaces: ['post-action-toggle-hide-confirm-confirm'],
      resolve: ({ isHidden }) => ({
        text: isHidden ? '恢复显示' : '隐藏回复',
      }),
    },
    {
      key: 'post-event-hidden-label',
      order: 479,
      surfaces: ['post-event-hidden-label'],
      resolve: ({ isHidden, targetPostNumber }) => ({
        text: isHidden ? `隐藏了第 ${targetPostNumber} 楼回复` : `恢复显示第 ${targetPostNumber} 楼回复`,
      }),
    },
    createUiTextCopy('post-composer-content-placeholder', 620, '输入你的回复... 支持 Markdown、@用户名 和代码块'),
    {
      key: 'post-composer-submit',
      order: 630,
      surfaces: ['post-composer-submit'],
      resolve: ({ submitting, uploading, isEditing }) => ({
        text: submitting ? '提交中...' : (uploading ? '上传中...' : (isEditing ? '更新回复' : '发布回复')),
      }),
    },
    {
      key: 'post-composer-title',
      order: 631,
      surfaces: ['post-composer-title'],
      resolve: ({ isEditing, postNumber, discussionTitle }) => ({
        text: isEditing
          ? `编辑 #${postNumber || ''}`.trim()
          : (postNumber ? `回复 #${postNumber}` : `回复：${discussionTitle || '讨论'}`),
      }),
    },
    {
      key: 'post-composer-subtitle',
      order: 632,
      surfaces: ['post-composer-subtitle'],
      resolve: ({ isEditing, discussionTitle, hasDraftSavedAt, draftSavedAtText, username }) => {
        if (isEditing) {
          return {
            text: `${discussionTitle || '讨论'} · 编辑后会直接更新原帖`,
          }
        }

        if (hasDraftSavedAt) {
          return {
            text: `草稿已保存于 ${draftSavedAtText}`,
          }
        }

        if (username) {
          return {
            text: `${discussionTitle || '讨论'} · @${username}`,
          }
        }

        return {
          text: discussionTitle || '讨论',
        }
      },
    },
    {
      key: 'post-composer-minimized-summary',
      order: 633,
      surfaces: ['post-composer-minimized-summary'],
      resolve: ({ isEditing, postNumber, discussionTitle }) => ({
        text: isEditing
          ? `编辑 #${postNumber || ''}`.trim()
          : (postNumber ? `回复 #${postNumber}` : (discussionTitle || '回复讨论')),
      }),
    },
    {
      key: 'post-composer-close-title',
      order: 634,
      surfaces: ['post-composer-close-title'],
      resolve: ({ isEditing }) => ({
        text: isEditing ? '关闭编辑器' : '关闭回复框',
      }),
    },
    {
      key: 'post-composer-close-message',
      order: 635,
      surfaces: ['post-composer-close-message'],
      resolve: ({ isEditing }) => ({
        text: isEditing
          ? '确定要关闭编辑器吗？未保存修改将丢失。'
          : '确定要关闭回复框吗？当前内容会保留在本地草稿中。',
      }),
    },
    createUiTextCopy('post-composer-close-confirm', 636, '关闭'),
    createUiTextCopy('post-composer-close-cancel', 637, '继续编辑'),
    {
      key: 'post-composer-draft-restored',
      order: 638,
      surfaces: ['post-composer-draft-restored'],
      resolve: ({ hasDraftSavedAt, draftSavedAtText }) => ({
        text: hasDraftSavedAt
          ? `已恢复你在 ${draftSavedAtText} 保存的回复草稿。`
          : '已恢复本地回复草稿。',
      }),
    },
    createUiTextCopy('post-composer-draft-restore-error', 639, '回复草稿恢复失败。'),
    createUiTextCopy('post-composer-draft-emptied', 640, '回复草稿已清空。'),
    createUiTextCopy('post-composer-draft-saved', 641, '回复草稿已保存。'),
    createUiTextCopy('post-composer-draft-cleared-local', 642, '已清除本地回复草稿。'),
    {
      key: 'post-composer-unsaved-exit-message',
      order: 642,
      surfaces: ['post-composer-unsaved-exit-message'],
      resolve: ({ isEditing }) => ({
        text: isEditing
          ? '你有未保存的帖子编辑内容。确定要离开当前页面吗？'
          : '你有未发布的回复内容。确定要离开当前页面吗？',
      }),
    },
  ]
}
