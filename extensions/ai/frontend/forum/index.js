import { extendForum } from '@bias/forum'
import AiAssistantPanel from './AiAssistantPanel.vue'
import AiDiscussionSummaryModal from './AiDiscussionSummaryModal.vue'

export const extend = [
  extendForum('ai', registerAiForum),
]

function registerAiForum(forum) {
  forum
    .composerTool({
      key: 'ai-assistant',
      moduleId: 'ai',
      title: 'AI 助手',
      icon: 'fas fa-wand-magic-sparkles',
      order: 25,
      popoverComponent: AiAssistantPanel,
      popoverWidth: 540,
      popoverHeight: 460,
      popoverProps: context => ({
        title: context.title || '',
        content: context.content || '',
        insertText: context.insertText,
        selectionStart: context.selectionStart || 0,
        selectionEnd: context.selectionEnd || 0,
        setToolPopoverVisible: context.setToolPopoverVisible,
      }),
    })
    .discussionAction({
      key: 'ai-summary',
      moduleId: 'ai',
      order: 25,
      surfaces: ['discussion-menu', 'discussion-sidebar'],
      isVisible: ({ authStore, discussion }) => Boolean(authStore?.isAuthenticated && discussion?.id),
      resolve: ({ pendingDiscussionActions }) => {
        const pending = Boolean(pendingDiscussionActions?.['ai-summary'])
        return {
          key: 'ai-summary',
          label: pending ? '整理中...' : 'AI 讨论纪要',
          icon: 'fas fa-wand-magic-sparkles',
          description: '让 AI 用书记员视角整理观点、分歧和下一步。',
          disabled: pending,
          order: 25,
        }
      },
    })
    .discussionActionHandler({
      key: 'ai-summary',
      moduleId: 'ai',
      order: 10,
      handle: handleDiscussionSummary,
    })
}

async function handleDiscussionSummary({
  discussion,
  modalStore,
  setDiscussionActionPending,
}) {
  if (!discussion?.id || !modalStore?.show) {
    return false
  }

  setDiscussionActionPending?.('ai-summary', true)
  try {
    await modalStore.show(
      AiDiscussionSummaryModal,
      { discussionId: Number(discussion.id) },
      { size: 'medium', className: 'Modal--ai-summary' },
    )
    return true
  } finally {
    setDiscussionActionPending?.('ai-summary', false)
  }
}
