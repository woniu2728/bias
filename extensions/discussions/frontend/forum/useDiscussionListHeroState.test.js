import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDiscussionListHeroState } from './useDiscussionListHeroState.js'

test('discussion list hero state resolves filter hero copy and icon', () => {
  const state = createDiscussionListHeroState({
    contextSubject: ref(null),
    getHero: ({ activeFilterCode }) => ({
      title: `hero:${activeFilterCode}`,
      icon: 'fas fa-inbox',
    }),
    isFollowingPage: ref(false),
    listFilter: ref('unread'),
  })

  assert.equal(state.activeFilterCode.value, 'unread')
  assert.deepEqual(state.hero.value, {
    title: 'hero:unread',
    icon: 'fas fa-inbox',
  })
})

test('discussion list hero state passes context subject into registered resolver', () => {
  const state = createDiscussionListHeroState({
    contextSubject: ref({ name: '公告' }),
    getHero: ({ contextSubject }) => ({
      title: contextSubject.name,
      description: 'tag hero',
    }),
    isFollowingPage: ref(false),
    listFilter: ref('all'),
  })

  assert.deepEqual(state.hero.value, {
    title: '公告',
    description: 'tag hero',
  })
})
