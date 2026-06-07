export function createDiscussionActionHandlers({
  deleteDiscussion,
  editDiscussion,
  goToLoginForReply,
  openComposer,
  shareDiscussion,
  toggleHide,
  toggleLock,
  togglePin,
}) {
  return {
    delete: async () => {
      await deleteDiscussion()
    },
    edit: async () => {
      editDiscussion()
    },
    login: async () => {
      goToLoginForReply()
    },
    reply: async () => {
      openComposer()
    },
    share: async () => {
      await shareDiscussion()
    },
    'toggle-hide': async () => {
      await toggleHide()
    },
    'toggle-lock': async () => {
      await toggleLock()
    },
    'toggle-pin': async () => {
      await togglePin()
    },
  }
}

export function createPostActionHandlers({
  deletePost,
  editPost,
  togglePostHidden,
}) {
  return {
    'delete-post': async (_, context = {}) => {
      await deletePost(context.post)
    },
    'edit-post': async (_, context = {}) => {
      await editPost(context.post)
    },
    'toggle-hide-post': async (_, context = {}) => {
      await togglePostHidden(context.post)
    },
  }
}
