import { existsSync, readdirSync } from 'node:fs'
import { dirname, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const frontendRoot = dirname(fileURLToPath(import.meta.url))
const corePackageRoot = resolve(frontendRoot, 'sdk-package')

const browserCoreAliases = [
  ['@bias/core', 'common.js'],
  ['@bias/core/common', 'common.js'],
  ['@bias/core/forum', 'forum.js'],
  ['@bias/core/admin', 'admin.js'],
  ['@bias/core/components/admin', 'components-admin.js'],
]

const nodeCoreAliases = [
  ['@bias/core', 'common.js'],
  ['@bias/core/common', 'common.js'],
  ['@bias/core/forum', 'forum-node.js'],
  ['@bias/core/admin', 'admin.js'],
  ['@bias/core/components/admin', 'components-admin-node.js'],
]

function discoverExtensionSdks() {
  const results = []
  const seen = new Set()
  const siteExtensionsRoot = resolve(frontendRoot, '..', 'extensions')
  if (existsSync(siteExtensionsRoot)) {
    const entries = readdirSync(siteExtensionsRoot, { withFileTypes: true })
    for (const entry of entries) {
      if (!entry.isDirectory()) continue
      const extId = entry.name
      const sdkPath = resolve(siteExtensionsRoot, entry.name, 'frontend', 'forum', 'sdk.js')
      if (existsSync(sdkPath)) {
        results.push(['@bias/' + extId, sdkPath])
        seen.add(extId)
      }
    }
  }

  // frontendRoot = <workspace>/bias_site/frontend
  // workspace = <workspace>
  const workspace = resolve(frontendRoot, '..', '..')
  if (!existsSync(workspace)) return results

  const entries = readdirSync(workspace, { withFileTypes: true })
  for (const entry of entries) {
    if (!entry.isDirectory()) continue
    const m = entry.name.match(/^bias-ext-(.+)$/)
    if (!m) continue
    const extId = m[1]
    if (seen.has(extId)) continue
    const sdkPath = resolve(workspace, entry.name, 'frontend', 'forum', 'sdk.js')
    if (existsSync(sdkPath)) {
      results.push(['@bias/' + extId, sdkPath])
    }
  }
  return results
}

const extensionSdks = discoverExtensionSdks()

export function discoverExtensionSdkAliases() {
  return extensionSdks.slice()
}

export function createViteSdkAliases() {
  return createBrowserSdkAliasEntries()
    .sort(([left], [right]) => right.length - left.length)
    .map(([find, replacement]) => ({ find, replacement }))
}

export function createBrowserSdkAliasEntries() {
  return [
    ...browserCoreAliases.map(([alias, target]) => [alias, resolve(corePackageRoot, target)]),
    ...extensionSdks,
  ]
}

export function createNodeSdkAliasEntries() {
  return [
    ...nodeCoreAliases.map(([alias, target]) => [alias, resolve(corePackageRoot, target)]),
    ...extensionSdks.map(([alias, target]) => {
      const nodeTarget = resolve(dirname(target), 'nodeSdk.js')
      return [alias, existsSync(nodeTarget) ? nodeTarget : target]
    }),
  ]
}

export function createNodeSdkAliasMap() {
  return new Map(createNodeSdkAliasEntries())
}

export function createJsconfigSdkPaths() {
  const paths = Object.fromEntries(
    browserCoreAliases.map(([alias, target]) => [
      alias,
      [relative(frontendRoot, resolve(corePackageRoot, target)).replaceAll('\\', '/')],
    ]),
  )
  for (const [alias, target] of extensionSdks) {
    paths[alias] = [relative(frontendRoot, target).replaceAll('\\', '/')]
  }
  return paths
}
