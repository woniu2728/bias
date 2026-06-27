import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, resolve, relative } from 'node:path'
import { fileURLToPath } from 'node:url'
import { discoverExtensionSdkAliases } from '../../extensionSdkAliases.mjs'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const workspaceRoot = resolve(repoRoot, '..')
const extensionRoot = workspaceRoot
const extensionPackageRoots = discoverExtensionPackageRoots()
const allowedPublicPackageImports = new Set([
  '@bias/core/forum',
  '@bias/core/admin',
  '@bias/core/components/admin',
  '@bias/core',
  ...discoverExtensionSdkAliases().map(([alias]) => alias),
])

function listFrontendFiles(directory) {
  const output = []
  for (const entry of readdirSync(directory)) {
    const path = resolve(directory, entry)
    const stat = statSync(path)
    if (stat.isDirectory()) {
      output.push(...listFrontendFiles(path))
      continue
    }
    if (/\.(js|ts|vue)$/.test(entry)) {
      output.push(path)
    }
  }
  return output
}

function discoverExtensionPackageRoots() {
  return readdirSync(workspaceRoot, { withFileTypes: true })
    .filter(entry => entry.isDirectory() && /^bias-ext-/.test(entry.name))
    .map(entry => resolve(workspaceRoot, entry.name))
    .filter(path => existsSync(resolve(path, 'frontend')))
    .sort()
}

function listExtensionFrontendFiles() {
  return extensionPackageRoots.flatMap(root => listFrontendFiles(resolve(root, 'frontend')))
}

function hasExtension(extensionId) {
  return existsSync(resolve(extensionRoot, `bias-ext-${extensionId}`, 'frontend'))
}

function extractImports(source) {
  const imports = []
  const staticImportPattern = /import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]/g
  const dynamicImportPattern = /import\(\s*['"]([^'"]+)['"]\s*\)/g
  for (const pattern of [staticImportPattern, dynamicImportPattern]) {
    let match = pattern.exec(source)
    while (match) {
      imports.push(match[1])
      match = pattern.exec(source)
    }
  }
  return imports
}

function readExtensionForumSource(extensionId) {
  return readFileSync(resolve(extensionRoot, `bias-ext-${extensionId}/frontend/forum/index.js`), 'utf8')
}

function readExtensionForumFileSource(extensionId, file) {
  return readFileSync(resolve(extensionRoot, `bias-ext-${extensionId}/frontend/forum/${file}`), 'utf8')
}

function assertCoreRegistryDoesNotOwn(keys) {
  const forumRegistrySource = readFileSync(resolve(repoRoot, 'frontend/src/forum/registry.js'), 'utf8')
  for (const key of keys) {
    assert.equal(forumRegistrySource.includes(key), false, key)
  }
}

function assertCorePostTypesDoesNotOwn(keys) {
  const postTypesSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/postTypes.js'), 'utf8')
  for (const key of keys) {
    assert.equal(postTypesSource.includes(key), false, key)
  }
}

test('extension frontend imports only public app APIs', () => {
  const offenders = []
  for (const path of listExtensionFrontendFiles()) {
    const source = readFileSync(path, 'utf8')
    for (const importPath of extractImports(source)) {
      if (allowedPublicPackageImports.has(importPath)) {
        continue
      }
      if (importPath.startsWith('@bias/')) {
        offenders.push(`${relative(repoRoot, path)} imports unknown public SDK ${importPath}`)
      }
      if (importPath === 'vue' || importPath === 'vue-router') {
        offenders.push(`${relative(repoRoot, path)} imports ${importPath}`)
      }
      if (
        importPath.startsWith('@/')
        || importPath.includes('frontend/src/')
        || importPath.includes('../../../../frontend/src')
      ) {
        offenders.push(`${relative(repoRoot, path)} imports ${importPath}`)
      }
    }
  }

  assert.deepEqual(offenders, [])
})

test('forum runtime does not import extension source modules directly', () => {
  const forumRoot = resolve(repoRoot, 'frontend/src/forum')
  const offenders = []
  for (const path of listFrontendFiles(forumRoot)) {
    if (/\.test\.(js|ts)$/.test(path)) {
      continue
    }
    const source = readFileSync(path, 'utf8')
    for (const specifier of extractImports(source)) {
      if (specifier.includes('/extensions/') || specifier.startsWith('../../../extensions')) {
        offenders.push(`${relative(repoRoot, path)} imports ${specifier}`)
      }
    }
  }

  assert.deepEqual(offenders, [])
})

