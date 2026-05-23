import { computed } from 'vue'
import { getUiCopy } from '@/forum/registry'
import { useHomeViewBindings } from '@/composables/useHomeViewBindings'
import { useStartDiscussionAction } from '@/composables/useStartDiscussionAction'
import { useForumStore } from '@/stores/forum'

export function useHomeViewModel({
  authStore,
  composerStore,
  router,
}) {
  const forumStore = useForumStore()
  const { startDiscussion } = useStartDiscussionAction({
    authStore,
    composerStore,
    router,
  })

  const heroTitleText = computed(() => getUiCopy({
    surface: 'home-hero-title',
  })?.text || forumStore.settings.forum_title || 'Bias')
  const heroDescriptionText = computed(() => getUiCopy({
    surface: 'home-hero-description',
  })?.text || forumStore.settings.forum_description || '基于 Django 和 Vue 3 的现代化论坛')
  const browseDiscussionsText = computed(() => getUiCopy({
    surface: 'home-browse-discussions',
  })?.text || '浏览讨论')
  const startDiscussionText = computed(() => getUiCopy({
    surface: 'home-start-discussion',
  })?.text || '发起讨论')
  const registerAccountText = computed(() => getUiCopy({
    surface: 'home-register-account',
  })?.text || '注册账号')

  function handleStartDiscussion() {
    startDiscussion({
      source: 'home',
    })
  }

  const viewBindings = useHomeViewBindings({
    authStore,
    browseDiscussionsText,
    handleStartDiscussion,
    heroDescriptionText,
    heroTitleText,
    registerAccountText,
    startDiscussionText,
  })

  return {
    ...viewBindings,
  }
}
