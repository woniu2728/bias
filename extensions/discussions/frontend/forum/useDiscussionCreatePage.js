import { onMounted } from '@bias/core'

export function useDiscussionCreatePage({
  route,
  router,
  startDiscussion,
}) {
  function resolveReturnTo() {
    return typeof route.query.returnTo === 'string' ? route.query.returnTo : '/'
  }

  onMounted(() => {
    startDiscussion({
      redirectToLogin: true,
      source: 'route',
    })
    router.replace(resolveReturnTo())
  })

  return {
    resolveReturnTo,
  }
}
