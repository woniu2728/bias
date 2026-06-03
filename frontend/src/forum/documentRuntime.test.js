import test from 'node:test'
import assert from 'node:assert/strict'

import {
  applyExtensionDocumentPayload,
  applyExtensionDocumentState,
  clearExtensionDocumentRuntime,
  registerExtensionDocumentContent,
  registerExtensionTitleDriver,
  resolveExtensionPageMeta,
} from './documentRuntime.js'

function createDocumentRef() {
  const links = []
  const headTags = []
  const attributes = {}
  const classes = []
  return {
    links,
    headTags,
    attributes,
    classes,
    head: {
      appendChild(element) {
        if (element.tag === 'link') {
          links.push(element)
          return
        }
        headTags.push(element)
      },
    },
    documentElement: {
      classList: {
        add(...items) {
          classes.push(...items)
        },
      },
      setAttribute(key, value) {
        attributes[key] = value
      },
    },
    createElement(tag) {
      return {
        tag,
        attrs: {},
        textContent: '',
        setAttribute(key, value) {
          this.attrs[key] = value
        },
      }
    },
  }
}

test('document runtime applies title drivers and content callbacks by priority', () => {
  clearExtensionDocumentRuntime()
  const calls = []
  registerExtensionDocumentContent('late', ({ meta }) => {
    calls.push('late')
    return {
      meta: {
        description: `${meta.description || ''} late`.trim(),
      },
    }
  })
  registerExtensionDocumentContent('early', () => {
    calls.push('early')
    return {
      meta: {
        title: 'Early title',
      },
      documentAttributes: {
        dataRuntime: 'early',
      },
    }
  })
  registerExtensionTitleDriver('title', ({ meta }) => `${meta.title} / runtime`)

  applyExtensionDocumentPayload({
    extension_document: {
      title_drivers: [{ extension_id: 'alpha', driver: 'title' }],
      content_callbacks: [
        { extension_id: 'alpha', callback: 'late', priority: 10 },
        { extension_id: 'alpha', callback: 'early', priority: 30 },
      ],
    },
  }, { documentRef: null })

  const state = resolveExtensionPageMeta({ title: 'Base', description: 'Base description' })

  assert.deepEqual(calls, ['early', 'late'])
  assert.equal(state.meta.title, 'Early title / runtime')
  assert.equal(state.meta.description, 'Base description late')
  assert.deepEqual(state.documentAttributes, { dataRuntime: 'early' })
})

test('document runtime applies content mutations to document head', () => {
  clearExtensionDocumentRuntime()
  registerExtensionDocumentContent('head', () => ({
    preloads: [{ href: '/alpha.js', as: 'script' }],
    document_attributes: { dataAlpha: '1' },
    head_tags: [{ tag: 'meta', attributes: { name: 'alpha', content: 'enabled' } }],
  }))
  applyExtensionDocumentPayload({
    extension_document: {
      content_callbacks: [{ extension_id: 'alpha', callback: 'head', priority: 0 }],
    },
  }, { documentRef: null })

  const documentRef = createDocumentRef()
  const state = resolveExtensionPageMeta()
  applyExtensionDocumentState(state, { documentRef })

  assert.equal(documentRef.links[0].attrs.href, '/alpha.js')
  assert.equal(documentRef.links[0].attrs.as, 'script')
  assert.equal(documentRef.attributes['data-alpha'], '1')
  assert.equal(documentRef.headTags[0].tag, 'meta')
  assert.equal(documentRef.headTags[0].attrs.name, 'alpha')
  assert.equal(documentRef.headTags[0].attrs.content, 'enabled')
})

test('document runtime merges document classes from attributes', () => {
  const documentRef = createDocumentRef()

  applyExtensionDocumentPayload({
    extension_document: {
      document_attributes: {
        class: ['has-alpha', { 'has-beta': true, 'has-gamma': false }],
      },
    },
  }, { documentRef })

  assert.deepEqual(documentRef.classes, ['has-alpha', 'has-beta'])
})

test('document runtime applies theme variables as css custom properties', () => {
  const documentRef = createDocumentRef()

  applyExtensionDocumentPayload({
    extension_document: {
      theme_variables: {
        biasAlphaColor: '#123456',
        '--bias-beta-color': '#654321',
      },
    },
  }, { documentRef })

  const style = documentRef.headTags[0]
  assert.equal(style.tag, 'style')
  assert.equal(style.attrs['data-bias-extension-theme'], 'true')
  assert.match(style.textContent, /--bias-alpha-color:#123456;/)
  assert.match(style.textContent, /--bias-beta-color:#654321;/)
})
