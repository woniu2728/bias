import test from 'node:test'
import assert from 'node:assert/strict'
import { formatDiscussionTypingNotice } from './discussionTypingState.js'

test('discussion typing notice formats single user', () => {
  assert.equal(formatDiscussionTypingNotice(['alice']), 'alice 正在输入...')
})

test('discussion typing notice formats two users', () => {
  assert.equal(formatDiscussionTypingNotice(['alice', 'bob']), 'alice、bob 正在输入...')
})

test('discussion typing notice formats multi-user summary', () => {
  assert.equal(formatDiscussionTypingNotice(['alice', 'bob', 'carol']), 'alice 等 3 人正在输入...')
})

test('discussion typing notice ignores empty usernames', () => {
  assert.equal(formatDiscussionTypingNotice(['', ' alice ', null]), 'alice 正在输入...')
})
