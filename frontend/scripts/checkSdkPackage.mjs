import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const packageRoot = resolve(frontendRoot, 'sdk-package')
const localExtensions = ['', '.js', '.vue', '.json']
const sourceExtensions = new Set(['.js', '.vue'])
const importPatterns = [
  /\bimport\s+["']([^"']+)["']/g,
  /\b(?:import|export)\s+[\s\S]*?\s+from\s+["']([^"']+)["']/g,
  /\bimport\(\s*["']([^"']+)["']\s*\)/g,
]

function walkFiles(dir) {
  const results = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = resolve(dir, entry.name)
    if (entry.isDirectory()) {
      results.push(...walkFiles(fullPath))
    } else if (sourceExtensions.has(fullPath.slice(fullPath.lastIndexOf('.')))) {
      results.push(fullPath)
    }
  }
  return results
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
  return null
}

const missing = []
for (const file of walkFiles(packageRoot)) {
  const source = readFileSync(file, 'utf8')
  for (const pattern of importPatterns) {
    pattern.lastIndex = 0
    let match
    while ((match = pattern.exec(source))) {
      const specifier = match[1]
      if (!specifier || (!specifier.startsWith('.') && !specifier.startsWith('/'))) {
        continue
      }
      if (!resolveLocalImport(file, specifier)) {
        missing.push(`${relative(packageRoot, file)} -> ${specifier}`)
      }
    }
  }
}

if (missing.length) {
  console.error('Unresolved @bias/core package-local imports:')
  console.error(missing.join('\n'))
  process.exit(1)
}

console.log('All @bias/core package-local imports resolve.')
