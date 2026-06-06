import test from 'node:test'
import assert from 'node:assert/strict'

import {
  normalizeExtensionFrontendEntry,
  registerExtensionFrontendOutput,
  resolveExtensionRouteComponent,
  resolveExtensionRouteComponentKeys,
  withRuntimeApplication,
} from './extensionRouteRuntime.js'

test('extension route runtime normalizes extension frontend entries', () => {
  assert.equal(
    normalizeExtensionFrontendEntry('extensions/alpha/frontend/forum/index.js'),
    '../../../extensions/alpha/frontend/forum/index.js',
  )
  assert.equal(
    normalizeExtensionFrontendEntry('..\\..\\extensions\\alpha\\frontend\\forum\\index.js'),
    '../../extensions/alpha/frontend/forum/index.js',
  )
  assert.equal(normalizeExtensionFrontendEntry(''), '')
})

test('extension route runtime resolves canonical route component keys', () => {
  assert.deepEqual(resolveExtensionRouteComponentKeys('./Page.vue', {
    id: 'alpha',
    frontend_forum_entry: 'extensions/alpha/frontend/forum/index.js',
  }, {
    frontend: 'forum',
  }), [
    'alpha:./Page.vue',
    'alpha:extensions/alpha/frontend/forum/Page.vue',
    'extensions/alpha/frontend/forum/Page.vue',
    '../../../extensions/alpha/frontend/forum/Page.vue',
    './Page.vue',
  ])

  assert.deepEqual(resolveExtensionRouteComponentKeys('frontend/forum/Deep/Page.vue', {
    id: 'alpha',
  }, {
    frontend: 'forum',
  }), [
    'alpha:frontend/forum/Deep/Page.vue',
    'alpha:extensions/alpha/frontend/forum/Deep/Page.vue',
    'extensions/alpha/frontend/forum/Deep/Page.vue',
    '../../../extensions/alpha/frontend/forum/Deep/Page.vue',
    'frontend/forum/Deep/Page.vue',
  ])
})

test('extension route runtime resolves components from importers first', async () => {
  const component = { name: 'AlphaPage' }
  const resolver = resolveExtensionRouteComponent('./Page.vue', {
    id: 'alpha',
    frontend_forum_entry: 'extensions/alpha/frontend/forum/index.js',
  }, {
    frontend: 'forum',
    importers: {
      '../../../extensions/alpha/frontend/forum/Page.vue': async () => ({ default: component }),
    },
  })

  assert.equal(await resolver(), component)
})

test('extension route runtime falls back to export registry chunks', async () => {
  const component = { name: 'ChunkPage' }
  const imported = []
  const application = {
    exportRegistry: {
      async asyncModuleImport(path) {
        imported.push(path)
        if (path === 'extensions/alpha/frontend/forum/Page.vue') {
          return { default: component }
        }
        throw new Error(`missing ${path}`)
      },
    },
  }

  const extension = withRuntimeApplication({
    id: 'alpha',
    frontend_forum_entry: 'extensions/alpha/frontend/forum/index.js',
  }, application)

  const resolver = resolveExtensionRouteComponent('./Page.vue', extension, {
    frontend: 'forum',
  })

  assert.equal(extension.application, application)
  assert.equal(await resolver(), component)
  assert.deepEqual(imported, ['extensions/alpha/frontend/forum/Page.vue'])
})

test('extension route runtime registers vite output through application registry', () => {
  const calls = []
  const output = {
    revision: 'rev1',
    chunks: [{ file: 'assets/alpha.js', module_id: 'frontend/forum/Page.vue' }],
  }
  const application = {
    exportRegistry: {
      registerViteOutput(extensionId, frontend, registeredOutput, options) {
        calls.push({ extensionId, frontend, registeredOutput, options })
        return ['registered']
      },
    },
  }

  const result = registerExtensionFrontendOutput(application, 'alpha', 'forum', output, {
    baseUrl: '/static/custom',
  })

  assert.deepEqual(result, ['registered'])
  assert.deepEqual(calls, [{
    extensionId: 'alpha',
    frontend: 'forum',
    registeredOutput: output,
    options: { baseUrl: '/static/custom' },
  }])
})
