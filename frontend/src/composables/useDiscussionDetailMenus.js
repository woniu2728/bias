import { computed } from 'vue'
import { getDiscussionMenuItems, getPostMenuItems } from '@/forum/discussionActions'

export function useDiscussionDetailMenus({
  activePostMenuId,
  authStore,
  canDeletePost,
  canEditPost,
  canModeratePostVisibility,
  canReportPost,
  canEditDiscussion,
  canModerateDiscussionSettings,
  canReplyFromMenu,
  discussion,
  deleteDiscussion,
  editDiscussion,
  goToLoginForReply,
  hasActiveComposer,
  isSuspended,
  openComposer,
  openReportModal,
  showDiscussionMenu,
  togglingSubscription,
  toggleHide,
  toggleLock,
  togglePin,
  toggleSubscription
}) {
  async function handleDiscussionMenuSelection(action) {
    const actionMap = {
      reply: openComposer,
      login: goToLoginForReply,
      'toggle-subscription': toggleSubscription,
      edit: editDiscussion,
      'toggle-pin': togglePin,
      'toggle-lock': toggleLock,
      'toggle-hide': toggleHide,
      delete: deleteDiscussion
    }
    const handler = actionMap[action]
    if (!handler) return

    showDiscussionMenu.value = false
    await handler()
  }

  const discussionMenuItems = computed(() => getDiscussionMenuItems({
    authStore,
    canEditDiscussion: canEditDiscussion.value,
    canModerateDiscussionSettings: canModerateDiscussionSettings.value,
    canReplyFromMenu: canReplyFromMenu.value,
    discussion: discussion.value || {},
    hasActiveComposer: hasActiveComposer.value,
    isSuspended: isSuspended.value,
    togglingSubscription: togglingSubscription.value
  }))

  function hasPostControls(post) {
    return getPostMenuItems({
      canDeletePost,
      canEditPost,
      canModeratePostVisibility,
      canReportPost,
      post
    }).length > 0
  }

  async function handleOpenReportModal(post) {
    activePostMenuId.value = null
    await openReportModal(post)
  }

  function getPostMenuOptions(post) {
    return getPostMenuItems({
      canDeletePost,
      canEditPost,
      canModeratePostVisibility,
      canReportPost,
      post
    })
  }

  return {
    discussionMenuItems,
    getPostMenuOptions,
    handleDiscussionMenuSelection,
    hasPostControls,
    handleOpenReportModal
  }
}
