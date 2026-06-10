import {
  ResourceNormalizer,
  useModalStore
} from '@bias/core'
import { extendForum,
  getUiCopy
} from '@bias/forum'
import { buildUserPath, normalizeUser, registerAuthModalProvider } from '@bias/users'
import AuthSessionModal from './AuthSessionModal.vue'
import HeaderUserMenu from './HeaderUserMenu.vue'
import MobileDrawerUserCard from './MobileDrawerUserCard.vue'
import ProfileDiscussionSection from './ProfileDiscussionSection.vue'
import ProfilePostSection from './ProfilePostSection.vue'
import ProfileSettingsSection from './ProfileSettingsSection.vue'
import ProfileSecuritySection from './ProfileSecuritySection.vue'

export const extend = [
  new ResourceNormalizer()
    .add('users', normalizeUser)
    .add('user', normalizeUser),
  extendForum('users', registerUsersForum),
]

function registerUsersForum(forum) {
  registerUsersAuthModal(forum)
  registerUsersNavigation(forum)
  registerUsersPresentation(forum)
  registerUsersStates(forum)
  registerUsersComposer(forum)
  registerUsersUiCopy(forum)
  registerProfilePanels(forum)
  return forum
}

function registerUsersAuthModal() {
  registerAuthModalProvider({
    key: 'users-auth-session-modal',
    moduleId: 'users',
    order: 10,
    open(props = {}) {
      return useModalStore().show(
        AuthSessionModal,
        {
          mode: props.mode || 'login',
          redirectPath: props.redirectPath || '/',
          initialIdentification: props.initialIdentification || '',
          initialEmail: props.initialEmail || '',
          initialUsername: props.initialUsername || '',
          initialPassword: props.initialPassword || '',
        },
        {
          dismissibleViaCloseButton: true,
          dismissibleViaEscKey: true,
          dismissibleViaBackdropClick: true,
        }
      )
    },
  })
}

function isOwnProfileRoute(route, user) {
  if (!route || !user) return false
  return route.name === 'profile'
    || (route.name === 'user-profile' && String(route.params.id) === String(user.id))
}

