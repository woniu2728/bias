import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, relative, resolve } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const packageRoot = resolve(frontendRoot, 'sdk-package')
const baselinePath = resolve(frontendRoot, 'sdk-export-baseline.json')
const writeBaseline = process.argv.includes('--write')

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'))
}

function normalizePath(path) {
  return path.replaceAll('\\', '/')
}

function sortedObject(value) {
  return Object.fromEntries(Object.entries(value).sort(([left], [right]) => left.localeCompare(right)))
}

function normalizeExportTarget(target) {
  if (typeof target === 'string') {
    return { default: target }
  }
  if (!target || typeof target !== 'object') {
    return {}
  }
  return sortedObject(Object.fromEntries(
    Object.entries(target)
      .filter(([, value]) => typeof value === 'string')
      .map(([key, value]) => [key, value]),
  ))
}

async function inspectRuntimeExports(targets) {
  const runtimeTarget = targets.node || targets.default || ''
  if (!runtimeTarget) {
    return []
  }
  const path = resolve(packageRoot, runtimeTarget)
  if (!existsSync(path)) {
    throw new Error(`Missing SDK export target: ${runtimeTarget}`)
  }
  const module = await import(pathToFileURL(path).href)
  return Object.keys(module).sort((left, right) => left.localeCompare(right))
}

async function buildSnapshot() {
  const manifest = readJson(resolve(packageRoot, 'package.json'))
  const entries = {}
  for (const [entry, target] of Object.entries(manifest.exports || {})) {
    const targets = normalizeExportTarget(target)
    entries[entry] = {
      targets,
      exports: await inspectRuntimeExports(targets),
    }
  }
  return {
    schema_version: 1,
    package: {
      name: String(manifest.name || ''),
      version: String(manifest.version || ''),
    },
    entries: sortedObject(entries),
  }
}

function compareBaseline(baseline, current) {
  const issues = []
  for (const [entry, baselineEntry] of Object.entries(baseline.entries || {})) {
    const currentEntry = current.entries?.[entry]
    if (!currentEntry) {
      issues.push(`SDK export entry removed: ${entry}`)
      continue
    }
    for (const [condition, target] of Object.entries(baselineEntry.targets || {})) {
      const currentTarget = currentEntry.targets?.[condition]
      if (currentTarget !== target) {
        issues.push(`SDK export target changed: ${entry}.${condition} ${target} -> ${currentTarget || '<missing>'}`)
      }
    }
    const currentExports = new Set(currentEntry.exports || [])
    for (const name of baselineEntry.exports || []) {
      if (!currentExports.has(name)) {
        issues.push(`SDK export removed: ${entry}.${name}`)
      }
    }
  }
  return issues.sort((left, right) => left.localeCompare(right))
}

const current = await buildSnapshot()

if (writeBaseline) {
  writeFileSync(baselinePath, JSON.stringify(current, null, 2) + '\n', 'utf8')
  console.log(`Wrote ${normalizePath(relative(frontendRoot, baselinePath))}`)
  process.exit(0)
}

if (!existsSync(baselinePath)) {
  throw new Error(`Missing SDK export baseline: ${normalizePath(relative(frontendRoot, baselinePath))}`)
}

const baseline = readJson(baselinePath)
const issues = compareBaseline(baseline, current)
if (issues.length) {
  console.error('SDK export baseline violations:')
  console.error(issues.join('\n'))
  process.exit(1)
}

console.log(`SDK export baseline is compatible (${Object.keys(current.entries).length} entries).`)
