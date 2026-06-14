import { extendAdmin } from '@bias/admin'

const ADVANCED_PAGE_KEY = 'core.advanced'

export const extend = [
  extendAdmin(admin => admin
    .pageCopy(ADVANCED_PAGE_KEY, {
      key: 'search-advanced-copy',
      moduleId: 'search',
      order: 25,
      resolve: () => ({
        searchSectionTitle: '搜索索引',
        searchStatusLabel: '当前状态',
        searchStatusHintText: '查看当前索引与队列运行状态。',
        searchStatusLoadingText: '加载中...',
        searchDatabaseLabel: '当前数据库',
        searchLastRebuildLabel: '最近重建',
        searchNeverRebuiltText: '尚未重建',
        searchLastRebuildDurationFallback: '最近一次重建未记录耗时。',
        searchLastRebuildDurationText: durationMs => `最近一次耗时 ${durationMs} ms`,
        searchQueueStatusLabel: '索引队列状态',
        searchQueueStatusHelpText: '当前重建按钮仍是请求内执行，后续异步索引任务会复用这里的队列运行状态。',
        searchMissingIndexesLabel: '缺失索引',
        searchIndexLabel: 'PostgreSQL 全文索引',
        searchIndexHelpText: '用于英文、数字关键词的讨论、回复和用户搜索。数据量较大时请在低峰期执行。',
        rebuildSearchIndexesLabel: '重建搜索索引',
        rebuildingSearchIndexesLabel: '重建中...',
      }),
    })
    .pageConfig(ADVANCED_PAGE_KEY, {
      key: 'search-advanced-config',
      moduleId: 'search',
      order: 25,
      resolve: () => ({
        enableSearchIndexSection: true,
      }),
    })
    .pageActionMeta(ADVANCED_PAGE_KEY, {
      key: 'search-advanced-action-meta',
      moduleId: 'search',
      order: 25,
      resolve: () => ({
        loadSearchStatusErrorText: '加载搜索索引状态失败，请稍后重试',
        rebuildSearchConfirmTitle: '重建搜索索引',
        rebuildSearchConfirmMessage: '确定在后台重建 PostgreSQL 全文搜索索引吗？数据量较大时可能耗时较长，建议在低峰期执行。',
        rebuildSearchConfirmText: '重建',
        rebuildSearchCancelText: '取消',
        rebuildSearchSuccessTitle: '搜索索引已重建',
        rebuildSearchSuccessMessage: result => `已重建 ${Array.isArray(result?.indexes) ? result.indexes.length : 0} 个搜索索引。`,
        rebuildSearchFailedTitle: '重建搜索索引失败',
      }),
    }))
]

export function resolveDetailPage() {
  return null
}
