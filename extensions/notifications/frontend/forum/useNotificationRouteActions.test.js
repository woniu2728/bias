import test from 'node:test'
import assert from 'node:assert/strict'
import { useNotificationRouteActions } from './useNotificationRouteActions.js'

test('notification route actions skip unchanged type and view mode updates', async () => {
  const calls = []
  const actions = useNotificationRouteActions({
    activeType: { value: 'mention' },
    currentPage: { value: 2 },
    routePagination: {
      async changePage(page, options) {
        calls.push(['changePage', page, options])
        return true
      },
      async resetPage(payload) {
        calls.push(['resetPage', payload])
      },
    },
    unreadOnly: { value: false },
    viewMode: { value: 'timeline' },
  })

  const changedType = await actions.changeType('mention')
  const changedMode = await actions.changeViewMode('other')

  assert.equal(changedType, false)
  assert.equal(changedMode, false)
  assert.deepEqual(calls, [])
})

test('notification route actions reset page while preserving normalized filter state', async () => {
  const calls = []
  const actions = useNotificationRouteActions({
    activeType: { value: '' },
    currentPage: { value: 4 },
    routePagination: {
      async changePage(page, options) {
        calls.push(['changePage', page, options])
        return page !== 4
      },
      async resetPage(payload) {
        calls.push(['resetPage', payload])
      },
    },
    unreadOnly: { value: false },
    viewMode: { value: 'timeline' },
  })

  const changedType = await actions.changeType(' approval ')
  const toggledUnread = await actions.toggleUnreadOnly()
  const changedMode = await actions.changeViewMode('grouped')
  const changedPage = await actions.changePage(3)

  assert.equal(changedType, true)
  assert.equal(toggledUnread, true)
  assert.equal(changedMode, true)
  assert.equal(changedPage, true)
  assert.deepEqual(calls, [
    ['resetPage', { activeType: 'approval' }],
    ['resetPage', { unreadOnly: true }],
    ['resetPage', { viewMode: 'grouped' }],
    ['changePage', 3, { scroll: false }],
  ])
})
