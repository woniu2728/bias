import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, isAbsolute, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { discoverExtensionSdkAliases } from '../extensionSdkAliases.mjs'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = resolve(frontendRoot, '..', '..')
const hostSourceRoot = resolve(frontendRoot, 'src')
const sourceFilePattern = /\.(js|jsx|ts|tsx|vue)$/
const testFilePattern = /\.test\.(js|jsx|ts|tsx)$/
const localExtensions = ['', '.js', '.jsx', '.ts', '.tsx', '.vue', '.json']
const importPatterns = [
  /\bimport\s+["']([^"']+)["']/g,
  /\b(?:import|export)\s+[\s\S]*?\s+from\s+["']([^"']+)["']/g,
  /\bimport\(\s*["']([^"']+)["']\s*\)/g,
]

const allowedCoreSdkImports = new Set([
  '@bias/core',
  '@bias/core/common',
  '@bias/core/forum',
  '@bias/core/admin',
  '@bias/core/components/admin',
])

const forbiddenDirectRuntimeImports = new Set([
  'pinia',
  'vue',
  'vue-router',
])

function normalizePath(path) {
  return path.replaceAll('\\', '/')
}

function listFiles(directory, options = {}) {
  const results = []
  if (!existsSync(directory)) {
    return results
  }
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name)
    if (entry.isDirectory()) {
      if (options.skipDirectories?.has(entry.name)) {
        continue
      }
      results.push(...listFiles(path, options))
      continue
    }
    if (sourceFilePattern.test(entry.name) && (!options.skipTests || !testFilePattern.test(entry.name))) {
      results.push(path)
    }
  }
  return results
}

function extractImports(source) {
  const imports = []
  for (const pattern of importPatterns) {
    pattern.lastIndex = 0
    let match
    while ((match = pattern.exec(source))) {
      imports.push(match[1])
    }
  }
  return imports
}

function resolveLocalImport(fromPath, specifier) {
  const basePath = resolve(dirname(fromPath), specifier)
  for (const extension of localExtensions) {
    const candidate = basePath + extension
    if (existsSync(candidate) && statSync(candidate).isFile()) {
      return candidate
    }
  }
  for (const extension of localExtensions.slice(1)) {
    const candidate = resolve(basePath, 'index' + extension)
    if (existsSync(candidate) && statSync(candidate).isFile()) {
      return candidate
    }
  }
  return basePath
}

export function discoverExtensionFrontendRoots(root = workspaceRoot) {
  if (!existsSync(root)) {
    return []
  }
  return readdirSync(root, { withFileTypes: true })
    .filter(entry => entry.isDirectory() && /^bias-ext-/.test(entry.name))
    .map(entry => {
      const packageRoot = resolve(root, entry.name)
      return {
        extensionId: entry.name.slice('bias-ext-'.length),
        packageRoot,
        frontendRoot: resolve(packageRoot, 'frontend'),
      }
    })
    .filter(entry => existsSync(entry.frontendRoot))
    .sort((left, right) => left.extensionId.localeCompare(right.extensionId))
}

function createAllowedPublicImports() {
  return new Set([
    ...allowedCoreSdkImports,
    ...discoverExtensionSdkAliases().map(([alias]) => alias),
  ])
}

function isInsidePath(child, parent) {
  const relativePath = relative(parent, child)
  return relativePath === '' || (!relativePath.startsWith('..') && !isAbsolute(relativePath))
}

export function collectExtensionFrontendBoundaryViolations(options = {}) {
  const roots = options.extensionFrontendRoots || discoverExtensionFrontendRoots(options.workspaceRoot || workspaceRoot)
  const allowedPublicImports = options.allowedPublicImports || createAllowedPublicImports()
  const violations = []

  for (const root of roots) {
    for (const file of listFiles(root.frontendRoot)) {
      const source = readFileSync(file, 'utf8')
      const displayPath = normalizePath(relative(frontendRoot, file))
      for (const specifier of extractImports(source)) {
        if (allowedPublicImports.has(specifier)) {
          continue
        }
        if (specifier.startsWith('@bias/')) {
          violations.push(`${displayPath} imports unknown public SDK ${specifier}`)
          continue
        }
        if (forbiddenDirectRuntimeImports.has(specifier)) {
          violations.push(`${displayPath} imports ${specifier}; use @bias/core instead`)
          continue
        }
        if (specifier.startsWith('@/') || specifier.includes('frontend/src/')) {
          violations.push(`${displayPath} imports host frontend source ${specifier}`)
          continue
        }
        if (specifier.includes('/extensions/') || specifier.startsWith('extensions/')) {
          violations.push(`${displayPath} imports generated extension source ${specifier}`)
          continue
        }
        if (specifier.startsWith('.')) {
          const resolvedImport = resolveLocalImport(file, specifier)
          if (!isInsidePath(resolvedImport, root.frontendRoot)) {
            violations.push(`${displayPath} imports outside its extension frontend ${specifier}`)
          }
        }
      }
    }
  }

  return violations.sort()
}

export function collectHostExtensionSourceBoundaryViolations(options = {}) {
  const root = options.hostSourceRoot || hostSourceRoot
  const displayRoot = options.displayRoot || root
  const violations = []
  for (const file of listFiles(root, {
    skipDirectories: new Set(['generated']),
    skipTests: true,
  })) {
    const source = readFileSync(file, 'utf8')
    if (/import\.meta\.glob\([^)]*bias-ext-\*/.test(source) || source.includes('bias-ext-*/frontend')) {
      violations.push(normalizePath(relative(displayRoot, file)))
    }
  }
  return violations.sort()
}

export function collectFrontendBoundaryViolations(options = {}) {
  return [
    ...collectExtensionFrontendBoundaryViolations(options),
    ...collectHostExtensionSourceBoundaryViolations(options).map(path => `${path} discovers split workspace extension source directly`),
  ].sort()
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const violations = collectFrontendBoundaryViolations()
  if (violations.length) {
    console.error('Extension frontend boundary violations:')
    console.error(violations.join('\n'))
    process.exit(1)
  }
  console.log('Extension frontend boundary is clean.')
}
