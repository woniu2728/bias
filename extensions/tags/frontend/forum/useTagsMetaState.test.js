import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, ref } from '@bias/forum'
import { createTagsMetaState } from './useTagsMetaState.js'

test('tags meta state resolves hero and state copy', () => {
  const state = createTagsMetaState({
    forumStore: { setPageMeta() {} },
    getEmptyStateBlock: ({ surface }) => ({ text: `${surface}-copy` }),
    getStateText: ({ surface }) => ({ text: `${surface}-copy` }),
    getText: ({ surface }) => ({ text: `${surface}-copy` }),
    loading: ref(true),
    tags: ref([{ id: 1 }]),
  })

  assert.equal(state.heroTitleText.value, 'tags-page-hero-title-copy')
  assert.equal(state.heroDescriptionText.value, 'tags-page-hero-description-copy')
  assert.equal(state.emptyStateText.value, 'tags-page-empty-copy')
  assert.equal(state.loadingStateText.value, 'tags-page-loading-copy')
})

test('tags meta state syncs page meta when tag count changes', async () => {
  const calls = []
  const tags = ref([{ id: 1 }, { id: 2 }])

  createTagsMetaState({
    forumStore: {
      setPageMeta(payload) {
        calls.push(payload)
      },
    },
    getText: ({ surface, tagCount }) => {
      if (surface === 'tags-page-hero-title') {
        return { text: '标签广场' }
      }
      if (surface === 'tags-page-hero-description') {
        return { text: `当前共有 ${tagCount} 个标签` }
      }
      return null
    },
    loading: ref(false),
    tags,
  })

  tags.value = [{ id: 1 }, { id: 2 }, { id: 3 }]

  await nextTick()

  assert.deepEqual(calls, [
    {
      title: '标签广场',
      description: '当前共有 2 个标签',
      canonicalUrl: '/tags',
    },
    {
      title: '标签广场',
      description: '当前共有 3 个标签',
      canonicalUrl: '/tags',
    },
  ])
})
