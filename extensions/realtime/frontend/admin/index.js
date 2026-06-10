import { extendAdmin } from '@bias/admin'

export const extend = [
  extendAdmin(admin => admin
    .dashboardCopy({
      key: 'realtime-dashboard-copy',
      order: 30,
      moduleId: 'realtime',
      resolve: () => ({
        queueEnqueuedLabel: '入队',
        queueSyncLabel: '同步',
        queueFallbackLabel: '回退',
        queueLastTaskLabel: '最近任务',
      }),
    })
    .dashboardConfig({
      key: 'realtime-dashboard-config',
      order: 30,
      moduleId: 'realtime',
      resolve: () => ({
        defaultStats: {
          queueMetrics: {
            enqueued_count: 0,
            sync_count: 0,
            fallback_count: 0,
            last_task: '',
            last_error: '',
            last_event_at: '',
          },
        },
      }),
    })
    .dashboardActionMeta({
      key: 'realtime-dashboard-action-meta',
      order: 30,
      moduleId: 'realtime',
      resolve: () => ({
        queueResetIdleText: '重置指标',
        queueResetPendingText: '重置中...',
        queueResetConfirmTitle: '重置队列指标',
        queueResetConfirmMessage: '确定重置队列运行指标吗？当前累计的入队、同步和回退计数会清零。',
        queueResetConfirmText: '重置',
        queueResetCancelText: '取消',
        queueResetSuccessTitle: '指标已重置',
        queueResetSuccessMessage: '队列运行指标已重置',
        queueResetErrorMessage: '重置失败，请稍后重试',
      }),
    })
    .dashboardQueueMetric({
      key: 'queue-enqueued',
      order: 10,
      variant: 'stat',
      moduleId: 'realtime',
      resolve: ({ stats, copy }) => ({
        label: copy?.queueEnqueuedLabel || '入队',
        value: stats?.queueMetrics?.enqueued_count || 0,
      }),
    })
    .dashboardQueueMetric({
      key: 'queue-sync',
      order: 20,
      variant: 'stat',
      moduleId: 'realtime',
      resolve: ({ stats, copy }) => ({
        label: copy?.queueSyncLabel || '同步',
        value: stats?.queueMetrics?.sync_count || 0,
      }),
    })
    .dashboardQueueMetric({
      key: 'queue-fallback',
      order: 30,
      variant: 'stat',
      moduleId: 'realtime',
      resolve: ({ stats, copy }) => ({
        label: copy?.queueFallbackLabel || '回退',
        value: stats?.queueMetrics?.fallback_count || 0,
      }),
    })
    .dashboardQueueMetric({
      key: 'queue-last-task',
      order: 40,
      variant: 'detail',
      moduleId: 'realtime',
      resolve: ({ stats, copy }) => ({
        label: copy?.queueLastTaskLabel || '最近任务',
        value: stats?.queueMetrics?.last_task || copy?.emptyValueText || '-',
        error: stats?.queueMetrics?.last_error || '',
      }),
    })
    .dashboardAction({
      key: 'reset-queue-metrics',
      order: 10,
      moduleId: 'realtime',
      resolve: ({ api, modalStore, stats, setStats, setMessage, setMessageTone, setPending, copy }) => ({
        run: async () => {
          const confirmed = await modalStore.confirm({
            title: copy?.queueResetConfirmTitle || '重置队列指标',
            message: copy?.queueResetConfirmMessage || '确定重置队列运行指标吗？当前累计的入队、同步和回退计数会清零。',
            confirmText: copy?.queueResetConfirmText || '重置',
            cancelText: copy?.queueResetCancelText || '取消',
            tone: 'warning',
          })
          if (!confirmed) {
            return
          }

          setPending(true)
          setMessage('')
          setMessageTone('success')

          try {
            const data = await api.post('/admin/queue/metrics/reset')
            setStats({
              ...stats,
              queueMetrics: data.metrics || stats.queueMetrics,
            })
            const successMessage = data.message || copy?.queueResetSuccessMessage || '队列运行指标已重置'
            setMessage(successMessage)
            await modalStore.alert({
              title: copy?.queueResetSuccessTitle || '指标已重置',
              message: successMessage,
              tone: 'success',
            })
          } catch (error) {
            console.error('重置队列指标失败:', error)
            setMessageTone('error')
            setMessage(error.response?.data?.error || copy?.queueResetErrorMessage || '重置失败，请稍后重试')
          } finally {
            setPending(false)
          }
        },
      }),
    }))
]

export function resolveDetailPage() {
  return null
}
