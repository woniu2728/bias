import {
  registerAdminDashboardActionMeta,
  registerAdminDashboardAlert,
  registerAdminDashboardConfig,
  registerAdminDashboardCopy,
  registerAdminDashboardStat,
  registerAdminDashboardStatusBadge,
  registerAdminDashboardStatusItem,
  registerAdminDashboardStatusSummary,
} from '../dashboard.js'

registerAdminDashboardStat({
  key: 'users',
  order: 10,
  icon: 'fas fa-users',
  moduleId: 'core',
  resolve: ({ stats, copy }) => ({
    label: copy?.usersStatLabel || '用户总数',
    value: stats?.totalUsers || 0,
  }),
})

registerAdminDashboardStat({
  key: 'discussions',
  order: 20,
  icon: 'fas fa-comments',
  moduleId: 'core',
  resolve: ({ stats, copy }) => ({
    label: copy?.discussionsStatLabel || '讨论总数',
    value: stats?.totalDiscussions || 0,
  }),
})

registerAdminDashboardStat({
  key: 'posts',
  order: 30,
  icon: 'fas fa-comment',
  moduleId: 'core',
  resolve: ({ stats, copy }) => ({
    label: copy?.postsStatLabel || '帖子总数',
    value: stats?.totalPosts || 0,
  }),
})

registerAdminDashboardStatusSummary({
  key: 'runtime',
  order: 10,
  resolve: ({ stats, copy }) => ({
    label: copy?.runtimeSummaryLabel || '运行时',
    value: stats?.runtimeName || copy?.runtimeNameFallback || 'Python',
    meta: `${copy?.pythonMetaPrefix || 'Python'} ${stats?.pythonVersion || copy?.emptyValueText || '-'}`,
  }),
})

registerAdminDashboardStatusBadge({
  key: 'debug-mode',
  order: 10,
  resolve: ({ stats, copy }) => ({
    text: stats?.debugMode ? (copy?.debugModeOnText || 'DEBUG') : (copy?.debugModeOffText || 'PRODUCTION'),
    tone: stats?.debugMode ? 'warning' : 'success',
  }),
})

registerAdminDashboardStatusBadge({
  key: 'maintenance-mode',
  order: 20,
  resolve: ({ stats, copy }) => ({
    text: stats?.maintenanceMode ? (copy?.maintenanceModeOnText || '维护模式开启') : (copy?.maintenanceModeOffText || '维护模式关闭'),
    tone: stats?.maintenanceMode ? 'warning' : 'neutral',
  }),
})

registerAdminDashboardStatusBadge({
  key: 'redis-status',
  order: 30,
  resolve: ({ stats, copy }) => ({
    text: !stats?.redisEnabled
      ? (copy?.redisDisabledText || 'Redis 未启用')
      : (stats?.cacheConnectionAvailable === false || stats?.queueBrokerAvailable === false
          ? (copy?.redisUnavailableText || 'Redis 已配置但不可用')
          : (copy?.redisEnabledText || 'Redis 已启用')),
    tone: !stats?.redisEnabled
      ? 'neutral'
      : (stats?.cacheConnectionAvailable === false || stats?.queueBrokerAvailable === false ? 'warning' : 'success'),
  }),
})

registerAdminDashboardStatusBadge({
  key: 'queue-worker-status',
  order: 40,
  resolve: ({ stats, copy }) => ({
    text: stats?.queueWorkerLabel || copy?.queueWorkerUndetectedText || '队列未检测',
    tone: !stats?.queueEnabled || ['disabled', 'sync'].includes(stats?.queueWorkerStatus)
      ? 'neutral'
      : (stats?.queueWorkerAvailable ? 'success' : 'warning'),
  }),
})

registerAdminDashboardStatusItem({
  key: 'python-version',
  order: 10,
  resolve: ({ stats, copy }) => ({
    label: copy?.pythonVersionLabel || 'Python 版本',
    value: stats?.pythonVersion || copy?.emptyValueText || '-',
  }),
})

registerAdminDashboardStatusItem({
  key: 'django-version',
  order: 20,
  resolve: ({ stats, copy }) => ({
    label: copy?.djangoVersionLabel || 'Django 版本',
    value: stats?.djangoVersion || copy?.emptyValueText || '-',
  }),
})

registerAdminDashboardStatusItem({
  key: 'database',
  order: 30,
  resolve: ({ stats, copy }) => ({
    label: copy?.databaseLabel || '数据库',
    value: stats?.databaseLabel || copy?.emptyValueText || '-',
  }),
})

registerAdminDashboardStatusItem({
  key: 'cache-driver',
  order: 40,
  resolve: ({ stats, copy }) => ({
    label: copy?.cacheDriverLabel || '缓存驱动',
    value: stats?.cacheDriver || copy?.emptyValueText || '-',
  }),
})

registerAdminDashboardStatusItem({
  key: 'realtime-driver',
  order: 50,
  resolve: ({ stats, copy }) => ({
    label: copy?.realtimeDriverLabel || '实时层',
    value: stats?.realtimeDriver || copy?.emptyValueText || '-',
  }),
})

