import { api, usePaginatedListState } from '@bias/core'

export function createSearchResultsLoadState({
  fetchSearch,
  getActiveSourceType,
  getErrorMessage,
  getNormalizedQuery,
  getPage,
  getSearchType,
  listStateFactory,
  onResponseLoaded,
  resetResults,
  setLoadError,
}) {
  let activeController = null
  let activeRequestId = 0

  function abortActiveRequest() {
    activeController?.abort()
  }

  function isCanceledRequest(error) {
    return error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError'
  }

  async function loadSearchResults() {
    const normalizedQuery = getNormalizedQuery()
    if (!normalizedQuery) {
      abortActiveRequest()
      resetResults()
      return null
    }

    abortActiveRequest()
    const requestId = activeRequestId + 1
    activeRequestId = requestId
    const controller = new AbortController()
    activeController = controller

    try {
      const data = await fetchSearch({
        page: getPage(),
        query: normalizedQuery,
        searchType: getSearchType(),
        sourceType: getActiveSourceType(),
        signal: controller.signal,
      })

      if (requestId !== activeRequestId) {
        return null
      }

      onResponseLoaded(data)
      setLoadError('')
      return data
    } catch (error) {
      if (isCanceledRequest(error)) {
        return null
      }
      throw error
    } finally {
      if (requestId === activeRequestId) {
        activeController = null
      }
    }
  }

  const listState = listStateFactory({
    async load() {
      return loadSearchResults()
    },
    reset: resetResults,
  })

  async function refreshResults() {
    try {
      await listState.refresh({
        mode: 'initial',
        forceLoading: Boolean(getNormalizedQuery()),
      })
    } catch (error) {
      console.error('加载搜索结果失败:', error)
      setLoadError(getErrorMessage(error))
      resetResults()
    }
  }

  return {
    abortActiveRequest,
    isCanceledRequest,
    listState,
    loadSearchResults,
    refreshResults,
  }
}

export function useSearchResultsLoadState({
  activeSource,
  normalizedQuery,
  page,
  resourceState,
  searchFilterCatalog,
  searchType,
}) {
  return createSearchResultsLoadState({
    async fetchSearch({ page: currentPage, query, searchType: currentSearchType, sourceType, signal }) {
      return api.get('/search', {
        params: {
          q: query,
          type: sourceType || currentSearchType,
          page: currentPage,
          limit: 20,
        },
        signal,
      })
    },
    getActiveSourceType() {
      return activeSource.value?.apiType || searchType.value
    },
    getErrorMessage(error) {
      return error.response?.data?.error
        || error.response?.data?.detail
        || error.message
        || '加载搜索结果失败，请稍后重试'
    },
    getNormalizedQuery() {
      return normalizedQuery.value
    },
    getPage() {
      return page.value
    },
    getSearchType() {
      return searchType.value
    },
    listStateFactory({ load, reset }) {
      return usePaginatedListState({
        watchSources: () => [normalizedQuery.value, searchType.value, page.value],
        initialLoading: false,
        load,
        reset,
      })
    },
    onResponseLoaded(data) {
      resourceState.applySearchResponse(data)
    },
    resetResults: resourceState.resetResults,
    setLoadError(message) {
      searchFilterCatalog.loadError.value = message
    },
  })
}
