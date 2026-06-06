import { Forum } from '@bias/forum'

function buildHelloLabel(context = {}) {
  const settings = context.forumStore?.settings || {}
  const extensions = settings.enabled_extensions || []
  const extension = extensions.find(item => item?.id === 'sample-hello') || {}
  const values = extension.settings_values || {}
  return String(values.welcome_message || 'Sample Hello').trim() || 'Sample Hello'
}

export const extend = [
  buildSampleHelloForumExtender(),
]

function buildSampleHelloForumExtender() {
  const forum = new Forum()
  registerSampleHelloForum(forum)
  return forum
}

function registerSampleHelloForum(forum) {
  forum.navItem({
    key: 'sample-hello-nav',
    moduleId: 'sample-hello',
    section: 'primary',
    order: 35,
    icon: 'fas fa-hand-sparkles',
    label: context => buildHelloLabel(context),
    to: '/',
    description: '示例扩展前台入口已成功加载。',
  })

  forum.headerItem({
    key: 'sample-hello-header',
    placement: 'after-search',
    moduleId: 'sample-hello',
    order: 35,
    icon: 'fas fa-plug',
    label: context => buildHelloLabel(context),
    to: '/',
    isVisible: ({ authStore }) => !authStore?.user,
  })
}