function registerUsersNavigation(forum) {
  forum
    .headerItem({
      key: 'user-menu-host',
      moduleId: 'users',
      placement: 'user-menu-host',
      order: 10,
      component: HeaderUserMenu,
      componentProps: ({
        authStore,
        getUserAvatarColor,
        getUserInitial,
        handleUserMenuItemClick,
        showUserMenu,
        toggleUserMenu,
        userMenuItems,
      }) => ({
        authStore,
        showUserMenu,
        items: userMenuItems,
        getUserAvatarColor,
        getUserInitial,
        onToggle: toggleUserMenu,
        onItemClick: handleUserMenuItemClick,
      }),
      isVisible: ({ authStore }) => Boolean(authStore?.user),
    })
    .navSection({
      key: 'personal',
      title: '个人',
      order: 20,
    })
    .navItem({
      key: 'profile',
      moduleId: 'users',
      to: ({ authStore }) => buildUserPath(authStore.user),
      icon: 'fas fa-user',
      label: '我的主页',
      description: '查看你的资料、讨论和回复。',
      section: 'personal',
      order: 50,
      surfaces: ['discussion-sidebar', 'mobile-drawer'],
      isVisible: ({ authStore }) => Boolean(authStore?.user),
    })
    .headerItem({
      key: 'user-profile-menu',
      moduleId: 'users',
      placement: 'user-menu',
      order: 10,
      icon: 'fas fa-user',
      label: '个人资料',
      to: ({ authStore }) => buildUserPath(authStore.user),
      isVisible: ({ authStore }) => Boolean(authStore?.user),
      isActive: ({ route, authStore }) => isOwnProfileRoute(route, authStore?.user),
    })
    .headerItem({
      key: 'mobile-user-card',
      moduleId: 'users',
      placement: 'mobile-drawer-user-card',
      order: 10,
      component: MobileDrawerUserCard,
      componentProps: ({
        authStore,
        getUserAvatarColor,
        getUserInitial,
      }) => ({
        authStore,
        getUserAvatarColor,
        getUserInitial,
      }),
      isVisible: ({ authStore }) => Boolean(authStore?.user),
    })
    .headerItem({
      key: 'guest-login',
      placement: 'guest-actions',
      order: 10,
      label: '登录',
      isVisible: ({ authStore }) => !authStore?.user,
      onClick: ({ openLogin }) => openLogin?.(),
    })
    .headerItem({
      key: 'mobile-header-login',
      moduleId: 'users',
      placement: 'mobile-header-right-action',
      order: 10,
      actionType: 'login',
      icon: 'fas fa-right-to-bracket',
      label: () => getUiCopy({
        surface: 'header-mobile-right-action-label',
        actionType: 'login',
      })?.text || '登录',
      isVisible: ({ authStore }) => !authStore?.isAuthenticated,
      onClick: ({ openLogin }) => openLogin?.(),
    })
    .headerItem({
      key: 'guest-register',
      placement: 'guest-actions',
      order: 20,
      label: '注册',
      tone: 'primary',
      isVisible: ({ authStore }) => !authStore?.user,
      onClick: ({ openRegister }) => openRegister?.(),
    })
    .headerItem({
      key: 'user-admin-menu',
      placement: 'user-menu',
      order: 30,
      icon: 'fas fa-cog',
      label: '管理后台',
      href: '/admin.html',
      isVisible: ({ authStore }) => Boolean(authStore?.user?.is_staff),
    })
    .headerItem({
      key: 'user-logout-menu',
      placement: 'user-menu',
      order: 40,
      icon: 'fas fa-sign-out-alt',
      label: '登出',
      tone: 'danger',
      separated: true,
      isVisible: ({ authStore }) => Boolean(authStore?.user),
      onClick: ({ handleLogout }) => handleLogout?.(),
    })
    .headerItem({
      key: 'mobile-profile',
      moduleId: 'users',
      placement: 'mobile-drawer-personal',
      order: 20,
      icon: 'fas fa-user',
      label: '我的主页',
      to: ({ authStore }) => buildUserPath(authStore.user),
      isVisible: ({ authStore }) => Boolean(authStore?.user),
      isActive: ({ route, authStore }) => isOwnProfileRoute(route, authStore?.user),
    })
    .headerItem({
      key: 'mobile-admin',
      placement: 'mobile-drawer-user',
      order: 10,
      icon: 'fas fa-cog',
      label: '管理后台',
      href: '/admin.html',
      isVisible: ({ authStore }) => Boolean(authStore?.user?.is_staff),
    })
    .headerItem({
      key: 'mobile-logout',
      placement: 'mobile-drawer-user',
      order: 20,
      icon: 'fas fa-sign-out-alt',
      label: '登出',
      tone: 'danger',
      isVisible: ({ authStore }) => Boolean(authStore?.user),
      onClick: ({ handleLogout }) => handleLogout?.(),
    })
    .headerItem({
      key: 'mobile-guest-login',
      placement: 'mobile-drawer-auth',
      order: 10,
      label: '登录',
      isVisible: ({ authStore }) => !authStore?.user,
      onClick: ({ openLogin }) => openLogin?.(),
    })
    .headerItem({
      key: 'mobile-guest-register',
      placement: 'mobile-drawer-auth',
      order: 20,
      label: '注册',
      tone: 'primary',
      isVisible: ({ authStore }) => !authStore?.user,
      onClick: ({ openRegister }) => openRegister?.(),
    })
}

function registerUsersPresentation(forum) {
  forum
    .userBadge({
      key: 'staff',
      order: 10,
      isVisible: ({ user }) => Boolean(user?.is_staff),
      resolve: () => ({
        label: '管理员',
        className: 'badge-admin',
      }),
    })
    .userBadge({
      key: 'primary-group',
      moduleId: 'users',
      order: 20,
      isVisible: ({ user }) => Boolean(user?.primary_group?.name),
      resolve: ({ user }) => ({
        label: user.primary_group.name,
        icon: user.primary_group.icon || '',
        color: user.primary_group.color || '#4d698e',
        variant: 'group',
      }),
    })
    .heroMeta({
      key: 'profile-last-seen',
      moduleId: 'users',
      order: 10,
      surfaces: ['profile-hero'],
      resolve: ({ isOnline, formatLastSeen, user }) => ({
        icon: 'fas fa-circle',
        iconClassName: isOnline ? 'hero-meta-icon hero-meta-icon--online' : 'hero-meta-icon',
        text: isOnline ? '在线' : formatLastSeen(user?.last_seen_at),
      }),
    })
    .heroMeta({
      key: 'profile-joined-at',
      moduleId: 'users',
      order: 20,
      surfaces: ['profile-hero'],
      isVisible: ({ user }) => Boolean(user?.joined_at),
      resolve: ({ formatJoinDate, user }) => ({
        icon: 'fas fa-clock',
        text: `加入于 ${formatJoinDate(user.joined_at)}`,
        title: user.joined_at,
      }),
    })
}

