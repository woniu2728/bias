import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const sourceRoot = resolve(frontendRoot, 'src')

function listSourceFiles(directory) {
  const output = []
  for (const entry of readdirSync(directory)) {
    const path = resolve(directory, entry)
    const stat = statSync(path)
    if (stat.isDirectory()) {
      output.push(...listSourceFiles(path))
      continue
    }
    if (/\.(js|ts|vue)$/.test(entry) && !/\.test\.(js|ts)$/.test(entry)) {
      output.push(path)
    }
  }
  return output
}

test('host production frontend loads extension source from generated site extensions only', () => {
  const offenders = []
  for (const path of listSourceFiles(sourceRoot)) {
    const source = readFileSync(path, 'utf8')
    if (/import\.meta\.glob\([^)]*bias-ext-\*/.test(source) || source.includes('bias-ext-*/frontend')) {
      offenders.push(relative(frontendRoot, path).replaceAll('\\', '/'))
    }
  }

  assert.deepEqual(offenders, [])
})
