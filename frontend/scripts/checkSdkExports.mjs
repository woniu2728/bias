import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, relative, resolve } from 'node:path'
import { pathToFileURL, fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const packageRoot = resolve(frontendRoot, 'sdk-package')
const baselinePath = resolve(frontendRoot, 'sdk-export-baseline.json')
const allowedStability = new Set(['stable', 'experimental', 'internal'])

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'))
}

function normalizePath(path) {
  return path.replaceAll('\\', '/')
}

function sortedObject(value) {
  return Object.fromEntries(Object.entries(value).sort(([left], [right]) => left.localeCompare(right)))
}

function readArgValue(argv, prefix) {
  const match = argv.find(item => item.startsWith(prefix))
  return match ? match.slice(prefix.length) : ''
}

function formatExportId(entry, name) {
  const packageEntry = entry === '.' ? '@bias/core' : `@bias/core${entry.slice(1)}`
  return `${packageEntry}:${name}`
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

function normalizeBaselineExports(exportsValue) {
  if (Array.isArray(exportsValue)) {
    return Object.fromEntries(exportsValue.map(name => [String(name), { stability: '' }]))
  }
  if (!exportsValue || typeof exportsValue !== 'object') {
    return {}
  }
  return sortedObject(Object.fromEntries(
    Object.entries(exportsValue).map(([name, metadata]) => {
      if (typeof metadata === 'string') {
        return [name, { stability: metadata }]
      }
      if (!metadata || typeof metadata !== 'object') {
        return [name, { stability: '' }]
      }
      return [name, { stability: String(metadata.stability || '') }]
    }),
  ))
}

function buildBaselineSnapshot(current, previousBaseline = {}, defaultStability = 'stable') {
  const fallbackStability = allowedStability.has(defaultStability) ? defaultStability : 'stable'
  const entries = {}

  for (const [entry, currentEntry] of Object.entries(current.entries || {})) {
    const previousEntry = previousBaseline.entries?.[entry] || {}
    const previousExports = normalizeBaselineExports(previousEntry.exports)
    const exportsMetadata = {}

    for (const name of currentEntry.exports || []) {
      const stability = previousExports[name]?.stability
      exportsMetadata[name] = {
        stability: allowedStability.has(stability) ? stability : fallbackStability,
      }
    }

    entries[entry] = {
      targets: currentEntry.targets || {},
      exports: sortedObject(exportsMetadata),
    }
  }

  return {
    schema_version: 2,
    package: current.package,
    stability_values: [...allowedStability].sort((left, right) => left.localeCompare(right)),
    entries: sortedObject(entries),
  }
}

export function compareBaseline(baseline, current) {
  const issues = []
  const baselineEntries = baseline.entries || {}
  const currentEntries = current.entries || {}

  for (const entry of Object.keys(currentEntries)) {
    if (!baselineEntries[entry]) {
      issues.push(`SDK export entry added without baseline stability: ${entry}`)
    }
  }

  for (const [entry, baselineEntry] of Object.entries(baseline.entries || {})) {
    const currentEntry = currentEntries[entry]
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
    const baselineExports = normalizeBaselineExports(baselineEntry.exports)
    const currentExports = new Set(currentEntry.exports || [])
    for (const [name, metadata] of Object.entries(baselineExports)) {
      if (!allowedStability.has(metadata.stability)) {
        issues.push(`SDK export missing valid stability: ${formatExportId(entry, name)}`)
      }
      if (!currentExports.has(name)) {
        issues.push(`SDK export removed: ${formatExportId(entry, name)}`)
      }
    }
    for (const name of currentExports) {
      if (!baselineExports[name]) {
        issues.push(`SDK export added without baseline stability: ${formatExportId(entry, name)}`)
      }
    }
  }
  return issues.sort((left, right) => left.localeCompare(right))
}

export async function runSdkExportCheck(argv = process.argv) {
  const writeBaseline = argv.includes('--write')
  const defaultStability = readArgValue(argv, '--default-stability=')
  const current = await buildSnapshot()

  if (writeBaseline) {
    const previousBaseline = existsSync(baselinePath) ? readJson(baselinePath) : {}
    const nextBaseline = buildBaselineSnapshot(current, previousBaseline, defaultStability || 'stable')
    writeFileSync(baselinePath, JSON.stringify(nextBaseline, null, 2) + '\n', 'utf8')
    console.log(`Wrote ${normalizePath(relative(frontendRoot, baselinePath))}`)
    return 0
  }

  if (!existsSync(baselinePath)) {
    throw new Error(`Missing SDK export baseline: ${normalizePath(relative(frontendRoot, baselinePath))}`)
  }

  const baseline = readJson(baselinePath)
  const issues = compareBaseline(baseline, current)
  if (issues.length) {
    console.error('SDK export baseline violations:')
    console.error(issues.join('\n'))
    return 1
  }

  console.log(`SDK export baseline is compatible (${Object.keys(current.entries).length} entries).`)
  return 0
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const exitCode = await runSdkExportCheck(process.argv)
  process.exit(exitCode)
}
