import { extendAdmin } from '@bias/admin'
import { ExtensionGeneratedPermissionsPage } from '@bias/admin/components'
import UsersPage from './UsersPage.vue'
import { buildUsersPageExtender } from './usersPageBootstrap.js'

const MAIL_PAGE_KEY = 'core.mail'

export const extend = [
  extendAdmin(admin => admin.route({
    path: '/admin/users',
    name: 'admin-users',
    component: UsersPage,
    icon: 'fas fa-users',
    label: '用户管理',
    navDescription: '管理论坛用户账号、状态和用户组。',
    navSection: 'core',
    navOrder: 80,
    showInDashboardActions: true,
    dashboardActionLabel: '管理用户',
    moduleId: 'users',
  })),

  extendAdmin(admin => admin
    .pageCopy(MAIL_PAGE_KEY, {
      key: 'users-mail-test-copy',
      moduleId: 'users',
      order: 30,
      resolve: () => ({
        testSectionTitle: '发送测试邮件',
        testSectionDescription: '优先发送到你填写的测试收件箱。留空时，会回退到当前管理员邮箱。',
        testRecipientLabel: '测试收件箱',
        testRecipientHint: '建议填写一个真实可收信邮箱，便于直接验证 SMTP 是否可用。',
        effectiveRecipientPrefix: '实际发送到：',
        effectiveRecipientEmptyText: '（未设置）',
        unsavedChangesHint: '请先保存当前修改，再发送测试邮件。',
        testSendLabel: '发送测试邮件',
        testSendingLabel: '发送中...',
      }),
    })
    .pageConfig(MAIL_PAGE_KEY, {
      key: 'users-mail-test-config',
      moduleId: 'users',
      order: 30,
      resolve: () => ({
        defaultSettings: {
          mail_test_recipient: '',
        },
        placeholders: {
          mailTestRecipient: 'admin@example.com',
        },
      }),
    })
    .pageActionMeta(MAIL_PAGE_KEY, {
      key: 'users-mail-test-action-meta',
      moduleId: 'users',
      order: 30,
      resolve: () => ({
        testSuccessTitle: '测试邮件已发送',
        testSuccessMessage: toEmail => `测试邮件已发送到 ${toEmail}，请检查收件箱`,
        testFailedTitle: '发送测试邮件失败',
      }),
    })
    .pageAction(MAIL_PAGE_KEY, {
      key: 'send-test-email',
      moduleId: 'users',
      order: 10,
      resolve: ({ api, modalStore, mailActionMeta, getRecipient, setTesting }) => ({
        run: async () => {
          const toEmail = typeof getRecipient === 'function' ? getRecipient() : ''
          setTesting?.(true)
          try {
            const data = await api.post('/admin/mail/test', {
              to_email: toEmail,
            })
            const recipient = data?.to_email || toEmail
            await modalStore.alert({
              title: mailActionMeta?.testSuccessTitle || '测试邮件已发送',
              message: mailActionMeta?.testSuccessMessage?.(recipient) || `测试邮件已发送到 ${recipient}，请检查收件箱`,
              tone: 'success',
            })
          } catch (error) {
            await modalStore.alert({
              title: mailActionMeta?.testFailedTitle || '发送测试邮件失败',
              message: error.response?.data?.error || error.message || mailActionMeta?.unknownErrorText || '未知错误',
              tone: 'danger',
            })
          } finally {
            setTesting?.(false)
          }
        },
      }),
    })),

  buildUsersPageExtender(),
]

export function resolvePermissionsPage() {
  return ExtensionGeneratedPermissionsPage
}
