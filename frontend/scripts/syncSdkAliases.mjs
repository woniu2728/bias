import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createJsconfigSdkPaths, frontendRoot } from '../extensionSdkAliases.mjs'

const jsconfigPath = resolve(frontendRoot, 'jsconfig.json')
const jsconfig = JSON.parse(readFileSync(jsconfigPath, 'utf8'))
const compilerOptions = jsconfig.compilerOptions || {}
const currentPaths = compilerOptions.paths || {}
const generatedPaths = createJsconfigSdkPaths()
const preservedPaths = Object.fromEntries(
  Object.entries(currentPaths).filter(([key]) => !key.startsWith('@bias/'))
)

const nextJsconfig = {
  ...jsconfig,
  compilerOptions: {
    ...compilerOptions,
    paths: {
      ...preservedPaths,
      ...generatedPaths,
    },
  },
}

const currentText = JSON.stringify(jsconfig, null, 2) + '\n'
const nextText = JSON.stringify(nextJsconfig, null, 2) + '\n'
if (nextText !== currentText) {
  writeFileSync(jsconfigPath, nextText, 'utf8')
}
