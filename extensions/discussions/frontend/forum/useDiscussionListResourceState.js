
import {
  api,
  ref,
  computed,
  unwrapList,
  useResourceStore } from '@bias/core'
import { getDiscussionListRequests } from '@bias/discussions'
import { normalizeDiscussion } from '@bias/discussions'

export function useDiscussionListResourceState({
  discussionListContexts,
  isFollowingPage,
  listFilter,
  primaryDiscussionListContext,
  route,
  searchQuery,
  sortBy,
}) {
  const resourceStore = useResourceStore()
  const discussionIds = ref([])
  const contextSubject = ref(null)
  const contextSubjectKey = ref('')
  const discussionListContextData = ref({})
  const sortOptions = ref([])
  const filterOptions = ref([])
  const currentPage = ref(1)
  const total = ref(0)
  const pageSize = 20

  const discussions = computed(() => resourceStore.list('discussions', discussionIds.value))
  const hasMore = computed(() => currentPage.value * pageSize < total.value)
  const activeDiscussionListContexts = computed(() => Array.isArray(discussionListContexts?.value)
    ? discussionListContexts.value
    : [])
  const activeContextSubject = computed(() => {
    const contextSubjectValue = primaryDiscussionListContext?.value?.subject
    if (contextSubjectValue) {
      return contextSubjectValue
    }
    return contextSubject.value
  })

  function reset() {
    discussionIds.value = []
    contextSubject.value = null
    contextSubjectKey.value = ''
    discussionListContextData.value = {}
    currentPage.value = 1
    total.value = 0
  }

  async function loadInitialResources() {
    await Promise.all([loadExtensionResources(), loadDiscussions({ append: false })])
  }

  async function loadMoreDiscussions() {
    currentPage.value += 1
    try {
      await loadDiscussions({ append: true })
    } catch (error) {
      currentPage.value = Math.max(1, currentPage.value - 1)
      throw error
    }
  }

  async function refreshDiscussions() {
    await loadDiscussions({ append: false })
  }

  async function loadExtensionResources() {
    const contexts = activeDiscussionListContexts.value
    if (!contexts.length) {
      contextSubject.value = null
      contextSubjectKey.value = ''
      discussionListContextData.value = {}
      return
    }

    const results = await Promise.all(contexts.map(item => loadContextResources(item)))
    let nextContextSubject = null
    let nextContextSubjectKey = ''
    const nextContextData = {}
    for (const result of results) {
      if (!result) {
        continue
      }
      const contextKey = String(result.contextKey || result.key || '').trim()
      if (contextKey && result.contextData && typeof result.contextData === 'object') {
        nextContextData[contextKey] = result.contextData
      }
      if (result.subject !== undefined) {
        nextContextSubject = result.subject
      }
      if (result.subjectKey) {
        nextContextSubjectKey = String(result.subjectKey || '')
      }
    }
    contextSubject.value = nextContextSubject
    contextSubjectKey.value = nextContextSubjectKey
    discussionListContextData.value = nextContextData
  }

  async function loadContextResources(item) {
    if (typeof item.loadResources !== 'function') {
      return null
    }
    const result = await item.loadResources(buildDiscussionListResourceContext(item))
    if (!result || typeof result !== 'object') {
      return result
    }
    return {
      contextKey: item.key,
      ...result,
    }
  }

  async function loadDiscussions({ append }) {
    const response = await api.get('/discussions/', {
      params: buildDiscussionListRequestParams({
        page: currentPage.value,
        limit: pageSize,
        sort: sortBy.value,
        filter: listFilter.value,
        q: searchQuery.value || undefined,
      })
    })

    const items = unwrapList(response).map(normalizeDiscussion)
    const ids = items.map(item => resourceStore.upsert('discussions', item).id)

    discussionIds.value = append
      ? [...discussionIds.value, ...ids]
      : ids

    total.value = response.total || items.length
    sortOptions.value = Array.isArray(response.available_sorts) ? response.available_sorts : []
    filterOptions.value = Array.isArray(response.available_filters) ? response.available_filters : []
  }

  function buildDiscussionListResourceContext(item = {}) {
    return {
      api,
      context: item,
      contextSubject: activeContextSubject.value,
      contextSubjectKey: contextSubjectKey.value,
      isFollowingPage: isFollowingPage.value,
      listFilter: listFilter.value,
      resourceStore,
      route,
      searchQuery: searchQuery.value,
      sortBy: sortBy.value,
    }
  }

  function buildDiscussionListRequestParams(baseParams = {}) {
    const params = { ...baseParams }
    const requests = getDiscussionListRequests({
      contexts: activeDiscussionListContexts.value,
      contextSubject: activeContextSubject.value,
      contextSubjectKey: contextSubjectKey.value,
      isFollowingPage: isFollowingPage.value,
      listFilter: listFilter.value,
      params,
      route,
      searchQuery: searchQuery.value,
      sortBy: sortBy.value,
      surface: 'discussion-list-request',
    })

    for (const item of requests) {
      if (typeof item.apply === 'function') {
        const nextParams = item.apply({
          contexts: activeDiscussionListContexts.value,
          contextSubject: activeContextSubject.value,
          contextSubjectKey: contextSubjectKey.value,
          isFollowingPage: isFollowingPage.value,
          listFilter: listFilter.value,
          params,
          route,
          searchQuery: searchQuery.value,
          sortBy: sortBy.value,
        })
        if (nextParams && typeof nextParams === 'object') {
          Object.assign(params, nextParams)
        }
      } else if (item.params && typeof item.params === 'object') {
        Object.assign(params, item.params)
      }
    }

    return params
  }

  return {
    contextSubject: activeContextSubject,
    contextSubjectKey,
    currentPage,
    discussionIds,
    discussionListContextData,
    discussions,
    filterOptions,
    hasMore,
    loadInitialResources,
    loadMoreDiscussions,
    refreshDiscussions,
    reset,
    sortOptions,
    total,
  }
}
