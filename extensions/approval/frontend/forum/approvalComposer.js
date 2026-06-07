import { getUiCopy } from '@bias/forum'

export function registerApprovalComposerCopy(forum) {
  for (const item of [
    {
      key: 'discussion-event-note-prefix',
      text: '理由：',
      order: 1,
    },
    {
      key: 'discussion-event-approved-label',
      text: '通过了该讨论的审核',
      order: 2,
    },
    {
      key: 'discussion-event-rejected-label',
      text: '拒绝了该讨论的审核',
      order: 3,
    },
    {
      key: 'discussion-event-resubmitted-label',
      text: '修改后重新提交了该讨论的审核',
      order: 4,
    },
    {
      key: 'post-event-approved-label',
      text: ({ targetPostNumber }) => `通过了第 ${targetPostNumber} 楼回复的审核`,
      order: 5,
    },
    {
      key: 'post-event-rejected-label',
      text: ({ targetPostNumber }) => `拒绝了第 ${targetPostNumber} 楼回复的审核`,
      order: 6,
    },
    {
      key: 'post-event-resubmitted-label',
      text: ({ targetPostNumber }) => `修改后重新提交了第 ${targetPostNumber} 楼回复的审核`,
      order: 7,
    },
    {
      key: 'discussion-composer-edit-pending-title',
      text: '讨论已重新提交审核',
      order: 10,
    },
    {
      key: 'discussion-composer-edit-pending-message',
      text: '请根据审核反馈继续完善内容，管理员通过后会重新公开显示。',
      order: 20,
    },
    {
      key: 'discussion-composer-create-pending-title',
      text: '讨论已进入审核队列',
      order: 30,
    },
    {
      key: 'discussion-composer-create-pending-message',
      text: '管理员通过后，这条讨论才会显示在论坛列表中。',
      order: 40,
    },
    {
      key: 'post-composer-edit-pending-title',
      text: '回复已重新提交审核',
      order: 50,
    },
    {
      key: 'post-composer-edit-pending-message',
      text: '管理员通过后，这条回复才会重新显示给其他用户。',
      order: 60,
    },
    {
      key: 'post-composer-create-pending-title',
      text: '回复已进入审核队列',
      order: 70,
    },
    {
      key: 'post-composer-create-pending-message',
      text: '管理员通过后，这条回复才会显示给其他用户。',
      order: 80,
    },
  ]) {
    forum.uiCopy({
      key: item.key,
      moduleId: 'approval',
      order: item.order,
      surfaces: [item.key],
      resolve: context => ({
        text: typeof item.text === 'function' ? item.text(context || {}) : item.text,
      }),
    })
  }
}

export function registerApprovalComposerInitialState(forum) {
  forum.composerInitialState({
    key: 'approval-edit-feedback-state',
    moduleId: 'approval',
    order: 10,
    isVisible: context => ['edit-discussion', 'edit-post'].includes(context.submitKind),
    contribute(context = {}) {
      const target = context.type === 'post' ? context.post : context.discussion
      const status = target?.approval_status || ''
      const note = target?.approval_note || ''
      if (!status && !note) {
        return {}
      }

      return {
        extensions: {
          approval: {
            status,
            note,
          },
        },
      }
    },
  })
}

export function registerApprovalComposerSubmitSuccess(forum) {
  forum.composerSubmitSuccess({
    key: 'approval-pending-submit-alert',
    moduleId: 'approval',
    order: 10,
    isVisible: context => getSubmittedApprovalStatus(context) === 'pending',
    async run(context) {
      if (typeof context.modalStore?.alert !== 'function') {
        return
      }

      const copy = getPendingSubmitCopy(context)
      await context.modalStore.alert({
        title: getUiCopy({ surface: copy.titleSurface })?.text || copy.title,
        message: getUiCopy({ surface: copy.messageSurface })?.text || copy.message,
      })
    },
  })
}

export function getApprovalComposerState(current = {}) {
  const state = current?.extensions?.approval || {}
  return {
    status: state.status || '',
    note: state.note || '',
  }
}

function getSubmittedApprovalStatus(context = {}) {
  const payload = context.type === 'post' ? (context.post || context.data) : context.data
  return payload?.approval_status || ''
}

function getPendingSubmitCopy(context = {}) {
  if (context.type === 'post') {
    if (context.mode === 'edit') {
      return {
        titleSurface: 'post-composer-edit-pending-title',
        messageSurface: 'post-composer-edit-pending-message',
        title: '回复已重新提交审核',
        message: '管理员通过后，这条回复才会重新显示给其他用户。',
      }
    }
    return {
      titleSurface: 'post-composer-create-pending-title',
      messageSurface: 'post-composer-create-pending-message',
      title: '回复已进入审核队列',
      message: '管理员通过后，这条回复才会显示给其他用户。',
    }
  }

  if (context.mode === 'edit') {
    return {
      titleSurface: 'discussion-composer-edit-pending-title',
      messageSurface: 'discussion-composer-edit-pending-message',
      title: '讨论已重新提交审核',
      message: '请根据审核反馈继续完善内容，管理员通过后会重新公开显示。',
    }
  }

  return {
    titleSurface: 'discussion-composer-create-pending-title',
    messageSurface: 'discussion-composer-create-pending-message',
    title: '讨论已进入审核队列',
    message: '管理员通过后，这条讨论才会显示在论坛列表中。',
  }
}
