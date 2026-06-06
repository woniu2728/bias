import test from 'node:test'
import assert from 'node:assert/strict'
import {
  getDiscussionListFilterHeroDescriptionText,
  getDiscussionListFilterHeroTitleText,
  getDiscussionListFilterLabelText,
  resolveDiscussionListActiveFilterCode,
  resolveDiscussionListPageMetaDescription,
  resolveDiscussionListPageMetaTitle,
} from './discussionList.js'

test('discussion list helper resolves active filter code with following priority', () => {
  assert.equal(resolveDiscussionListActiveFilterCode({
    isFollowingPage: true,
    listFilter: 'my',
  }), 'following')
  assert.equal(resolveDiscussionListActiveFilterCode({
    isFollowingPage: false,
    listFilter: 'unread',
  }), 'unread')
})

test('discussion list helper resolves filter labels and hero copy', () => {
  assert.equal(getDiscussionListFilterLabelText('my'), '我的讨论')
  assert.equal(getDiscussionListFilterHeroTitleText('unread'), '未读讨论')
  assert.equal(
    getDiscussionListFilterHeroDescriptionText('following'),
    '这里会显示你已关注、并在后续收到新回复通知的讨论。'
  )
})

test('discussion list helper resolves page meta with search and context subject', () => {
  assert.equal(resolveDiscussionListPageMetaTitle({
    filterCode: 'all',
    subjectName: '公告',
    searchQuery: '维护',
  }), '公告 - 搜索“维护”')

  assert.equal(resolveDiscussionListPageMetaDescription({
    filterCode: 'all',
    subjectName: '公告',
    subjectDescription: '站点公告',
    searchQuery: '维护',
  }), '查看“公告”范围内与“维护”相关的讨论。')

  assert.equal(resolveDiscussionListPageMetaDescription({
    filterCode: 'unread',
    subjectName: '',
    subjectDescription: '',
    searchQuery: '修复',
  }), '在未读中搜索与“修复”相关的讨论。')

  assert.equal(resolveDiscussionListPageMetaTitle({
    filterCode: 'following',
    subjectName: '',
    searchQuery: '',
  }), '关注的讨论')

  assert.equal(resolveDiscussionListPageMetaDescription({
    filterCode: 'following',
    subjectName: '',
    subjectDescription: '',
    searchQuery: '',
  }), '查看你关注的讨论和最新回复。')
})
