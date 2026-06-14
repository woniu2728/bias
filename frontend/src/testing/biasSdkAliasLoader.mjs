import { pathToFileURL } from 'node:url'
import { createNodeSdkAliasMap } from '../../extensionSdkAliases.mjs'

const sdkAliases = createNodeSdkAliasMap()
const virtualExtensionImportMap = 'virtual:bias-extension-import-map'
const emptyExtensionImportMapSource = [
  'export const generatedAdminExtensionModules = {}',
  'export const generatedForumExtensionModules = {}',
].join('\n')

export function resolve(specifier, context, nextResolve) {
  if (specifier === virtualExtensionImportMap) {
    return {
      shortCircuit: true,
      url: `data:text/javascript,${encodeURIComponent(emptyExtensionImportMapSource)}`,
    }
  }
  const target = sdkAliases.get(specifier)
  if (target) {
    return nextResolve(pathToFileURL(target).href, context)
  }
  if (specifier.startsWith('@/')) {
    return nextResolve(new URL(`../${specifier.slice(2)}`, import.meta.url).href, context)
  }
  return nextResolve(specifier, context)
}