test('forum sdk does not expose core runtime facade', () => {
  const forumSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.js'), 'utf8')
  const forumNodeSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/nodeSdk.js'), 'utf8')
  const forumTypesSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.d.ts'), 'utf8')

  for (const source of [forumSdkSource, forumNodeSdkSource, forumTypesSource]) {
    assert.equal(source.includes("export * from '../common/sdk"), false)
    assert.equal(source.includes("export * from './runtimeSdk"), false)
    assert.equal(source.includes("export * from './vueRuntime"), false)
    assert.equal(source.includes("from './runtimeSdk"), false)
    assert.equal(source.includes("from './vueRuntime"), false)
    assert.equal(source.includes("from 'vue'"), false)
    assert.equal(source.includes("from 'vue-router'"), false)
    assert.equal(source.includes("from 'pinia'"), false)
    assert.equal(source.includes('function computed'), false)
    assert.equal(source.includes('function ref'), false)
    assert.equal(source.includes('function useRouter'), false)
    assert.equal(source.includes('function defineStore'), false)
    assert.equal(source.includes('forumApi'), false)
    assert.equal(source.includes('useModalStore'), false)
    assert.equal(source.includes('useResourceStore'), false)
  }
})

test('admin sdk does not expose core runtime facade', () => {
  const adminSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/admin/sdk.js'), 'utf8')
  const adminTypesSource = readFileSync(resolve(repoRoot, 'frontend/src/admin/sdk.d.ts'), 'utf8')

  assert.equal(adminSdkSource.includes("export * from '../common/sdk"), false)
  for (const source of [adminSdkSource, adminTypesSource]) {
    assert.equal(source.includes("from 'vue'"), false)
    assert.equal(source.includes("from 'vue-router'"), false)
    assert.equal(source.includes("from 'pinia'"), false)
    assert.equal(source.includes('function computed'), false)
    assert.equal(source.includes('function ref'), false)
    assert.equal(source.includes('function useRouter'), false)
  }
})

