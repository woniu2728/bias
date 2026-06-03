import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { resolve, relative } from 'node:path'

const repoRoot = resolve(process.cwd(), '..')
const extensionRoot = resolve(repoRoot, 'extensions')
const allowedPublicImports = new Set([
  '@/forum/registry',
  '@/admin/registry',
  '@/forum/documentRuntime',
  '@/common/extensionRuntime',
])

function listFrontendFiles(directory) {
  const output = []
  for (const entry of readdirSync(directory)) {
    const path = resolve(directory, entry)
    const stat = statSync(path)
    if (stat.isDirectory()) {
      output.push(...listFrontendFiles(path))
      continue
    }
    if (/\.(js|ts|vue)$/.test(entry)) {
      output.push(path)
    }
  }
  return output
}

function extractImports(source) {
  const imports = []
  const staticImportPattern = /import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]/g
  const dynamicImportPattern = /import\(\s*['"]([^'"]+)['"]\s*\)/g
  for (const pattern of [staticImportPattern, dynamicImportPattern]) {
    let match = pattern.exec(source)
    while (match) {
      imports.push(match[1])
      match = pattern.exec(source)
    }
  }
  return imports
}

test('extension frontend imports only public app APIs', () => {
  const offenders = []
  for (const path of listFrontendFiles(extensionRoot)) {
    const source = readFileSync(path, 'utf8')
    for (const importPath of extractImports(source)) {
      if (!importPath.startsWith('@/')) {
        continue
      }
      if (allowedPublicImports.has(importPath)) {
        continue
      }
      offenders.push(`${relative(repoRoot, path)} imports ${importPath}`)
    }
  }

  assert.deepEqual(offenders, [])
})
