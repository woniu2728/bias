import { pathToFileURL } from 'node:url'
import { createNodeSdkAliasMap } from '../../extensionSdkAliases.mjs'

const sdkAliases = createNodeSdkAliasMap()

export function resolve(specifier, context, nextResolve) {
  const target = sdkAliases.get(specifier)
  if (target) {
    return nextResolve(pathToFileURL(target).href, context)
  }
  if (specifier.startsWith('@/')) {
    return nextResolve(new URL(`../${specifier.slice(2)}`, import.meta.url).href, context)
  }
  return nextResolve(specifier, context)
}
