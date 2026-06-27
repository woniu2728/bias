import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { dirname, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptRoot = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(scriptRoot, '..')
const sourceRoot = resolve(frontendRoot, 'src')
const packageRoot = resolve(frontendRoot, 'sdk-package')
const packageSourceRoot = resolve(packageRoot, 'src')
const checkOnly = process.argv.includes('--check')

const entryFiles = [
  'common/sdk.js',
  'forum/sdk.js',
  'forum/nodeSdk.js',
  'admin/sdk.js',
  'admin/componentsSdk.js',
  'admin/nodeComponentsSdk.js',
]

const localExtensions = ['', '.js', '.vue', '.json']
const sourceExtensions = new Set(['.js', '.vue'])
const importPatterns = [
  /\bimport\s+["']([^"']+)["']/g,
  /\b(?:import|export)\s+[\s\S]*?\s+from\s+["']([^"']+)["']/g,
  /\bimport\(\s*["']([^"']+)["']\s*\)/g,
]

function readSource(path) {
  return readFileSync(path, 'utf8')
}

function resolveFile(basePath) {
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
  return null
}

function resolveImport(fromPath, specifier) {
  if (specifier.startsWith('@/')) {
    return resolveFile(resolve(sourceRoot, specifier.slice(2)))
  }
  if (specifier.startsWith('.') || specifier.startsWith('/')) {
    return resolveFile(resolve(dirname(fromPath), specifier))
  }
  return null
}

function collectSourceClosure() {
  const seen = new Set()
  const missing = []

  function walk(path) {
    const sourcePath = resolve(path)
    if (seen.has(sourcePath)) return
    seen.add(sourcePath)

    const source = readSource(sourcePath)
    for (const pattern of importPatterns) {
      pattern.lastIndex = 0
      let match
      while ((match = pattern.exec(source))) {
        const specifier = match[1]
        if (!specifier || (!specifier.startsWith('.') && !specifier.startsWith('/') && !specifier.startsWith('@/'))) {
          continue
        }
        const target = resolveImport(sourcePath, specifier)
        if (!target) {
          missing.push(`${relative(frontendRoot, sourcePath)} -> ${specifier}`)
          continue
        }
        walk(target)
      }
    }
  }

  for (const entry of entryFiles) {
    walk(resolve(sourceRoot, entry))
    const typeSource = resolve(sourceRoot, entry.replace(/\.js$/, '.d.ts'))
    if (existsSync(typeSource)) seen.add(typeSource)
  }

  if (missing.length) {
    throw new Error(`Unresolved SDK source imports:\n${missing.join('\n')}`)
  }

  return [...seen].sort()
}

function listPackageSourceFiles() {
  if (!existsSync(packageSourceRoot)) return []
  const results = []
  function walk(dir) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const fullPath = resolve(dir, entry.name)
      if (entry.isDirectory()) {
        walk(fullPath)
      } else {
        results.push(fullPath)
      }
    }
  }
  walk(packageSourceRoot)
  return results.sort()
}

function rewriteAliasImports(source, sourcePath) {
  return source.replace(/(["'])@\/([^"']+)\1/g, (match, quote, specifier) => {
    const target = resolveImport(sourcePath, `@/${specifier}`)
    if (!target) return match
    let nextSpecifier = relative(dirname(sourcePath), target).replaceAll('\\', '/')
    if (!nextSpecifier.startsWith('.')) nextSpecifier = `./${nextSpecifier}`
    return `${quote}${nextSpecifier}${quote}`
  })
}

function packagePathForSource(sourcePath) {
  return resolve(packageSourceRoot, relative(sourceRoot, sourcePath))
}

function expectedPackageFiles(sourceFiles) {
  return new Set(sourceFiles.map(packagePathForSource))
}

function isSameFileContent(left, right) {
  if (!existsSync(right)) return false
  return readFileSync(left, 'utf8') === readFileSync(right, 'utf8')
}

function assertPackageSourcesSynced(sourceFiles) {
  const expected = expectedPackageFiles(sourceFiles)
  const actual = new Set(listPackageSourceFiles())
  const missing = [...expected].filter(path => !actual.has(path))
  const extra = [...actual].filter(path => !expected.has(path))
  const changed = []

  for (const sourcePath of sourceFiles) {
    const targetPath = packagePathForSource(sourcePath)
    const source = rewriteAliasImports(readSource(sourcePath), sourcePath)
    if (!existsSync(targetPath) || readFileSync(targetPath, 'utf8') !== source) {
      changed.push(relative(frontendRoot, targetPath))
    }
  }

  if (missing.length || extra.length || changed.length) {
    const lines = [
      ...missing.map(path => `missing ${relative(frontendRoot, path)}`),
      ...extra.map(path => `extra ${relative(frontendRoot, path)}`),
      ...changed.map(path => `changed ${path}`),
    ]
    throw new Error(`SDK package sources are out of sync:\n${lines.join('\n')}`)
  }
}

function syncPackageSources(sourceFiles) {
  const packageRootPath = resolve(packageRoot)
  if (existsSync(packageSourceRoot)) {
    const resolvedTarget = resolve(packageSourceRoot)
    if (!resolvedTarget.startsWith(packageRootPath)) {
      throw new Error(`Refusing to remove path outside SDK package: ${resolvedTarget}`)
    }
    rmSync(resolvedTarget, { recursive: true, force: true })
  }

  for (const sourcePath of sourceFiles) {
    const targetPath = packagePathForSource(sourcePath)
    mkdirSync(dirname(targetPath), { recursive: true })
    if (sourceExtensions.has(sourcePath.slice(sourcePath.lastIndexOf('.')))) {
      writeFileSync(targetPath, rewriteAliasImports(readSource(sourcePath), sourcePath))
    } else {
      cpSync(sourcePath, targetPath)
    }
  }
}

const sourceFiles = collectSourceClosure()
if (checkOnly) {
  assertPackageSourcesSynced(sourceFiles)
  console.log(`Checked ${sourceFiles.length} @bias/core SDK source files.`)
} else {
  syncPackageSources(sourceFiles)
  console.log(`Synced ${sourceFiles.length} @bias/core SDK source files.`)
}
