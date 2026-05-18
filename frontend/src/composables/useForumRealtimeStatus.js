import { computed } from 'vue'

export function useForumRealtimeStatus({
  forumRealtimeStore,
  authStore,
  getText = () => null,
}) {
  const shouldShow = computed(() => (
    Boolean(authStore?.isAuthenticated)
    && (forumRealtimeStore?.isReconnecting?.value || forumRealtimeStore?.hasConnectionError?.value)
  ))

  const tone = computed(() => {
    if (forumRealtimeStore?.hasConnectionError?.value) {
      return 'warning'
    }
    return 'info'
  })

  const text = computed(() => {
    if (!shouldShow.value) {
      return ''
    }

    const surface = forumRealtimeStore?.hasConnectionError?.value
      ? 'forum-realtime-status-error'
      : 'forum-realtime-status-reconnecting'

    return getText({
      surface,
      failureCount: Number(forumRealtimeStore?.connectionFailureCount?.value || 0),
    })?.text || ''
  })

  return {
    shouldShow,
    tone,
    text,
  }
}
