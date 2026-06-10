import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

export const frontendRoot = dirname(fileURLToPath(import.meta.url))
export const repoRoot = resolve(frontendRoot, '..')
export const extensionsRoot = resolve(repoRoot, 'extensions')

const browserCoreAliases = [
  ['@bias/core', 'src/common/sdk.js'],
  ['@bias/admin/components', 'src/admin/componentsSdk.js'],
  ['@bias/admin', 'src/admin/sdk.js'],
  ['@bias/forum', 'src/forum/sdk.js'],
]

const nodeCoreAliases = [
  ['@bias/core', 'src/common/sdk.js'],
  ['@bias/admin/components', 'src/admin/nodeComponentsSdk.js'],
  ['@bias/admin', 'src/admin/sdk.js'],
  ['@bias/forum', 'src/forum/nodeSdk.js'],
]

export function createViteSdkAliases() {
  return Object.fromEntries(createBrowserSdkAliasEntries())
}

export function createNodeSdkAliasMap() {
  return new Map(createNodeSdkAliasEntries())
}

export function createJsconfigSdkPaths() {
  return Object.fromEntries(
    createBrowserSdkAliasEntries().map(([alias, target]) => [
      alias,
      [normalizeJsconfigPath(relative(frontendRoot, target))],
    ])
  )
}

export function createBrowserSdkAliasEntries() {
  return [
    ...browserCoreAliases.map(([alias, target]) => [alias, resolve(frontendRoot, target)]),
    ...discoverExtensionSdkAliases({ runtime: 'browser' }),
  ]
}

export function createNodeSdkAliasEntries() {
  return [
    ...nodeCoreAliases.map(([alias, target]) => [alias, resolve(frontendRoot, target)]),
    ...discoverExtensionSdkAliases({ runtime: 'node' }),
  ]
}

export function discoverExtensionSdkAliases({ runtime = 'browser' } = {}) {
  if (!existsSync(extensionsRoot)) {
    return []
  }

  return readdirSync(extensionsRoot, { withFileTypes: true })
    .filter(entry => entry.isDirectory())
    .map(entry => resolve(extensionsRoot, entry.name))
    .map(extensionPath => discoverExtensionSdkAlias(extensionPath, runtime))
    .filter(Boolean)
    .sort((left, right) => left[0].localeCompare(right[0]))
}

function discoverExtensionSdkAlias(extensionPath, runtime) {
  const manifestPath = resolve(extensionPath, 'extension.json')
  if (!existsSync(manifestPath)) {
    return null
  }

  const extensionId = readExtensionId(manifestPath)
  if (!extensionId) {
    return null
  }

  const forumFrontendPath = resolve(extensionPath, 'frontend', 'forum')
  const browserSdkPath = resolve(forumFrontendPath, 'sdk.js')
  if (!existsSync(browserSdkPath)) {
    return null
  }

  const nodeSdkPath = resolve(forumFrontendPath, 'nodeSdk.js')
  const target = runtime === 'node' && existsSync(nodeSdkPath)
    ? nodeSdkPath
    : browserSdkPath
  return [`@bias/${extensionId}`, target]
}

function readExtensionId(manifestPath) {
  try {
    const payload = JSON.parse(readFileSync(manifestPath, 'utf8'))
    return String(payload.id || '').trim()
  } catch {
    return ''
  }
}

function normalizeJsconfigPath(path) {
  return path.split(sep).join('/')
}
