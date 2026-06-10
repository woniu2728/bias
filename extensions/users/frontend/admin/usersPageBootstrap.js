import { extendAdmin } from '@bias/admin'

const PAGE_KEY = 'core.users'
const ADVANCED_PAGE_KEY = 'core.advanced'

export function buildUsersPageExtender() {
  return extendAdmin(admin => admin
    .dashboardStat({
      key: 'users',
      order: 10,
      icon: 'fas fa-users',
      moduleId: 'users',
      resolve: ({ stats, copy }) => ({
        label: copy?.usersStatLabel || '用户总数',
        value: stats?.totalUsers || 0,
      }),
    })
    .pageCopy(PAGE_KEY, {
      key: 'core-users-page-copy',
      order: 10,
      resolve: () => ({
        pageTitle: '用户管理',
        pageDescription: '管理论坛用户',
        searchLabel: '搜索用户',
        searchPlaceholder: '搜索用户名或邮箱...',
        tableIdHeader: 'ID',
        tableUsernameHeader: '用户名',
        tableEmailHeader: '邮箱',
        tableDisplayNameHeader: '显示名称',
        tableDiscussionHeader: '讨论',
        tableReplyHeader: '回复',
        tableJoinedHeader: '加入时间',
        tableStatusHeader: '状态',
        tableActionHeader: '操作',
        loadingText: '加载中...',
        emptyText: '暂无用户',
        editLabel: '编辑',
        mobileEmailLabel: '邮箱',
        mobileIdLabel: 'ID',
        mobileDiscussionLabel: '讨论',
        mobileReplyLabel: '回复',
        mobileJoinedLabel: '加入时间',
        modalTitle: '编辑用户',
        usernameLabel: '用户名',
        emailLabel: '邮箱',
        displayNameLabel: '显示名称',
        bioLabel: '个人简介',
        bioPlaceholder: '管理员后台可直接维护用户简介',
        staffLabel: '管理员',
        emailConfirmedLabel: '邮箱已验证',
        groupsLabel: '用户组',
        suspendedUntilLabel: '封禁截止时间',
        suspendedUntilHelpText: '留空表示未封禁',
        suspendReasonLabel: '封禁原因',
        suspendReasonPlaceholder: '例如：垃圾广告、违规内容',
        suspendMessageLabel: '对用户显示的信息',
        suspendMessagePlaceholder: '显示给被封禁用户的提示',
        deleteLabel: '删除用户',
        deletingLabel: '删除中...',
        cancelLabel: '取消',
        saveLabel: '保存',
        savingLabel: '保存中...',
        deleteBlockedText: '当前登录管理员账号不允许删除',
        statusSuspendedLabel: '已封禁',
        statusActiveLabel: '已激活',
        statusPendingLabel: '未激活',
        riskAdminLabel: '管理员权限',
        riskGroupLabel: '用户组',
        riskSuspensionLabel: '封禁状态',
        noEmailValueText: '-',
      }),
    })
    .pageConfig(PAGE_KEY, {
      key: 'core-users-page-config',
      order: 10,
      resolve: () => ({
        searchDebounceMs: 500,
        paginationLimit: 20,
        dateLocale: 'zh-CN',
        groupBadgeFallbackColor: '#7f8c8d',
        groupFallbackUnknownLabel: '?',
      }),
    })
    .pageActionMeta(PAGE_KEY, {
      key: 'core-users-page-actions-meta',
      order: 10,
      resolve: () => ({
        loadUsersFailedMessage: '加载用户失败，请稍后重试',
        loadGroupsFailedTitle: '加载用户组失败',
        loadGroupsFailedMessage: '未知错误',
        loadDetailFailedTitle: '加载用户详情失败',
        loadDetailFailedMessage: '未知错误',
        saveRiskConfirmTitle: '保存用户变更',
        saveRiskConfirmMessage: changes => `以下变更会立即影响用户权限或账号状态：${changes}。确定保存吗？`,
        saveConfirmText: '保存',
        saveCancelText: '取消',
        saveSuccessTitle: '用户已保存',
        saveSuccessMessage: '用户资料和状态已更新。',
        saveFailedTitle: '保存失败',
        saveFailedMessage: '未知错误',
        deleteConfirmTitle: '删除用户',
        deleteConfirmMessage: user => `确定删除用户“${user}”吗？该操作不可撤销。`,
        deleteConfirmText: '删除',
        deleteCancelText: '取消',
        deleteSuccessTitle: '用户已删除',
        deleteSuccessMessage: user => `用户“${user}”已删除。`,
        deleteFailedTitle: '删除失败',
        deleteFailedMessage: '未知错误',
      }),
    })
    .pageCopy(ADVANCED_PAGE_KEY, {
      key: 'users-human-verification-advanced-copy',
      moduleId: 'users',
      order: 20,
      resolve: () => ({
        humanVerificationSectionTitle: '安全与真人验证',
        humanVerificationProviderLabel: '验证提供方',
        humanVerificationProviderHelpText: '建议正式环境开启，优先拦截登录和注册机器人。',
        turnstileSiteKeyLabel: 'Site Key',
        turnstileSecretKeyLabel: 'Secret Key',
        turnstileLoginEnabledLabel: '登录时启用真人验证',
        turnstileRegisterEnabledLabel: '注册时启用真人验证',
        turnstileMisconfiguredText: '已选择 Turnstile，但 Site Key 或 Secret Key 仍为空，当前不会真正启用验证。',
      }),
    })
    .pageConfig(ADVANCED_PAGE_KEY, {
      key: 'users-human-verification-advanced-config',
      moduleId: 'users',
      order: 20,
      resolve: () => ({
        enableHumanVerificationSection: true,
        defaultSettings: {
          auth_human_verification_provider: 'off',
          auth_turnstile_site_key: '',
          auth_turnstile_secret_key: '',
          auth_human_verification_login_enabled: true,
          auth_human_verification_register_enabled: true,
        },
        placeholders: {
          turnstileSiteKey: '0x4AAAA...',
          turnstileSecretKey: '0x4AAAA...',
        },
        humanVerificationProviderOptions: [
          { value: 'off', label: '关闭' },
          { value: 'turnstile', label: 'Cloudflare Turnstile' },
        ],
      }),
    }))
}
