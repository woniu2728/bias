import fs from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import path from 'node:path'

const VIRTUAL_ID = 'virtual:bias-extension-import-map'
const RESOLVED_VIRTUAL_ID = `\0${VIRTUAL_ID}`

const fallbackSource = [
  'export const generatedAdminExtensionModules = {}',
  'export const generatedForumExtensionModules = {}',
  '',
].join('\n')

export function biasExtensionImportMapPlugin() {
  const frontendRoot = fileURLToPath(new URL('.', import.meta.url))
  const importMapPath = fileURLToPath(new URL('./src/generated/extensionImportMap.js', import.meta.url))

  return {
    name: 'bias-extension-import-map',
    resolveId(id) {
      if (id === VIRTUAL_ID) {
        return fs.existsSync(importMapPath) ? importMapPath : RESOLVED_VIRTUAL_ID
      }
      return null
    },
    load(id) {
      if (id !== RESOLVED_VIRTUAL_ID) {
        return null
      }
      if (!fs.existsSync(importMapPath)) {
        return fallbackSource
      }
      return null
    },
    transform(source, id) {
      if (path.resolve(id) !== path.resolve(importMapPath)) {
        return null
      }
      return {
        code: normalizeExtensionImportMapSource(source, frontendRoot, importMapPath),
        map: null,
      }
    },
  }
}

export function normalizeExtensionImportMapSource(source, frontendRoot, importMapPath = '') {
  if (!String(source || '').trim()) {
    return fallbackSource
  }
  const importMapDir = path.dirname(importMapPath || path.join(frontendRoot, 'src/generated/extensionImportMap.js'))
  const lines = String(source).split(/\r?\n/)
  const filtered = lines.filter(line => {
    const match = line.match(/import\(["']([^"']+)["']\)/)
    if (!match) {
      return true
    }
    const importPath = match[1]
    if (!importPath.startsWith('.')) {
      return true
    }
    return fs.existsSync(path.resolve(importMapDir, importPath))
  })
  const normalized = filtered.join('\n').trim()
  return normalized ? `${normalized}\n` : fallbackSource
}
