
import { computed } from '@bias/core'
import { getUiCopy } from '@bias/forum'

export function createDiscussionListSidebarStartButtonState({
  contextSubject,
  getText = getUiCopy,
}) {
  const labelText = computed(() => getText({
    surface: 'start-discussion-button',
    hasContextSubject: Boolean(contextSubject.value),
    subjectName: contextSubject.value?.name || contextSubject.value?.title || '',
  })?.text || '发起讨论')

  return {
    labelText,
  }
}

export function useDiscussionListSidebarStartButtonState(options) {
  return createDiscussionListSidebarStartButtonState(options)
}
