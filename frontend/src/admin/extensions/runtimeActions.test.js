import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildRuntimeActionRequest,
  postRuntimeAction,
  resolveRuntimeActionPayload,
} from './runtimeActions.js'

test('resolveRuntimeActionPayload clones object payloads only', () => {
  const payload = { include_dependencies: true }
  const result = resolveRuntimeActionPayload({ payload })

  assert.deepEqual(result, payload)
  assert.notEqual(result, payload)
  assert.deepEqual(resolveRuntimeActionPayload({ payload: null }), {})
  assert.deepEqual(resolveRuntimeActionPayload({ payload: ['x'] }), {})
})

test('buildRuntimeActionRequest preserves lifecycle transaction payloads', () => {
  assert.deepEqual(
    buildRuntimeActionRequest('alpha-tools', {
      action: 'enable',
      payload: { include_dependencies: true },
    }),
    {
      url: '/admin/extensions/alpha-tools/enable',
      payload: { include_dependencies: true },
    },
  )

  assert.deepEqual(
    buildRuntimeActionRequest('beta-tools', {
      action: 'disable',
      payload: { include_dependents: true },
    }),
    {
      url: '/admin/extensions/beta-tools/disable',
      payload: { include_dependents: true },
    },
  )
})

test('buildRuntimeActionRequest ignores payloads for runtime hooks', () => {
  assert.deepEqual(
    buildRuntimeActionRequest('alpha-tools', {
      action: 'hook:run_rebuild_cache',
      payload: { include_dependencies: true },
    }),
    {
      url: '/admin/extensions/alpha-tools/runtime-hooks/run_rebuild_cache',
      payload: {},
    },
  )
})

test('buildRuntimeActionRequest rejects incomplete runtime actions', () => {
  assert.equal(buildRuntimeActionRequest('', { action: 'enable' }), null)
  assert.equal(buildRuntimeActionRequest('alpha-tools', {}), null)
  assert.equal(buildRuntimeActionRequest('alpha-tools', { action: '   ' }), null)
})

test('postRuntimeAction posts the resolved url and payload', async () => {
  const calls = []
  const api = {
    post(url, payload) {
      calls.push({ url, payload })
      return Promise.resolve({ ok: true })
    },
  }

  const result = await postRuntimeAction(api, 'beta-tools', {
    action: 'uninstall',
    payload: { include_dependents: true },
  })

  assert.deepEqual(result, { ok: true })
  assert.deepEqual(calls, [{
    url: '/admin/extensions/beta-tools/uninstall',
    payload: { include_dependents: true },
  }])
})

test('postRuntimeAction skips invalid action requests', async () => {
  const api = {
    post() {
      throw new Error('should not post invalid runtime actions')
    },
  }

  assert.equal(await postRuntimeAction(api, '', { action: 'enable' }), null)
  assert.equal(await postRuntimeAction(api, 'alpha-tools', {}), null)
})
