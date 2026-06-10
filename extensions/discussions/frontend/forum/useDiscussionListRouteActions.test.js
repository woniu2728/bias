import test from 'node:test'
import assert from 'node:assert/strict'
import { useDiscussionListRouteActions } from './useDiscussionListRouteActions.js'

test('discussion list route actions skip sort navigation when value is unchanged', async () => {
  const pushes = []
  const actions = useDiscussionListRouteActions({
    routeState: {
      push: async payload => {
        pushes.push(payload)
      },
    },
    listFilter: { value: 'all' },
    searchQuery: { value: '' },
    sortBy: { value: 'latest' },
  })

  await actions.changeSortBy('latest')

  assert.deepEqual(pushes, [])
})

test('discussion list route actions preserve sibling state on sort/filter/search changes', async () => {
  const pushes = []
  const actions = useDiscussionListRouteActions({
    routeState: {
      push: async payload => {
        pushes.push(payload)
      },
    },
    listFilter: { value: 'unread' },
    searchQuery: { value: '维护' },
    sortBy: { value: 'top' },
  })

  await actions.changeSortBy('latest')
  await actions.changeListFilter('my')
  await actions.changeSearchQuery('恢复')

  assert.deepEqual(pushes, [
    {
      sortBy: 'latest',
      listFilter: 'unread',
      searchQuery: '维护',
    },
    {
      listFilter: 'my',
      sortBy: 'top',
      searchQuery: '维护',
    },
    {
      searchQuery: '恢复',
      sortBy: 'top',
      listFilter: 'unread',
    },
  ])
})
