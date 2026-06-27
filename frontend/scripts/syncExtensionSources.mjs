import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { basename, dirname, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptRoot = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(scriptRoot, '..')
const siteRoot = resolve(frontendRoot, '..')
const workspaceRoot = resolve(siteRoot, '..')
const siteExtensionsRoot = resolve(siteRoot, 'extensions')
const markerFile = '.bias-generated-extension-source'
const checkOnly = process.argv.includes('--check')

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'))
}

function isValidExtensionId(value) {
  return /^[a-z0-9_-]+$/.test(String(value || ''))
}

function discoverWorkspaceExtensions() {
  if (!existsSync(workspaceRoot)) {
    return []
  }
  const entries = readdirSync(workspaceRoot, { withFileTypes: true })
  return entries
    .filter(entry => entry.isDirectory() && entry.name.startsWith('bias-ext-'))
    .map(entry => resolve(workspaceRoot, entry.name))
    .filter(root => existsSync(resolve(root, 'extension.json')) && existsSync(resolve(root, 'frontend')))
    .sort((left, right) => basename(left).localeCompare(basename(right)))
}

function syncExtensionSource(sourceRoot) {
  const manifestPath = resolve(sourceRoot, 'extension.json')
  const frontendPath = resolve(sourceRoot, 'frontend')
  const manifest = readJson(manifestPath)
  const extensionId = String(manifest.id || '')
  if (!isValidExtensionId(extensionId)) {
    throw new Error(`Invalid extension id in ${manifestPath}: ${extensionId}`)
  }

  const targetRoot = resolve(siteExtensionsRoot, extensionId)
  const targetFrontend = resolve(targetRoot, 'frontend')

  if (existsSync(targetFrontend)) {
    const markerPath = resolve(targetRoot, markerFile)
    if (!existsSync(markerPath)) {
      throw new Error(
        `Refusing to overwrite ${targetFrontend}; missing ${markerFile}. ` +
        'Move local edits to the source extension package or add the marker if this is generated.'
      )
    }
    if (checkOnly) {
      return extensionId
    }
    rmSync(targetFrontend, { recursive: true, force: true })
  }
  if (checkOnly) {
    throw new Error(`Missing synced frontend source for ${extensionId}: ${relative(siteRoot, targetFrontend)}`)
  }
  mkdirSync(targetRoot, { recursive: true })
  cpSync(frontendPath, targetFrontend, { recursive: true })
  cpSync(manifestPath, resolve(targetRoot, 'extension.json'))
  writeFileSync(resolve(targetRoot, markerFile), `${basename(sourceRoot)}\n`)

  return extensionId
}

const sources = discoverWorkspaceExtensions()
mkdirSync(siteExtensionsRoot, { recursive: true })

const synced = []
for (const sourceRoot of sources) {
  synced.push(syncExtensionSource(sourceRoot))
}

console.log(`${checkOnly ? 'Checked' : 'Synced'} ${synced.length} extension frontend source trees.`)
if (synced.length) {
  console.log(synced.join(', '))
}