registerAdminDashboardStatusItem({
  key: 'queue-driver',
  order: 60,
  resolve: ({ stats, copy }) => ({
    label: copy?.queueDriverLabel || '队列执行',
    value: stats?.queueLabel || copy?.emptyValueText || '-',
  }),
})

registerAdminDashboardStatusItem({
  key: 'queue-worker',
  order: 70,
  resolve: ({ stats, copy }) => ({
    label: copy?.queueWorkerLabel || '队列 Worker',
    value: stats?.queueWorkerLabel || copy?.emptyValueText || '-',
    help: stats?.queueWorkerMessage || '',
  }),
})

registerAdminDashboardStatusItem({
  key: 'auth-secret-status',
  order: 80,
  resolve: ({ stats, copy }) => ({
    label: copy?.authSecretStatusLabel || '认证密钥',
    value: stats?.authSecretLabel || copy?.emptyValueText || '-',
    help: stats?.authSecretMessage || '',
  }),
})

registerAdminDashboardAlert({
  key: 'runtime-risks',
  order: 10,
  isVisible: ({ stats }) => Array.isArray(stats?.runtimeRisks) && stats.runtimeRisks.length > 0,
  resolve: ({ stats, copy }) => {
    const risks = Array.isArray(stats?.runtimeRisks) ? stats.runtimeRisks : []
    return {
      title: copy?.runtimeRiskAlertTitle || '运行时风险提示：',
      tone: risks.some(item => item?.level === 'danger') ? 'danger' : 'warning',
      text: risks.map(item => item.title).join('；'),
    }
  },
})

registerAdminDashboardCopy({
  key: 'core-dashboard-copy',
  order: 10,
  resolve: () => ({
    pageTitle: '仪表盘',
    pageDescription: '查看论坛概况和系统状态',
    loadingText: '加载中...',
    statusWidgetTitle: '系统状态',
    statsWidgetTitle: '论坛统计',
    actionsWidgetTitle: '快速操作',
    runtimeRiskAlertTitle: '运行时风险提示：',
    runtimeSummaryLabel: '运行时',
    runtimeNameFallback: 'Python',
    pythonMetaPrefix: 'Python',
    debugModeOnText: 'DEBUG',
    debugModeOffText: 'PRODUCTION',
    maintenanceModeOnText: '维护模式开启',
    maintenanceModeOffText: '维护模式关闭',
    redisEnabledText: 'Redis 已启用',
    redisDisabledText: 'Redis 未启用',
    redisUnavailableText: 'Redis 已配置但不可用',
    queueWorkerUndetectedText: '队列未检测',
    authSecretStatusLabel: '认证密钥',
    usersStatLabel: '用户总数',
    discussionsStatLabel: '讨论总数',
    postsStatLabel: '帖子总数',
    pendingApprovalsStatLabel: '待审核内容',
    openFlagsStatLabel: '待处理举报',
    pythonVersionLabel: 'Python 版本',
    djangoVersionLabel: 'Django 版本',
    databaseLabel: '数据库',
    cacheDriverLabel: '缓存驱动',
    realtimeDriverLabel: '实时层',
    queueDriverLabel: '队列执行',
    queueWorkerLabel: '队列 Worker',
    emptyValueText: '-',
  }),
})

registerAdminDashboardConfig({
  key: 'core-dashboard-config',
  order: 10,
  resolve: () => ({
    defaultStats: {
      runtimeName: 'Python',
      pythonVersion: null,
      djangoVersion: null,
      databaseLabel: null,
      cacheDriver: null,
      queueDriver: null,
      queueEnabled: false,
      queueLabel: null,
      queueWorkerStatus: 'disabled',
      queueWorkerLabel: null,
      queueWorkerAvailable: false,
      queueWorkerCount: 0,
      queueWorkerMessage: '',
      authSecretStatus: 'healthy',
      authSecretLabel: '健康',
      authSecretMessage: '',
      realtimeDriver: null,
      redisEnabled: false,
      cacheConnectionStatus: 'disabled',
      cacheConnectionLabel: '',
      cacheConnectionAvailable: null,
      cacheConnectionMessage: '',
      realtimeConnectionStatus: 'disabled',
      realtimeConnectionLabel: '',
      realtimeConnectionAvailable: null,
      realtimeConnectionMessage: '',
      queueBrokerStatus: 'disabled',
      queueBrokerLabel: '',
      queueBrokerAvailable: null,
      queueBrokerMessage: '',
      runtimeRisks: [],
      debugMode: false,
      maintenanceMode: false,
      totalUsers: 0,
      totalDiscussions: 0,
      totalPosts: 0,
      pendingApprovals: 0,
      openFlags: 0,
    },
  }),
})

registerAdminDashboardActionMeta({
  key: 'core-dashboard-actions-meta',
  order: 10,
  resolve: () => ({
    loadingErrorText: '加载统计数据失败，请稍后重试',
  }),
})