function registerUsersStates(forum) {
  forum
    .emptyState({
      key: 'profile-discussions-empty',
      order: 10,
      surfaces: ['profile-discussion-empty'],
      isVisible: ({ discussions }) => Array.isArray(discussions) && discussions.length === 0,
      resolve: ({ isOwnProfile }) => ({
        text: isOwnProfile ? '你还没有发起过讨论' : '该用户还没有发起过讨论',
      }),
    })
    .emptyState({
      key: 'profile-posts-empty',
      order: 20,
      surfaces: ['profile-post-empty'],
      isVisible: ({ posts }) => Array.isArray(posts) && posts.length === 0,
      resolve: ({ isOwnProfile }) => ({
        text: isOwnProfile ? '你还没有发表过回复' : '该用户还没有发表过回复',
      }),
    })
    .pageState({
      key: 'profile-loading',
      order: 30,
      surfaces: ['profile-loading'],
      isVisible: ({ loading }) => Boolean(loading),
      resolve: () => ({
        text: '加载中...',
      }),
    })
    .pageState({
      key: 'profile-not-found',
      order: 40,
      surfaces: ['profile-not-found'],
      isVisible: ({ loading, user }) => !loading && !user,
      resolve: () => ({
        text: '用户不存在',
      }),
    })
    .stateBlock({
      key: 'profile-discussion-loading',
      order: 70,
      surfaces: ['profile-discussion-loading'],
      isVisible: ({ loading }) => Boolean(loading),
      resolve: () => ({
        text: '加载中...',
      }),
    })
    .stateBlock({
      key: 'profile-post-loading',
      order: 80,
      surfaces: ['profile-post-loading'],
      isVisible: ({ loading }) => Boolean(loading),
      resolve: () => ({
        text: '加载中...',
      }),
    })
    .stateBlock({
      key: 'profile-preferences-loading',
      order: 90,
      surfaces: ['profile-preferences-loading'],
      isVisible: ({ loading }) => Boolean(loading),
      resolve: () => ({
        text: '加载偏好中...',
      }),
    })
}

function registerUsersComposer(forum) {
  forum
    .composerNotice({
      key: 'suspension',
      moduleId: 'users',
      order: 10,
      isVisible: ({ authStore }) => Boolean(authStore?.user?.is_suspended),
      resolve: ({ authStore, type }) => ({
        label: '账号',
        tone: 'warning',
        message: formatComposerSuspensionNotice(
          authStore.user,
          type === 'discussion' ? '暂时无法发布讨论。' : '暂时无法回复、编辑或上传附件。'
        ),
      }),
    })
    .composerSubmitGuard({
      key: 'suspension',
      moduleId: 'users',
      order: 10,
      isVisible: ({ authStore }) => Boolean(authStore?.user?.is_suspended),
      check: ({ authStore, type }) => ({
        tone: 'error',
        message: formatComposerSuspensionNotice(
          authStore.user,
          type === 'discussion' ? '暂时无法发布讨论。' : '暂时无法回复、编辑或上传附件。'
        ),
      }),
    })
}

function formatComposerSuspensionNotice(user = {}, fallbackMessage) {
  if (!user?.is_suspended) return ''

  if (user.suspend_message) {
    return user.suspended_until
      ? `账号已被封禁至 ${formatComposerDateTime(user.suspended_until)}。${user.suspend_message}`
      : `账号当前已被封禁。${user.suspend_message}`
  }

  return user.suspended_until
    ? `账号已被封禁至 ${formatComposerDateTime(user.suspended_until)}，${fallbackMessage}`
    : `账号当前已被封禁，${fallbackMessage}`
}

function formatComposerDateTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未知时间'
  return date.toLocaleString('zh-CN')
}

function registerUsersUiCopy(forum) {
  for (const definition of usersUiCopyDefinitions) {
    forum.uiCopy(definition)
  }
}

const usersUiCopyDefinitions = [
  uiCopy('turnstile-loading', 90, ['auth-turnstile-status'], ({ turnstileLoading }) => ({
    text: '真人验证加载中...',
  }), ({ turnstileLoading }) => Boolean(turnstileLoading)),
  uiCopy('turnstile-required', 100, ['auth-turnstile-status'], () => ({
    text: '请完成真人验证后再继续。',
  }), ({ humanVerificationRequired, hasToken }) => Boolean(humanVerificationRequired) && !hasToken),
  uiCopy('profile-settings-section-title', 135, ['profile-settings-section-title'], () => ({ text: '个人设置' })),
  uiCopy('profile-settings-section-description', 136, ['profile-settings-section-description'], () => ({ text: '维护你的显示名称、邮箱、个人简介和通知偏好。' })),
  uiCopy('profile-settings-display-name-label', 137, ['profile-settings-display-name-label'], () => ({ text: '显示名称' })),
  uiCopy('profile-settings-email-label', 138, ['profile-settings-email-label'], () => ({ text: '邮箱' })),
  uiCopy('profile-settings-bio-label', 139, ['profile-settings-bio-label'], () => ({ text: '个人简介' })),
  uiCopy('profile-settings-display-name-placeholder', 140, ['profile-settings-display-name-placeholder'], () => ({ text: '显示名称' })),
  uiCopy('profile-settings-email-placeholder', 150, ['profile-settings-email-placeholder'], () => ({ text: 'name@example.com' })),
  uiCopy('profile-settings-bio-placeholder', 160, ['profile-settings-bio-placeholder'], () => ({ text: '介绍一下自己...' })),
  uiCopy('profile-settings-email-help', 170, ['profile-settings-email-help'], ({ isEmailConfirmed }) => ({ text: isEmailConfirmed ? '当前邮箱已完成验证。' : '修改邮箱后会重新进入未验证状态。' })),
  uiCopy('profile-security-section-title', 175, ['profile-security-section-title'], () => ({ text: '账号安全' })),
  uiCopy('profile-security-section-description', 176, ['profile-security-section-description'], () => ({ text: '查看邮箱验证状态，并修改登录密码。' })),
  uiCopy('profile-security-email-section-title', 177, ['profile-security-email-section-title'], () => ({ text: '邮箱验证' })),
  uiCopy('profile-security-email-section-description', 178, ['profile-security-email-section-description'], () => ({ text: '验证邮箱后，可确保找回密码和安全通知正常送达。' })),
  uiCopy('profile-security-status-label', 180, ['profile-security-status-label'], ({ isEmailConfirmed }) => ({ text: isEmailConfirmed ? '已验证' : '未验证' })),
  uiCopy('profile-security-email-help', 190, ['profile-security-email-help'], ({ isEmailConfirmed }) => ({ text: isEmailConfirmed ? '当前邮箱已通过验证。' : '当前邮箱尚未验证，你可以重新发送验证邮件。' })),
  uiCopy('profile-security-resend-button', 200, ['profile-security-resend-button'], ({ sending }) => ({ text: sending ? '发送中...' : '重新发送验证邮件' })),
  uiCopy('profile-security-old-password-label', 207, ['profile-security-old-password-label'], () => ({ text: '当前密码' })),
  uiCopy('profile-security-old-password-placeholder', 210, ['profile-security-old-password-placeholder'], () => ({ text: '请输入当前密码' })),
  uiCopy('profile-security-new-password-label', 217, ['profile-security-new-password-label'], () => ({ text: '新密码' })),
  uiCopy('profile-security-new-password-placeholder', 220, ['profile-security-new-password-placeholder'], () => ({ text: '请输入新密码' })),
  uiCopy('profile-security-confirm-password-label', 227, ['profile-security-confirm-password-label'], () => ({ text: '确认新密码' })),
  uiCopy('profile-security-confirm-password-placeholder', 230, ['profile-security-confirm-password-placeholder'], () => ({ text: '请再次输入新密码' })),
  uiCopy('profile-security-password-section-title', 235, ['profile-security-password-section-title'], () => ({ text: '修改密码' })),
  uiCopy('profile-security-password-section-description', 236, ['profile-security-password-section-description'], () => ({ text: '修改后，下次登录请使用新密码。' })),
  uiCopy('profile-security-submit-button', 240, ['profile-security-submit-button'], ({ submitting }) => ({ text: submitting ? '提交中...' : '更新密码' })),
  uiCopy('profile-settings-save-button', 250, ['profile-settings-save-button'], ({ saving }) => ({ text: saving ? '保存中...' : '保存资料' })),
  uiCopy('profile-settings-save-success', 255, ['profile-settings-save-success'], ({ emailChanged, email }) => ({ text: emailChanged ? `资料已保存，验证邮件已发送到 ${email}` : '资料已保存' })),
  uiCopy('profile-settings-save-error', 256, ['profile-settings-save-error'], () => ({ text: '保存失败' })),
  uiCopy('profile-settings-load-error', 256, ['profile-settings-load-error'], () => ({ text: '加载用户失败，请稍后重试' })),
  uiCopy('profile-discussions-load-error', 256, ['profile-discussions-load-error'], () => ({ text: '加载讨论失败，请稍后重试' })),
  uiCopy('profile-posts-load-error', 256, ['profile-posts-load-error'], () => ({ text: '加载回复失败，请稍后重试' })),
  uiCopy('profile-preferences-section-title', 257, ['profile-preferences-section-title'], () => ({ text: '通知偏好' })),
  uiCopy('profile-preferences-section-description', 258, ['profile-preferences-section-description'], () => ({ text: '按模块统一管理自动关注和通知订阅，新增通知类型后可以直接从注册表接入这里。' })),
  uiCopy('profile-preferences-group-label', 259, ['profile-preferences-group-label'], ({ category }) => ({ text: category === 'behavior' ? '自动关注' : '通知订阅' })),
  uiCopy('profile-preferences-group-description', 259, ['profile-preferences-group-description'], ({ category }) => ({ text: category === 'behavior' ? '控制发帖和回帖时的默认关注行为。' : '控制哪些站内通知会推送给你。' })),
  uiCopy('profile-preferences-save-button', 260, ['profile-preferences-save-button'], ({ saving }) => ({ text: saving ? '保存中...' : '保存偏好' })),
  uiCopy('profile-preferences-load-error', 261, ['profile-preferences-load-error'], () => ({ text: '加载通知偏好失败' })),
  uiCopy('profile-preferences-save-success', 262, ['profile-preferences-save-success'], () => ({ text: '通知偏好已保存' })),
  uiCopy('profile-preferences-save-error', 263, ['profile-preferences-save-error'], () => ({ text: '保存通知偏好失败' })),
  uiCopy('profile-verification-success', 264, ['profile-verification-success'], () => ({ text: '验证邮件已发送' })),
  uiCopy('profile-verification-error', 265, ['profile-verification-error'], () => ({ text: '发送失败' })),
  uiCopy('profile-password-empty-error', 266, ['profile-password-empty-error'], () => ({ text: '请完整填写密码信息' })),
  uiCopy('profile-password-mismatch-error', 267, ['profile-password-mismatch-error'], () => ({ text: '两次输入的新密码不一致' })),
  uiCopy('profile-password-success', 268, ['profile-password-success'], () => ({ text: '密码修改成功' })),
  uiCopy('profile-password-error', 269, ['profile-password-error'], () => ({ text: '密码修改失败' })),
  uiCopy('auth-login-identification-placeholder', 270, ['auth-login-identification-placeholder'], () => ({ text: '请输入用户名或邮箱' })),
  uiCopy('auth-login-password-placeholder', 280, ['auth-login-password-placeholder'], () => ({ text: '请输入密码' })),
  uiCopy('auth-register-username-placeholder', 290, ['auth-register-username-placeholder'], () => ({ text: '3-30 个字符' })),
  uiCopy('auth-register-email-placeholder', 300, ['auth-register-email-placeholder'], () => ({ text: '请输入邮箱' })),
  uiCopy('auth-register-password-placeholder', 310, ['auth-register-password-placeholder'], () => ({ text: '至少 6 个字符' })),
  uiCopy('auth-register-password-confirm-placeholder', 320, ['auth-register-password-confirm-placeholder'], () => ({ text: '请再次输入密码' })),
  uiCopy('auth-forgot-email-placeholder', 330, ['auth-forgot-email-placeholder'], () => ({ text: '请输入注册邮箱' })),
  uiCopy('auth-forgot-success', 340, ['auth-forgot-success'], () => ({ text: '重置链接已发送，请检查邮箱。' })),
  uiCopy('auth-debug-reset-title', 350, ['auth-debug-reset-title'], () => ({ text: '开发环境调试链接' })),
  uiCopy('auth-login-submit', 360, ['auth-login-submit'], ({ loading }) => ({ text: loading ? '登录中...' : '登录' })),
  uiCopy('auth-register-submit', 370, ['auth-register-submit'], ({ loading }) => ({ text: loading ? '注册中...' : '注册' })),
  uiCopy('auth-forgot-submit', 380, ['auth-forgot-submit'], ({ loading }) => ({ text: loading ? '发送中...' : '发送重置链接' })),
  uiCopy('reset-password-token-placeholder', 390, ['reset-password-token-placeholder'], () => ({ text: '请输入邮件中的重置令牌' })),
  uiCopy('reset-password-new-placeholder', 400, ['reset-password-new-placeholder'], () => ({ text: '请输入新密码' })),
  uiCopy('reset-password-confirm-placeholder', 410, ['reset-password-confirm-placeholder'], () => ({ text: '请再次输入新密码' })),
  uiCopy('reset-password-submit', 420, ['reset-password-submit'], ({ loading }) => ({ text: loading ? '提交中...' : '重置密码' })),
  uiCopy('header-mobile-login-action-label', 475, ['header-mobile-right-action-label'], () => ({ text: '登录' }), ({ actionType }) => actionType === 'login'),
  uiCopy('mobile-drawer-profile-section-title', 540, ['mobile-drawer-profile-section-title'], () => ({ text: '个人' })),
  uiCopy('verify-email-title', 640, ['verify-email-title'], () => ({ text: '验证邮箱' })),
  uiCopy('verify-email-subtitle', 650, ['verify-email-subtitle'], () => ({ text: '确认你的邮箱地址后，账号安全设置会完整开放。' })),
  uiCopy('verify-email-loading', 660, ['verify-email-loading'], () => ({ text: '正在验证邮箱，请稍候...' })),
  uiCopy('verify-email-idle', 670, ['verify-email-idle'], () => ({ text: '请从邮件中的链接打开本页面，或确认地址中的验证令牌是否完整。' })),
  uiCopy('verify-email-login-action', 680, ['verify-email-login-action'], () => ({ text: '前往登录' })),
  uiCopy('verify-email-profile-action', 690, ['verify-email-profile-action'], () => ({ text: '返回个人资料' })),
  uiCopy('verify-email-success', 700, ['verify-email-success'], () => ({ text: '邮箱验证成功。现在你可以继续登录，或返回个人资料查看最新状态。' })),
  uiCopy('verify-email-error', 710, ['verify-email-error'], () => ({ text: '邮箱验证失败，请稍后重试' })),
  uiCopy('reset-password-title', 720, ['reset-password-title'], () => ({ text: '重置密码' })),
  uiCopy('reset-password-subtitle', 730, ['reset-password-subtitle'], () => ({ text: '输入新的密码以完成重置。如果你是通过邮件打开页面，令牌会自动填入。' })),
  uiCopy('reset-password-token-label', 740, ['reset-password-token-label'], () => ({ text: '重置令牌' })),
  uiCopy('reset-password-new-label', 750, ['reset-password-new-label'], () => ({ text: '新密码' })),
  uiCopy('reset-password-confirm-label', 760, ['reset-password-confirm-label'], () => ({ text: '确认新密码' })),
  uiCopy('reset-password-back-to-login', 770, ['reset-password-back-to-login'], () => ({ text: '返回登录' })),
  uiCopy('reset-password-mismatch-error', 780, ['reset-password-mismatch-error'], () => ({ text: '两次输入的新密码不一致' })),
  uiCopy('reset-password-success', 790, ['reset-password-success'], () => ({ text: '密码已重置，正在返回登录页...' })),
  uiCopy('reset-password-error', 800, ['reset-password-error'], () => ({ text: '重置失败，请检查令牌或稍后重试' })),
  uiCopy('profile-hero-avatar-upload', 1170, ['profile-hero-avatar-upload'], ({ uploading }) => ({ text: uploading ? '上传中...' : '更换头像' })),
  uiCopy('profile-avatar-upload-error-title', 1171, ['profile-avatar-upload-error-title'], () => ({ text: '头像上传失败' })),
  uiCopy('profile-avatar-upload-error-message', 1172, ['profile-avatar-upload-error-message'], () => ({ text: '未知错误' })),
  uiCopy('profile-error-unknown', 1173, ['profile-error-unknown'], () => ({ text: '未知错误' })),
  uiCopy('profile-hero-settings-button', 1180, ['profile-hero-settings-button'], () => ({ text: '设置' })),
  uiCopy('auth-session-close', 1310, ['auth-session-close'], () => ({ text: '关闭' })),
  uiCopy('auth-session-title', 1311, ['auth-session-title'], ({ mode }) => ({ text: mode === 'register' ? '加入讨论' : (mode === 'forgot-password' ? '找回密码' : '登录') })),
  uiCopy('auth-session-subtitle', 1312, ['auth-session-subtitle'], ({ mode }) => ({
    text: mode === 'register'
      ? '注册完成后即可回到当前页面继续操作。'
      : (mode === 'forgot-password'
          ? '输入注册邮箱，我们会向你发送重置密码链接。'
          : '欢迎回来，登录后即可继续回复、关注和管理你的内容。'),
  })),
  uiCopy('auth-session-eyebrow', 1313, ['auth-session-eyebrow'], ({ mode }) => ({ text: mode === 'register' ? 'Sign Up' : (mode === 'forgot-password' ? 'Recovery' : 'Session') })),
  uiCopy('auth-login-identification-label', 1314, ['auth-login-identification-label'], () => ({ text: '用户名或邮箱' })),
  uiCopy('auth-login-password-label', 1315, ['auth-login-password-label'], () => ({ text: '密码' })),
  uiCopy('auth-human-verification-label', 1316, ['auth-human-verification-label'], () => ({ text: '真人验证' })),
  uiCopy('auth-register-username-label', 1317, ['auth-register-username-label'], () => ({ text: '用户名' })),
  uiCopy('auth-register-email-label', 1318, ['auth-register-email-label'], () => ({ text: '邮箱' })),
  uiCopy('auth-register-password-label', 1319, ['auth-register-password-label'], () => ({ text: '密码' })),
  uiCopy('auth-register-password-confirm-label', 1319, ['auth-register-password-confirm-label'], () => ({ text: '确认密码' })),
  uiCopy('auth-forgot-email-label', 1319, ['auth-forgot-email-label'], () => ({ text: '邮箱' })),
  uiCopy('auth-turnstile-expired-error', 1319, ['auth-turnstile-expired-error'], () => ({ text: '真人验证已过期，请重新完成验证。' })),
  uiCopy('auth-turnstile-load-error', 1319, ['auth-turnstile-load-error'], () => ({ text: '真人验证加载失败，请稍后重试。' })),
  uiCopy('auth-login-error', 1319, ['auth-login-error'], () => ({ text: '登录失败，请检查用户名和密码' })),
  uiCopy('auth-register-password-mismatch-error', 1319, ['auth-register-password-mismatch-error'], () => ({ text: '两次输入的密码不一致' })),
  uiCopy('auth-register-error', 1319, ['auth-register-error'], () => ({ text: '注册失败，请稍后重试' })),
  uiCopy('auth-register-success', 1319, ['auth-register-success'], () => ({ text: '注册成功，请检查邮箱完成验证。' })),
  uiCopy('auth-register-field-error', 1319, ['auth-register-field-error'], ({ field, message }) => ({ text: `${field}: ${message}` })),
  uiCopy('auth-forgot-error', 1319, ['auth-forgot-error'], () => ({ text: '发送失败，请稍后重试' })),
  uiCopy('auth-session-remember-me', 1320, ['auth-session-remember-me'], () => ({ text: '记住我' })),
  uiCopy('auth-session-forgot-link', 1330, ['auth-session-forgot-link'], () => ({ text: '忘记密码？' })),
  uiCopy('auth-session-no-account', 1340, ['auth-session-no-account'], () => ({ text: '还没有账号？' })),
  uiCopy('auth-session-switch-register', 1350, ['auth-session-switch-register'], () => ({ text: '立即注册' })),
  uiCopy('auth-session-has-account', 1360, ['auth-session-has-account'], () => ({ text: '已有账号？' })),
  uiCopy('auth-session-switch-login', 1370, ['auth-session-switch-login'], () => ({ text: '立即登录' })),
  uiCopy('auth-session-back-login', 1380, ['auth-session-back-login'], () => ({ text: '返回登录' })),
]

