import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildDiscussionFilterLocation,
  getDiscussionListContrastColor,
  getDiscussionListStartButtonStyle,
  isDiscussionFilterActive,
} from './discussionListNavigation.js'

test('discussion list navigation builds filter locations from route metadata', () => {
  assert.equal(buildDiscussionFilterLocation({ code: 'following', route_path: '/following' }), '/following')
  assert.deepEqual(buildDiscussionFilterLocation({ code: 'unread' }), {
    path: '/',
    query: {
      filter: 'unread',
    },
  })
})

test('discussion list navigation resolves active filter state', () => {
  assert.equal(isDiscussionFilterActive({
    contextSubjectKey: '',
    routeName: 'following',
    isFollowingPage: true,
    listFilter: 'all',
    filterCode: 'following',
  }), true)

  assert.equal(isDiscussionFilterActive({
    contextSubjectKey: 'announcements',
    routeName: 'home',
    isFollowingPage: false,
    listFilter: 'all',
    filterCode: 'all',
  }), false)
})

test('discussion list navigation derives start button style', () => {
  assert.equal(getDiscussionListContrastColor('#ffffff'), '#243447')
  assert.deepEqual(getDiscussionListStartButtonStyle({ color: '#112233' }), {
    '--tag-button-bg': '#112233',
    '--tag-button-text': '#ffffff',
  })
})
