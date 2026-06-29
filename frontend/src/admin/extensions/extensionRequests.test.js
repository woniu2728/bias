import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildAdminExtensionSummaryRequest,
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
