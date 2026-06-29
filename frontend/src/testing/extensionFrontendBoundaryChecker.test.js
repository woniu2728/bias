import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import {
  collectExtensionFrontendBoundaryViolations,
  collectHostExtensionSourceBoundaryViolations,
} from '../../scripts/checkExtensionFrontendBoundary.mjs'

function writeFile(path, source) {
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, source, 'utf8')
}

test('extension frontend boundary checker accepts public sdks and local frontend imports', () => {
  const root = mkdtempSync(resolve(tmpdir(), 'bias-frontend-boundary-'))
  const frontendRoot = resolve(root, 'bias-ext-alpha', 'frontend')
  writeFile(
    resolve(frontendRoot, 'forum', 'index.js'),
    [
      "import { extendForum } from '@bias/core/forum'",
      "import { normalizeUser } from '@bias/users'",
      "import './local.js'",
    ].join('\n')
  )
  writeFile(resolve(frontendRoot, 'forum', 'local.js'), 'export const ok = true\n')

  assert.deepEqual(
    collectExtensionFrontendBoundaryViolations({
      extensionFrontendRoots: [{
        extensionId: 'alpha',
        packageRoot: resolve(root, 'bias-ext-alpha'),
        frontendRoot,
      }],
      allowedPublicImports: new Set(['@bias/core/forum', '@bias/users']),
    }),
    []
  )
})

test('extension frontend boundary checker rejects host and private runtime imports', () => {
  const root = mkdtempSync(resolve(tmpdir(), 'bias-frontend-boundary-'))
  const frontendRoot = resolve(root, 'bias-ext-alpha', 'frontend')
  writeFile(
    resolve(frontendRoot, 'forum', 'index.js'),
    [
      "import { ref } from 'vue'",
      "import api from '@/api'",
      "import '../../backend/private.js'",
      "import { missing } from '@bias/missing'",
      "import '../../bias/frontend/src/common/sdk.js'",
    ].join('\n')
  )

  const violations = collectExtensionFrontendBoundaryViolations({
    extensionFrontendRoots: [{
      extensionId: 'alpha',
      packageRoot: resolve(root, 'bias-ext-alpha'),
      frontendRoot,
    }],
    allowedPublicImports: new Set(['@bias/core']),
  })

  assert.equal(violations.length, 5)
  assert.equal(violations.some(item => item.includes("imports vue; use @bias/core instead")), true)
  assert.equal(violations.some(item => item.includes("imports host frontend source @/api")), true)
  assert.equal(violations.some(item => item.includes("imports outside its extension frontend ../../backend/private.js")), true)
  assert.equal(violations.some(item => item.includes("imports unknown public SDK @bias/missing")), true)
  assert.equal(violations.some(item => item.includes("imports host frontend source ../../bias/frontend/src/common/sdk.js")), true)
})

test('host frontend source boundary checker rejects split workspace source globbing', () => {
  const root = mkdtempSync(resolve(tmpdir(), 'bias-host-boundary-'))
  const sourceRoot = resolve(root, 'src')
  writeFile(resolve(sourceRoot, 'forum', 'loader.js'), "const modules = import.meta.glob('../../bias-ext-*/frontend/forum/index.js')\n")
  writeFile(resolve(sourceRoot, 'generated', 'extensionImportMap.js'), "const modules = import.meta.glob('../../bias-ext-*/frontend/forum/index.js')\n")
  writeFile(resolve(sourceRoot, 'forum', 'loader.test.js'), "const modules = import.meta.glob('../../bias-ext-*/frontend/forum/index.js')\n")

  assert.deepEqual(
    collectHostExtensionSourceBoundaryViolations({ hostSourceRoot: sourceRoot }),
    ['forum/loader.js']
  )
})
