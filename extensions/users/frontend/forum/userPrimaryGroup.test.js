import test from 'node:test'
import assert from 'node:assert/strict'
import {
  getUserPrimaryGroup,
  getUserPrimaryGroupColor,
  getUserPrimaryGroupIcon,
  getUserPrimaryGroupLabel,
} from './userPrimaryGroup.js'

test('user primary group helpers resolve group display fields', () => {
  const user = {
    primary_group: {
      icon: 'fas fa-shield',
      color: '#123456',
      name: '管理员',
    },
  }

  assert.deepEqual(getUserPrimaryGroup(user), user.primary_group)
  assert.equal(getUserPrimaryGroupIcon(user), 'fas fa-shield')
  assert.equal(getUserPrimaryGroupColor(user, '#000000'), '#123456')
  assert.equal(getUserPrimaryGroupLabel(user), '管理员')
})

test('user primary group helpers fall back when group is absent', () => {
  assert.equal(getUserPrimaryGroupIcon({}), '')
  assert.equal(getUserPrimaryGroupColor({}, '#4d698e'), '#4d698e')
  assert.equal(getUserPrimaryGroupLabel({}), '')
})
