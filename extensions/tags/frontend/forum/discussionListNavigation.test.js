import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildDiscussionListPrimaryTagItems,
  buildDiscussionListSecondaryTagItems,
  findDiscussionListSidebarContextParent,
  isDiscussionSidebarTagActive,
} from './discussionListNavigation.js'

test('tags sidebar navigation derives context ordering and active parent tags', () => {
  const normalizedTags = [
    {
      id: 1,
      slug: 'parent',
      position: 1,
      discussion_count: 5,
      children: [{ id: 2, slug: 'child' }],
    },
    {
      id: 2,
      slug: 'child',
      position: 2,
      parent_id: 1,
      discussion_count: 3,
      children: [],
    },
    {
      id: 3,
      slug: 'secondary',
      position: null,
      discussion_count: 9,
      children: [],
    },
  ]

  const contextParent = findDiscussionListSidebarContextParent('child', normalizedTags)
  assert.equal(contextParent?.slug, 'parent')
  assert.deepEqual(
    buildDiscussionListPrimaryTagItems(normalizedTags, contextParent).map(tag => tag.slug),
    ['parent', 'child']
  )
  assert.deepEqual(
    buildDiscussionListSecondaryTagItems(normalizedTags).map(tag => tag.slug),
    ['secondary']
  )
  assert.equal(isDiscussionSidebarTagActive({
    currentTag: { parent_id: 1 },
    currentTagSlug: 'child',
    normalizedTags,
    tag: { slug: 'parent' },
  }), true)
})
