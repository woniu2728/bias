import test from 'node:test'
import assert from 'node:assert/strict'
import {
  createJsconfigSdkPaths,
  createNodeSdkAliasMap,
  discoverExtensionSdkAliases,
} from '../../extensionSdkAliases.mjs'

const sdkExtensions = {
  emoji: true,
  realtime: true,
  users: false,
}

test('public extension SDK aliases are discovered from generated site extension sources', () => {
  const browserAliases = new Map(discoverExtensionSdkAliases())
  const nodeAliases = createNodeSdkAliasMap()
  const jsconfigPaths = createJsconfigSdkPaths()

  for (const [extensionId, hasNodeSdk] of Object.entries(sdkExtensions)) {
    const alias = `@bias/${extensionId}`
    assert.match(browserAliases.get(alias), new RegExp(`extensions[/\\\\]${extensionId}[/\\\\]frontend[/\\\\]forum[/\\\\]sdk\\.js$`))
    if (hasNodeSdk) {
      assert.match(nodeAliases.get(alias), new RegExp(`extensions[/\\\\]${extensionId}[/\\\\]frontend[/\\\\]forum[/\\\\]nodeSdk\\.js$`))
    } else {
      assert.match(nodeAliases.get(alias), new RegExp(`extensions[/\\\\]${extensionId}[/\\\\]frontend[/\\\\]forum[/\\\\]sdk\\.js$`))
    }
    assert.deepEqual(jsconfigPaths[alias], [`../extensions/${extensionId}/frontend/forum/sdk.js`])
  }

  assert.equal(browserAliases.has('@bias/core'), false)
  assert.match(browserAliases.get('@bias/approval'), /extensions[/\\]approval[/\\]frontend[/\\]forum[/\\]sdk\.js$/)
})

test('node test runtime resolves public Bias SDK package aliases', async () => {
  const forum = await import('@bias/core/forum')
  const admin = await import('@bias/core/admin')
  const adminComponents = await import('@bias/core/components/admin')
  const core = await import('@bias/core')
  const emoji = await import('@bias/emoji')
  const realtime = await import('@bias/realtime')
  const users = await import('@bias/users')

  assert.equal(typeof forum.extendForum, 'function')
  assert.equal(typeof forum.ForumExtender, 'function')
  assert.equal(forum.ModerationActionModal, null)
  assert.equal(forum.PostTypes, undefined)
  assert.equal(forum.Store, undefined)
  assert.equal(forum.ref, undefined)
  assert.equal(forum.useAuthStore, undefined)
  assert.equal(forum.useOnlineUsersStore, undefined)
  assert.equal(forum.openLoginModal, undefined)
  assert.equal(forum.useForumRealtimeStore, undefined)
  assert.equal(forum.shouldRefreshForumEvent, undefined)
  assert.equal(forum.forumApi, undefined)
  assert.equal(forum.useResourceStore, undefined)
  assert.equal(forum.useModalStore, undefined)
  assert.equal(typeof admin.extendAdmin, 'function')
  assert.equal(typeof admin.AdminExtender, 'function')
  assert.equal(admin.createAdminExtensionApp, undefined)
  assert.equal(admin.createAdminRuntimeRegistry, undefined)
  assert.equal(admin.bootstrapEnabledAdminExtensions, undefined)
  assert.equal(admin.resetLoadedAdminExtensions, undefined)
  assert.equal(admin.ref, undefined)
  assert.equal(admin.ItemList, undefined)
  assert.equal(admin.ResourceNormalizer, undefined)
  assert.equal(typeof adminComponents.resolveApprovalSelectionState, 'function')
  assert.equal(adminComponents.ExtensionGeneratedPermissionsPage, null)
  assert.equal(typeof core.extend, 'function')
  assert.equal(typeof core.override, 'function')
  assert.equal(typeof core.resetPatches, 'function')
  assert.equal(typeof core.ItemList, 'function')
  assert.equal(core.createRuntimeApplication, undefined)
  assert.equal(core.createExtensionAppApi, undefined)
  assert.equal(core.createExtensionInitializers, undefined)
  assert.equal(core.createExtensionPatcher, undefined)
  assert.equal(core.ExportRegistry, undefined)
  assert.equal(typeof core.ResourceModel, 'function')
  assert.equal(typeof core.ResourceModelExtender, 'function')
  assert.equal(typeof core.ResourceNormalizer, 'function')
  assert.equal(typeof core.PostTypes, 'function')
  assert.equal(typeof core.Store, 'function')
  assert.equal(typeof core.ref, 'function')
  assert.equal(core.normalizeExtensionFrontendEntry, undefined)
  assert.equal(core.resolveExtensionRouteComponentKeys, undefined)
  assert.equal(core.registerExtensionFrontendOutput, undefined)
  assert.equal(core.onLazyModuleLoad, undefined)
  assert.equal(core.registerLazyExtensionModule, undefined)
  assert.equal(core.unregisterLazyExtensionModules, undefined)
  assert.equal(typeof core.formatRelativeTime, 'function')
  assert.equal(typeof core.formatMonth, 'function')
  assert.equal(typeof core.unwrapList, 'function')
  assert.equal(forum.formatRelativeTime, undefined)
  assert.equal(forum.formatMonth, undefined)
  assert.equal(forum.unwrapList, undefined)
  assert.equal(forum.createForumExtensionApp, undefined)
  assert.equal(forum.applyExtensionDocumentPayload, undefined)
  assert.equal(forum.normalizeExtensionDocumentPayload, undefined)
  assert.equal(forum.useStartDiscussionAction, undefined)
  assert.equal(forum.getStartDiscussionProvider, undefined)
  assert.equal(forum.registerStartDiscussionProvider, undefined)
  assert.equal(forum.usePaginatedListState, undefined)
  assert.equal(forum.useRequestedPaginatedListState, undefined)
  assert.equal(forum.useRouteListState, undefined)
  assert.equal(forum.useRoutePagination, undefined)
  assert.equal(typeof core.usePaginatedListState, 'function')
  assert.equal(typeof core.useRequestedPaginatedListState, 'function')
  assert.equal(typeof core.useRouteListState, 'function')
  assert.equal(typeof core.useRoutePagination, 'function')
  assert.equal(typeof core.useModalStore, 'function')
  assert.equal(typeof core.useResourceStore, 'function')
  assert.equal(typeof emoji.renderTwemojiHtml, 'function')
  assert.equal(typeof emoji.renderTwemojiText, 'function')
  assert.equal(typeof emoji.searchEmojiItems, 'function')
  assert.equal(typeof realtime.useForumRealtimeStore, 'function')
  assert.equal(typeof realtime.shouldRefreshForumEvent, 'function')
  assert.equal(typeof realtime.getTrackedDiscussionIdsFromDiscussionItems, 'function')
  assert.equal(typeof users.resolveProfileMetaPayload, 'function')
  assert.equal(typeof users.getUserPrimaryGroupLabel, 'function')
  assert.equal(typeof users.buildUserPath, 'function')
  assert.equal(typeof users.normalizeUser, 'function')
  assert.equal(typeof users.useAuthStore, 'function')
  assert.equal(typeof users.useOnlineUsersStore, 'function')
  assert.equal(typeof users.openLoginModal, 'function')
  assert.equal(typeof users.openRegisterModal, 'function')
  assert.equal(typeof users.openForgotPasswordModal, 'function')
  assert.equal(typeof users.sanitizeRedirectPath, 'function')
})