function uiCopy(key, order, surfaces, resolve, isVisible) {
  return {
    key,
    order,
    surfaces,
    ...(isVisible ? { isVisible } : {}),
    resolve,
  }
}

function registerProfilePanels(forum) {
  forum
    .profilePanel({
      key: 'discussions',
      moduleId: 'discussions',
      label: '讨论',
      icon: 'fas fa-bars',
      order: 10,
      badge: ({ user }) => Number(user?.discussion_count || 0),
      resolve: context => ({
        component: ProfileDiscussionSection,
        componentProps: {
          discussions: context.discussions,
          loading: context.loadingDiscussions,
          isOwnProfile: context.isOwnProfile,
          buildDiscussionPath: context.buildDiscussionPath,
          formatDate: context.formatDate,
        },
      }),
    })
    .profilePanel({
      key: 'posts',
      moduleId: 'posts',
      label: '回复',
      icon: 'far fa-comment',
      order: 20,
      badge: ({ user }) => Number(user?.comment_count || 0),
      resolve: context => ({
        component: ProfilePostSection,
        componentProps: {
          posts: context.posts,
          loading: context.loadingPosts,
          isOwnProfile: context.isOwnProfile,
          buildDiscussionPath: context.buildDiscussionPath,
          formatDate: context.formatDate,
        },
      }),
    })
    .profilePanel({
      key: 'settings',
      moduleId: 'users',
      label: '设置',
      icon: 'fas fa-user-cog',
      order: 30,
      isVisible: ({ isOwnProfile }) => Boolean(isOwnProfile),
      resolve: context => ({
        component: ProfileSettingsSection,
        componentProps: {
          user: context.user,
          editForm: context.editForm,
          preferences: context.preferences,
          saving: context.saving,
          settingsSuccess: context.settingsSuccess,
          settingsError: context.settingsError,
          loadingPreferences: context.loadingPreferences,
          savingPreferences: context.savingPreferences,
          preferencesSuccess: context.preferencesSuccess,
          preferencesError: context.preferencesError,
        },
        componentEvents: {
          saveProfile: context.saveProfile,
          savePreferences: context.savePreferences,
        },
      }),
    })
    .profilePanel({
      key: 'security',
      moduleId: 'users',
      label: '安全',
      icon: 'fas fa-shield-alt',
      order: 40,
      isVisible: ({ isOwnProfile }) => Boolean(isOwnProfile),
      resolve: context => ({
        component: ProfileSecuritySection,
        componentProps: {
          user: context.user,
          passwordForm: context.passwordForm,
          verificationSending: context.verificationSending,
          verificationSuccess: context.verificationSuccess,
          verificationError: context.verificationError,
          changingPassword: context.changingPassword,
          passwordSuccess: context.passwordSuccess,
          passwordError: context.passwordError,
        },
        componentEvents: {
          resendVerification: context.resendVerificationEmail,
          changePassword: context.changePassword,
        },
      }),
    })
}
