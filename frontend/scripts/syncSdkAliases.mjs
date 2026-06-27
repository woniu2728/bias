import { writeFileSync } from 'node:fs'
import { createJsconfigSdkPaths } from '../extensionSdkAliases.mjs'

// Generate jsconfig.json with SDK alias paths for IDE support
const jsconfig = {
  compilerOptions: {
    baseUrl: '.',
    paths: {
      ...createJsconfigSdkPaths(),
      '@/*': ['./src/*'],
    },
  },
  exclude: ['node_modules', 'dist'],
}

writeFileSync(
  new URL('../jsconfig.json', import.meta.url),
  JSON.stringify(jsconfig, null, 2) + '\n',
)
