import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildAdminExtensionDetailListRequest,
  buildAdminExtensionSummaryRequest,
  fetchAdminExtensionDetailList,
  fetchAdminExtensionSummaries,
} from './extensionRequests.js'

test('buildAdminExtensionSummaryRequest asks for lightweight extension summaries', () => {
  assert.deepEqual(buildAdminExtensionSummaryRequest(), {
    url: '/admin/extensions',
    options: {
      params: { summary: 1 },
    },
  })
})

test('fetchAdminExtensionSummaries sends the summary request', async () => {
  const calls = []
  const api = {
    get(url, options) {
      calls.push({ url, options })
      return Promise.resolve({ extensions: [] })
    },
  }

  const result = await fetchAdminExtensionSummaries(api)

  assert.deepEqual(result, { extensions: [] })
  assert.deepEqual(calls, [{
    url: '/admin/extensions',
    options: { params: { summary: 1 } },
  }])
})

test('buildAdminExtensionDetailListRequest asks for full extension details', () => {
  assert.deepEqual(buildAdminExtensionDetailListRequest(), {
    url: '/admin/extensions',
    options: {},
  })
})

test('fetchAdminExtensionDetailList sends the full detail request', async () => {
  const calls = []
  const api = {
    get(url, options) {
      calls.push({ url, options })
      return Promise.resolve({ extensions: [], runtime: { package_lock: {} } })
    },
  }

  const result = await fetchAdminExtensionDetailList(api)

  assert.deepEqual(result, { extensions: [], runtime: { package_lock: {} } })
  assert.deepEqual(calls, [{
    url: '/admin/extensions',
    options: {},
  }])
})