test('users auth APIs are owned by users sdk instead of forum or admin facades', () => {
  const usersSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-users/frontend/forum/sdk.js'), 'utf8')
  const forumSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.js'), 'utf8')
  const forumNodeSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/nodeSdk.js'), 'utf8')
  const forumTypesSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.d.ts'), 'utf8')
  const adminComponentsSource = readFileSync(resolve(repoRoot, 'frontend/src/admin/componentsSdk.js'), 'utf8')
  const adminComponentsTypesSource = readFileSync(resolve(repoRoot, 'frontend/src/admin/componentsSdk.d.ts'), 'utf8')

  for (const symbol of [
    'useAuthStore',
    'useOnlineUsersStore',
    'openLoginModal',
    'openRegisterModal',
    'openForgotPasswordModal',
    'getAuthModalProvider',
    'registerAuthModalProvider',
  ]) {
    assert.equal(usersSdkSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
    assert.equal(forumNodeSdkSource.includes(symbol), false, symbol)
    assert.equal(forumTypesSource.includes(symbol), false, symbol)
    assert.equal(adminComponentsSource.includes(symbol), false, symbol)
    assert.equal(adminComponentsTypesSource.includes(symbol), false, symbol)
  }
})

test('realtime APIs are owned by realtime sdk instead of forum facade', () => {
  const realtimeSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-realtime/frontend/forum/sdk.js'), 'utf8')
  const forumSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.js'), 'utf8')
  const forumNodeSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/nodeSdk.js'), 'utf8')
  const forumTypesSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.d.ts'), 'utf8')

  for (const symbol of [
    'useForumRealtimeStore',
    'getForumRealtimeEventPolicy',
    'getTrackedDiscussionIdsFromDiscussionItems',
    'mergeForumEventPayload',
    'shouldRefreshForumEvent',
  ]) {
    assert.equal(realtimeSdkSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
    assert.equal(forumNodeSdkSource.includes(symbol), false, symbol)
    assert.equal(forumTypesSource.includes(symbol), false, symbol)
  }
})

test('emoji rendering APIs are owned by emoji sdk instead of forum facade', () => {
  const emojiSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-emoji/frontend/forum/sdk.js'), 'utf8')
  const forumSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.js'), 'utf8')
  const forumNodeSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/nodeSdk.js'), 'utf8')
  const forumTypesSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.d.ts'), 'utf8')

  for (const symbol of [
    'renderTwemojiHtml',
    'renderTwemojiText',
    'setTwemojiBaseUrl',
    'setTwemojiEnabled',
  ]) {
    assert.equal(emojiSdkSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
    assert.equal(forumNodeSdkSource.includes(symbol), false, symbol)
    assert.equal(forumTypesSource.includes(symbol), false, symbol)
  }
})

test('extensions import core runtime primitives from core sdk', () => {
  const coreRuntimeNames = new Set([
    'computed',
    'nextTick',
    'onBeforeUnmount',
    'onMounted',
    'reactive',
    'ref',
    'toRef',
    'watch',
    'useRoute',
    'useRouter',
    'createPinia',
    'defineStore',
    'setActivePinia',
    'forumApi',
    'useModalStore',
    'useResourceStore',
  ])
  const offenders = []
  const importPattern = /import\s*\{([^{}]*)\}\s*from\s*['"]@bias\/core\/forum['"];?/g

  for (const path of listFrontendFiles(extensionRoot)) {
    const source = readFileSync(path, 'utf8')
    let match = importPattern.exec(source)
    while (match) {
      for (const specifier of match[1].split(',').map(item => item.trim()).filter(Boolean)) {
        const importedName = specifier.match(/^([^\s]+)\s+as\s+[^\s]+$/)?.[1] || specifier
        if (coreRuntimeNames.has(importedName)) {
          offenders.push(`${relative(repoRoot, path)} imports ${specifier} from @bias/core/forum`)
        }
      }
      match = importPattern.exec(source)
    }
  }

  assert.deepEqual(offenders, [])
})

test('extensions import discussion and post runtime APIs from owning extension sdks', () => {
  const forumOwnedRuntimeNames = new Set([
    'getDiscussionBadges',
    'getDiscussionListContexts',
    'getDiscussionListHero',
    'getDiscussionListRequests',
    'getDiscussionMenuItems',
    'getDiscussionPresentationItems',
    'getDiscussionReplyState',
    'getDiscussionReviewBanner',
    'getDiscussionStateBadges',
    'getPostFlagPanel',
    'getPostMenuItems',
    'getPostReviewBanner',
    'getPostStateBadges',
    'getPostTypeDefinition',
    'registerDiscussionAction',
    'registerDiscussionActionHandler',
    'registerDiscussionListContext',
    'registerDiscussionListHero',
    'registerDiscussionListRequest',
    'registerDiscussionPresentation',
    'registerDiscussionReplyState',
    'registerDiscussionReviewBanner',
    'registerPostAction',
    'registerPostActionHandler',
    'registerPostFlagPanel',
    'registerPostReviewBanner',
    'registerPostStateBadge',
    'runDiscussionAction',
    'runPostAction',
  ])
  const offenders = []
  const importPattern = /import\s*\{([^{}]*)\}\s*from\s*['"]@bias\/core\/forum['"];?/g

  for (const path of listFrontendFiles(extensionRoot)) {
    const source = readFileSync(path, 'utf8')
    let match = importPattern.exec(source)
    while (match) {
      for (const specifier of match[1].split(',').map(item => item.trim()).filter(Boolean)) {
        const importedName = specifier.match(/^([^\s]+)\s+as\s+[^\s]+$/)?.[1] || specifier
        if (forumOwnedRuntimeNames.has(importedName)) {
          offenders.push(`${relative(repoRoot, path)} imports ${specifier} from @bias/core/forum`)
        }
      }
      match = importPattern.exec(source)
    }
  }

  assert.deepEqual(offenders, [])
})

test('forum public sdk does not export discussion and post runtime APIs', () => {
  const forbiddenNames = [
    'getDiscussionBadges',
    'getDiscussionListContexts',
    'getDiscussionListHero',
    'getDiscussionListRequests',
    'getDiscussionMenuItems',
    'getDiscussionPresentationItems',
    'getDiscussionReplyState',
    'getDiscussionReviewBanner',
    'getDiscussionStateBadges',
    'getPostFlagPanel',
    'getPostMenuItems',
    'getPostReviewBanner',
    'getPostStateBadges',
    'getPostTypeDefinition',
    'registerDiscussionAction',
    'registerDiscussionActionHandler',
    'registerDiscussionListContext',
    'registerDiscussionListHero',
    'registerDiscussionListRequest',
    'registerDiscussionPresentation',
    'registerDiscussionReplyState',
    'registerDiscussionReviewBanner',
    'registerPostAction',
    'registerPostActionHandler',
    'registerPostFlagPanel',
    'registerPostReviewBanner',
    'registerPostStateBadge',
    'runDiscussionAction',
    'runPostAction',
  ]
  const sources = [
    readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.js'), 'utf8'),
    readFileSync(resolve(repoRoot, 'frontend/src/forum/nodeSdk.js'), 'utf8'),
  ]

  const offenders = []
  for (const source of sources) {
    for (const name of forbiddenNames) {
      if (new RegExp(`\\b${name}\\b`).test(source)) {
        offenders.push(name)
      }
    }
  }

  assert.deepEqual(offenders, [])
})

test('discussion and post sdks own their runtime exports', () => {
  const sources = [
    readFileSync(resolve(extensionRoot, 'bias-ext-discussions/frontend/forum/sdk.js'), 'utf8'),
    readFileSync(resolve(extensionRoot, 'bias-ext-discussions/frontend/forum/nodeSdk.js'), 'utf8'),
    readFileSync(resolve(extensionRoot, 'bias-ext-posts/frontend/forum/sdk.js'), 'utf8'),
    readFileSync(resolve(extensionRoot, 'bias-ext-posts/frontend/forum/sdk.js'), 'utf8'),
    // posts 已合并 — nodeSdk.js 已删除，sdk.js 同时用作浏览器和 Node 入口
  ]

  assert.deepEqual(
    sources
      .map(source => source.includes('@bias/core/forum'))
      .filter(Boolean),
    []
  )
})

test('feature runtime APIs are owned by their extension sdks instead of forum', () => {
  const forumRuntimeNames = new Set([
    'getNotificationRenderers',
    'registerNotificationRenderer',
    'getSearchSources',
    'getSearchModalProvider',
    'getSearchModalSections',
    'registerSearchSource',
    'registerSearchModalProvider',
    'registerSearchModalSection',
    'getProfilePanels',
    'getUserBadges',
    'getAuthModalProvider',
    'registerProfilePanel',
    'registerUserBadge',
    'registerAuthModalProvider',
    'getForumRealtimeEvents',
    'registerForumRealtimeEvent',
    'getStartDiscussionProvider',
    'registerStartDiscussionProvider',
    'useStartDiscussionAction',
    'formatRelativeTime',
    'formatMonth',
    'unwrapList',
  ])
  const offenders = []
  const importPattern = /import\s*\{([^{}]*)\}\s*from\s*['"]@bias\/core\/forum['"];?/g

  for (const path of listFrontendFiles(extensionRoot)) {
    const source = readFileSync(path, 'utf8')
    let match = importPattern.exec(source)
    while (match) {
      for (const specifier of match[1].split(',').map(item => item.trim()).filter(Boolean)) {
        const importedName = specifier.match(/^([^\s]+)\s+as\s+[^\s]+$/)?.[1] || specifier
        if (forumRuntimeNames.has(importedName)) {
          offenders.push(`${relative(repoRoot, path)} imports ${specifier} from @bias/core/forum`)
        }
      }
      match = importPattern.exec(source)
    }
  }

  assert.deepEqual(offenders, [])
})

test('forum public sdk does not export feature-owned runtime APIs', () => {
  const forbiddenNames = [
    'getNotificationRenderers',
    'registerNotificationRenderer',
    'getSearchSources',
    'getSearchModalProvider',
    'getSearchModalSections',
    'registerSearchSource',
    'registerSearchModalProvider',
    'registerSearchModalSection',
    'getProfilePanels',
    'getUserBadges',
    'registerProfilePanel',
    'registerUserBadge',
    'getForumRealtimeEvents',
    'registerForumRealtimeEvent',
    'getStartDiscussionProvider',
    'registerStartDiscussionProvider',
    'useStartDiscussionAction',
    'formatRelativeTime',
    'formatMonth',
    'unwrapList',
    'usePaginatedListState',
    'useRequestedPaginatedListState',
    'useRouteListState',
    'useRoutePagination',
  ]
  const sources = [
    readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.js'), 'utf8'),
    readFileSync(resolve(repoRoot, 'frontend/src/forum/nodeSdk.js'), 'utf8'),
    readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.d.ts'), 'utf8'),
  ]

  const offenders = []
  for (const source of sources) {
    for (const name of forbiddenNames) {
      if (new RegExp(`\\b${name}\\b`).test(source)) {
        offenders.push(name)
      }
    }
  }

  assert.deepEqual(offenders, [])
})

test('feature sdks expose their owned runtime APIs', () => {
  const notificationsSdk = readFileSync(resolve(extensionRoot, 'bias-ext-notifications/frontend/forum/sdk.js'), 'utf8')
  const searchSdk = readFileSync(resolve(extensionRoot, 'bias-ext-search/frontend/forum/sdk.js'), 'utf8')
  const usersSdk = readFileSync(resolve(extensionRoot, 'bias-ext-users/frontend/forum/sdk.js'), 'utf8')
  const realtimeSdk = readFileSync(resolve(extensionRoot, 'bias-ext-realtime/frontend/forum/sdk.js'), 'utf8')
  const discussionsSdk = readFileSync(resolve(extensionRoot, 'bias-ext-discussions/frontend/forum/sdk.js'), 'utf8')

  for (const symbol of ['getNotificationRenderers', 'registerNotificationRenderer']) {
    assert.equal(notificationsSdk.includes(symbol), true, symbol)
  }
  for (const symbol of ['getSearchSources', 'getSearchModalProvider', 'registerSearchSource']) {
    assert.equal(searchSdk.includes(symbol), true, symbol)
  }
  for (const symbol of ['getProfilePanels', 'getUserBadges', 'getAuthModalProvider', 'registerProfilePanel', 'registerAuthModalProvider']) {
    assert.equal(usersSdk.includes(symbol), true, symbol)
  }
  for (const symbol of ['getForumRealtimeEvents', 'registerForumRealtimeEvent']) {
    assert.equal(realtimeSdk.includes(symbol), true, symbol)
  }
  for (const symbol of ['getStartDiscussionProvider', 'registerStartDiscussionProvider', 'useStartDiscussionAction']) {
    assert.equal(discussionsSdk.includes(symbol), true, symbol)
  }
})

test('ai and points expose reusable runtime APIs through their owning sdks', () => {
  if (!hasExtension('ai')) {
    return
  }
  const forumSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.js'), 'utf8')
  const aiSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-ai/frontend/forum/sdk.js'), 'utf8')
  const aiRuntimeSource = readFileSync(resolve(extensionRoot, 'bias-ext-ai/frontend/forum/aiRuntime.js'), 'utf8')
  const aiPanelSource = readExtensionForumFileSource('ai', 'AiAssistantPanel.vue')
  const pointsSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-points/frontend/forum/sdk.js'), 'utf8')
  const pointsRuntimeSource = readFileSync(resolve(extensionRoot, 'bias-ext-points/frontend/forum/pointsRuntime.js'), 'utf8')
  const pointsForumSource = readExtensionForumSource('points')

  for (const symbol of [
    'formatAiResultMarkdown',
    'getAiResultTitle',
    'getAiModeLabel',
    'getAiPointsCost',
    'wasAiPointsCharged',
  ]) {
    assert.equal(aiSdkSource.includes(symbol), true, symbol)
    assert.equal(aiRuntimeSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
  }
  assert.equal(aiPanelSource.includes('formatResultMarkdown'), false)
  assert.equal(aiPanelSource.includes('formatAiResultMarkdown'), true)

  for (const symbol of [
    'buildUserPointsPath',
    'formatPointsBalance',
    'formatPointsLabel',
    'getUserPointsBalance',
    'normalizePointsLedgerEntry',
  ]) {
    assert.equal(pointsSdkSource.includes(symbol), true, symbol)
    assert.equal(pointsRuntimeSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
  }
  assert.equal(pointsForumSource.includes("from './pointsRuntime.js'"), true)
})

test('other extension sdks expose their owned runtime APIs through their owning sdks', () => {
  const forumSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.js'), 'utf8')
  const approvalSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-approval/frontend/forum/sdk.js'), 'utf8')
  const flagsSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-flags/frontend/forum/sdk.js'), 'utf8')
  const flagsNodeSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-flags/frontend/forum/nodeSdk.js'), 'utf8')
  const likesSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-likes/frontend/forum/sdk.js'), 'utf8')
  const mentionsSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-mentions/frontend/forum/sdk.js'), 'utf8')
  const uploadsSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-uploads/frontend/forum/sdk.js'), 'utf8')
  const securitySdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-security/frontend/forum/sdk.js'), 'utf8')
  const subscriptionsSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-subscriptions/frontend/forum/sdk.js'), 'utf8')
  const tagsSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-tags/frontend/forum/sdk.js'), 'utf8')
  const tagsNodeSdkSource = readFileSync(resolve(extensionRoot, 'bias-ext-tags/frontend/forum/nodeSdk.js'), 'utf8')

  for (const symbol of ['getApprovalComposerState']) {
    assert.equal(approvalSdkSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
  }

  for (const symbol of [
    'buildPostFlagPanel',
    'canModeratePostFlags',
    'getPostOpenFlagCount',
    'hasViewerOpenFlag',
    'normalizePostFlag',
  ]) {
    assert.equal(flagsSdkSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
  }
  assert.equal(flagsNodeSdkSource.includes('PostReportModal = null'), true)

  for (const symbol of ['buildLikeSummary', 'canLikePost', 'getPostLikeCount', 'isPostLiked']) {
    assert.equal(likesSdkSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
  }

  for (const symbol of ['buildMentionReplacement', 'buildMentionTrigger', 'detectMentionQuery']) {
    assert.equal(mentionsSdkSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
  }

  for (const symbol of ['buildUploadedFileMarkdown', 'sanitizeMarkdownLabel', 'stripFileExtension']) {
    assert.equal(uploadsSdkSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
  }

  for (const symbol of ['buildHumanVerificationPayload', 'shouldUseTurnstile']) {
    assert.equal(securitySdkSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
  }

  for (const symbol of ['getSubscriptionActionDescription', 'getSubscriptionActionLabel', 'isDiscussionSubscribed', 'shouldFollowAfterReply']) {
    assert.equal(subscriptionsSdkSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
  }

  for (const symbol of ['buildTagPath', 'flattenTags', 'normalizeTag', 'unwrapTagList']) {
    assert.equal(tagsSdkSource.includes(symbol), true, symbol)
    assert.equal(forumSdkSource.includes(symbol), false, symbol)
  }
  assert.equal(tagsNodeSdkSource.includes('TagModel = null'), true)
})

test('mentions extension owns composer autocomplete provider and toolbar tool registration', () => {
  const composerSource = readFileSync(resolve(repoRoot, 'frontend/src/utils/composer.js'), 'utf8')
  const runtimeSource = readFileSync(resolve(repoRoot, 'frontend/src/composables/useComposerRuntime.js'), 'utf8')
  const mentionsForumSource = readExtensionForumSource('mentions')

  assertCoreRegistryDoesNotOwn([
    "key: 'default-users'",
    'composer-mention-loading',
    'composer-mention-empty',
    'composer-mention-picker-label',
  ])
  assert.equal(composerSource.includes("key: 'mention'"), false)
  assert.equal(runtimeSource.includes('runComposerMentionProviders'), false)
  assert.equal(runtimeSource.includes('detectMentionQuery'), false)
  assert.equal(mentionsForumSource.includes('extendForum(registerMentionsForum)'), true)
  assert.equal(mentionsForumSource.includes('forum.composerMentionProvider'), false)
  assert.equal(mentionsForumSource.includes('forum.composerAutocompleteProvider'), true)
  assert.equal(mentionsForumSource.includes('detectMentionQuery'), true)
  assert.equal(mentionsForumSource.includes('buildMentionReplacement'), true)
  assert.equal(mentionsForumSource.includes('buildMentionTrigger'), true)
  assert.equal(mentionsForumSource.includes('forum.composerTool'), true)
  assert.equal(mentionsForumSource.includes('forum.stateBlock'), true)
  assert.equal(mentionsForumSource.includes('forum.uiCopy'), true)
  assert.equal(mentionsForumSource.includes("key: 'mention'"), true)
  assert.equal(mentionsForumSource.includes("moduleId: 'mentions'"), true)
})

test('emoji extension owns composer emoji tool and picker copy registration', () => {
  const runtimeSource = readFileSync(resolve(repoRoot, 'frontend/src/composables/useComposerRuntime.js'), 'utf8')
  const emojiForumSource = readExtensionForumSource('emoji')

  assertCoreRegistryDoesNotOwn([
    "key: 'emoji'",
    'composer-emoji-picker-empty',
    'composer-emoji-picker-dialog-label',
    'composer-emoji-picker-search-placeholder',
    'composer-emoji-picker-summary',
    'composer-emoji-autocomplete-label',
  ])
  assert.equal(runtimeSource.includes('detectEmojiQuery'), false)
  assert.equal(runtimeSource.includes('searchEmojiItems'), false)
  assert.equal(emojiForumSource.includes('extendForum(registerEmojiForum)'), true)
  assert.equal(emojiForumSource.includes('forum.composerAutocompleteProvider'), true)
  assert.equal(emojiForumSource.includes('detectEmojiQuery'), true)
  assert.equal(emojiForumSource.includes('searchEmojiItems'), true)
  assert.equal(emojiForumSource.includes('buildEmojiReplacement'), true)
  assert.equal(emojiForumSource.includes('forum.composerTool'), true)
  assert.equal(emojiForumSource.includes('forum.uiCopy'), true)
  assert.equal(emojiForumSource.includes("key: 'emoji'"), true)
  assert.equal(emojiForumSource.includes("moduleId: 'emoji'"), true)
})

test('uploads extension owns composer upload and image tool registration', () => {
  const composerSource = readFileSync(resolve(repoRoot, 'frontend/src/utils/composer.js'), 'utf8')
  const uploadsForumSource = readExtensionForumSource('uploads')

  assert.equal(composerSource.includes("key: 'upload'"), false)
  assert.equal(composerSource.includes("key: 'image'"), false)
  assert.equal(composerSource.includes('uploadComposerFile'), false)
  assert.equal(composerSource.includes('/uploads'), false)
  assert.equal(uploadsForumSource.includes('extendForum('), true)
  assert.equal(uploadsForumSource.includes('.composerTool'), true)
  assert.equal(uploadsForumSource.includes('.composerUploadHandler'), true)
  assert.equal(uploadsForumSource.includes("key: 'upload'"), true)
  assert.equal(uploadsForumSource.includes("key: 'image'"), true)
  assert.equal(uploadsForumSource.includes("moduleId: 'uploads'"), true)
  assert.equal(uploadsForumSource.includes('openAttachmentPicker'), true)
  assert.equal(uploadsForumSource.includes('openImagePicker'), true)
})

test('tags and notifications extensions own navigational forum contributions', () => {
  const tagsForumSource = readExtensionForumSource('tags')
  const notificationsForumSource = readExtensionForumSource('notifications')
  const forumSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.js'), 'utf8')

  assertCoreRegistryDoesNotOwn([
    "key: 'tags'",
    'tags-page-empty',
    'tags-page-hero-title',
    'discussion-list-tag-empty',
    'discussion-primary-tag',
    'discussion-selected-tag',
    "key: 'notifications'",
    'notifications-page-empty',
    'notifications-menu-empty',
  ])
  assert.equal(tagsForumSource.includes('extendForum(registerTagsForum)'), true)
  assert.equal(/import\s*\{[\s\S]*ResourceNormalizer[\s\S]*Store[\s\S]*\}\s*from\s*['"]@bias\/core['"]/.test(tagsForumSource), true)
  assert.equal(tagsForumSource.includes('new Store()'), true)
  assert.equal(tagsForumSource.includes(".add('tags', TagModel)"), true)
  assert.equal(tagsForumSource.includes('new ResourceNormalizer()'), true)
  assert.equal(tagsForumSource.includes('registerResourceNormalizer'), false)
  assert.equal(tagsForumSource.includes('forum.postType'), true)
  assert.equal(tagsForumSource.includes("postType('discussionTagged'"), true)
  assert.equal(tagsForumSource.includes('forum.navItem'), true)
  assert.equal(tagsForumSource.includes('forum.emptyState'), true)
  assert.equal(tagsForumSource.includes('forum.composerSubmitGuard'), true)
  assert.equal(tagsForumSource.includes("moduleId: 'tags'"), true)
  assert.equal(notificationsForumSource.includes('extendForum(registerNotificationsForum)'), true)
  assert.equal(/import\s*\{[\s\S]*ResourceNormalizer[\s\S]*\}\s*from\s*['"]@bias\/core['"]/.test(notificationsForumSource), true)
  assert.equal(notificationsForumSource.includes('new ResourceNormalizer()'), true)
  assert.equal(notificationsForumSource.includes('registerResourceNormalizer'), false)
  assert.equal(notificationsForumSource.includes('forum.navItem'), true)
  assert.equal(notificationsForumSource.includes('forum.headerItem'), true)
  assert.equal(notificationsForumSource.includes('forum.notificationRenderer'), true)
  assert.equal(notificationsForumSource.includes("moduleId: 'notifications'"), true)
  assert.equal(forumSdkSource.includes('registerResourceNormalizer'), false)
})

test('forum registry state is shared with the packaged core sdk', () => {
  const frontendRegistrySource = readFileSync(resolve(repoRoot, 'frontend/src/forum/frontendRegistry.js'), 'utf8')
  const registrySlotsSource = readFileSync(resolve(repoRoot, 'frontend/src/common/frontendRegistrySlots.js'), 'utf8')

  assert.equal(frontendRegistrySource.includes("getFrontendRegistrySlot('forum.navItems')"), true)
  assert.equal(frontendRegistrySource.includes("getFrontendRegistrySlot('forum.sidebarSections')"), true)
  assert.equal(frontendRegistrySource.includes('const forumNavItems = []'), false)
  assert.equal(frontendRegistrySource.includes('const forumSidebarSections = []'), false)
  assert.equal(registrySlotsSource.includes('__biasFrontendRegistrySlots'), true)
})

test('core resource modules declare normalizers through ResourceNormalizer extender', () => {
  for (const extensionId of ['users', 'posts', 'discussions']) {
    const source = readExtensionForumSource(extensionId)
    assert.equal(/import\s*\{[\s\S]*ResourceNormalizer[\s\S]*\}\s*from\s*['"]@bias\/core['"]/.test(source), true, extensionId)
    assert.equal(source.includes('new ResourceNormalizer()'), true, extensionId)
    assert.equal(source.includes('registerResourceNormalizer'), false, extensionId)
  }
})

test('search extension owns default forum search sources', () => {
  const searchForumSource = readExtensionForumSource('search')
  const searchViewSource = readExtensionForumFileSource('search', 'SearchResultsView.vue')
  const forumSdkSource = readFileSync(resolve(repoRoot, 'frontend/src/forum/sdk.js'), 'utf8')

  assertCoreRegistryDoesNotOwn([
    "type: 'discussions'",
    "type: 'posts'",
    "type: 'users'",
    "filterTarget: 'discussion'",
    "filterTarget: 'post'",
  ])
  assert.equal(searchForumSource.includes('extendForum(registerSearchForum)'), true)
  assert.equal(searchForumSource.includes('forum.searchSource'), true)
  assert.equal(searchForumSource.includes("key: 'discussions'"), true)
  assert.equal(searchForumSource.includes("key: 'posts'"), true)
  assert.equal(searchForumSource.includes("key: 'users'"), true)
  assert.equal(searchForumSource.includes("moduleId: 'search'"), true)
  assert.equal(searchForumSource.includes('useSearchFilterCatalog'), false)
  assert.equal(forumSdkSource.includes('useSearchResultsViewModel'), false)
  assert.equal(forumSdkSource.includes('useSearchFilterCatalog'), false)
  assert.equal(searchViewSource.includes("import { useSearchResultsViewModel } from './useSearchResultsViewModel'"), true)
})

test('approval flags subscriptions and likes own interaction contributions', () => {
  const approvalForumSource = readExtensionForumSource('approval')
  const approvalComposerSource = readExtensionForumFileSource('approval', 'approvalComposer.js')
  const approvalModerationSource = readExtensionForumFileSource('approval', 'approvalModerationActions.js')
  const flagsForumSource = readExtensionForumSource('flags')
  const subscriptionsForumSource = readExtensionForumSource('subscriptions')
  const likesForumSource = readExtensionForumSource('likes')

  assertCoreRegistryDoesNotOwn([
    'discussionApproved',
    'discussionRejected',
    'discussionResubmitted',
    'postApproved',
    'postRejected',
    'postResubmitted',
    'discussion-event-note-prefix',
    'discussion-event-approved-label',
    'discussion-event-rejected-label',
    'discussion-event-resubmitted-label',
    'post-event-approved-label',
    'post-event-rejected-label',
    'post-event-resubmitted-label',
    'discussion-detail-moderation-title',
    'discussion-detail-moderation-description',
    'discussion-detail-moderation-confirm',
    'discussion-detail-moderation-placeholder',
    'discussion-detail-moderation-success-title',
    'discussion-detail-moderation-success-message',
    'open-report-modal',
    'toggle-subscription',
    'postLiked',
    'discussion-detail-like-summary',
    'discussion-post-like-action',
    'discussion-composer-edit-pending-title',
    'discussion-composer-create-pending-title',
    'post-composer-edit-pending-title',
    'post-composer-create-pending-title',
  ])
  assertCorePostTypesDoesNotOwn([
    'discussionApproved',
    'discussionRejected',
    'discussionResubmitted',
    'postApproved',
    'postRejected',
    'postResubmitted',
  ])
  assert.equal(approvalForumSource.includes('extendForum(registerApprovalForum)'), true)
  assert.equal(approvalForumSource.includes('forum.postType'), true)
  assert.equal(approvalForumSource.includes("type: 'discussionApproved'"), true)
  assert.equal(approvalForumSource.includes("type: 'postResubmitted'"), true)
  assert.equal(approvalForumSource.includes('forum.feedbackNote'), true)
  assert.equal(approvalForumSource.includes('forum.realtimeEvent'), true)
  assert.equal(approvalComposerSource.includes('forum.composerSubmitSuccess'), true)
  assert.equal(approvalComposerSource.includes('forum.composerInitialState'), true)
  assert.equal(approvalComposerSource.includes('forum.uiCopy'), true)
  assert.equal(approvalModerationSource.includes('forum.discussionActionHandler'), true)
  assert.equal(approvalModerationSource.includes('forum.postActionHandler'), true)
  assert.equal(approvalModerationSource.includes('forum.uiCopy'), true)
  assert.equal(approvalModerationSource.includes("moduleId: 'approval'"), true)
  assert.equal(approvalForumSource.includes('forum.discussionReviewBanner'), true)
  assert.equal(approvalForumSource.includes("moduleId: 'approval'"), true)
  assert.equal(flagsForumSource.includes('extendForum(registerFlagsForum)'), true)
  assert.equal(flagsForumSource.includes('forum.postActionHandler'), true)
  assert.equal(flagsForumSource.includes('forum.postFlagPanel'), true)
  assert.equal(flagsForumSource.includes("moduleId: 'flags'"), true)
  assert.equal(subscriptionsForumSource.includes('extendForum(registerSubscriptionsForum)'), true)
  assert.equal(subscriptionsForumSource.includes('forum.discussionActionHandler'), true)
  assert.equal(subscriptionsForumSource.includes('forum.stateBlock'), true)
  assert.equal(subscriptionsForumSource.includes('forum.runtime'), true)
  assert.equal(subscriptionsForumSource.includes('forum.notificationRenderer'), true)
  assert.equal(subscriptionsForumSource.includes("moduleId: 'subscriptions'"), true)
  assert.equal(likesForumSource.includes('extendForum(registerLikesForum)'), true)
  assert.equal(likesForumSource.includes('forum.postAction'), true)
  assert.equal(likesForumSource.includes('forum.postActionHandler'), true)
  assert.equal(likesForumSource.includes('forum.uiCopy'), true)
  assert.equal(likesForumSource.includes("key: 'toggle-post-like-primary'"), true)
  assert.equal(likesForumSource.includes("key: 'post-like-feedback'"), true)
  assert.equal(likesForumSource.includes("key: 'toggle-post-like'"), true)
  assert.equal(likesForumSource.includes('forum.notificationRenderer'), true)
  assert.equal(likesForumSource.includes("moduleId: 'likes'"), true)
})

test('extension frontend contributions do not claim core module ownership', () => {
  const offenders = []
  for (const path of listExtensionFrontendFiles()) {
    const source = readFileSync(path, 'utf8')
    if (/\bmoduleId\s*:\s*['"]core['"]/.test(source)) {
      offenders.push(relative(repoRoot, path))
    }
  }

  assert.deepEqual(offenders, [])
})
