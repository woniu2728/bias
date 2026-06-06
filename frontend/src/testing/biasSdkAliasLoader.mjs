const sdkAliases = new Map([
  ['@bias/forum', '../forum/nodeSdk.js'],
  ['@bias/admin', '../admin/sdk.js'],
  ['@bias/admin/components', '../admin/nodeComponentsSdk.js'],
  ['@bias/core', '../common/sdk.js'],
])

export function resolve(specifier, context, nextResolve) {
  const target = sdkAliases.get(specifier)
  if (target) {
    return nextResolve(new URL(target, import.meta.url).href, context)
  }
  return nextResolve(specifier, context)
}
