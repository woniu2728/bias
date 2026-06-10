import { ref } from '@bias/core'
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDiscussionCreateViewBindings } from './useDiscussionCreateViewBindings.js'

test('discussion create view bindings expose redirect card copy', () => {
  const bindings = createDiscussionCreateViewBindings({
    descriptionText: ref('系统会自动切换到浮层编辑器。'),
    titleText: ref('正在打开讨论编辑器...'),
  })

  assert.deepEqual(bindings.cardBindings.value, {
    title: '正在打开讨论编辑器...',
    description: '系统会自动切换到浮层编辑器。',
  })
})
