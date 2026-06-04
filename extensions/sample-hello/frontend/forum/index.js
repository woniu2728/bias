import { registerForumNavItem, registerHeaderItem } from '@/forum/registry'

function buildHelloLabel(context = {}) {
  const settings = context.forumStore?.settings || {}
  const extensions = settings.enabled_extensions || []
  const extension = extensions.find(item => item?.id === 'sample-hello') || {}
  const values = extension.settings_values || {}
  return String(values.welcome_message || 'Sample Hello').trim() || 'Sample Hello'
}

export async function bootForumExtension(context = {}) {
  registerForumNavItem({
    key: 'sample-hello-nav',
    moduleId: 'sample-hello',
    section: 'primary',
    order: 35,
    icon: 'fas fa-hand-sparkles',
    label: () => buildHelloLabel(context),
    to: '/',
    description: '示例扩展前台入口已成功加载。',
  })

  registerHeaderItem({
    key: 'sample-hello-header',
    placement: 'after-search',
    moduleId: 'sample-hello',
    order: 35,
    icon: 'fas fa-plug',
    label: () => buildHelloLabel(context),
    to: '/',
    isVisible: ({ authStore }) => !authStore?.user,
  })
}
