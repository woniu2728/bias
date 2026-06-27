import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import { createViteSdkAliases } from './extensionSdkAliases.mjs'
import { biasExtensionImportMapPlugin } from './extensionImportMapPlugin.mjs'

export default defineConfig({
  plugins: [vue(), biasExtensionImportMapPlugin()],
  resolve: {
    alias: [
      { find: 'vue', replacement: fileURLToPath(new URL('./node_modules/vue/dist/vue.esm-bundler.js', import.meta.url)) },
      { find: 'pinia', replacement: fileURLToPath(new URL('./node_modules/pinia/dist/pinia.mjs', import.meta.url)) },
      { find: 'axios', replacement: fileURLToPath(new URL('./node_modules/axios/index.js', import.meta.url)) },
      { find: '@twemoji/api', replacement: fileURLToPath(new URL('./node_modules/@twemoji/api/dist/twemoji.esm.js', import.meta.url)) },
      { find: 'dayjs', replacement: fileURLToPath(new URL('./node_modules/dayjs/dayjs.min.js', import.meta.url)) },
      { find: 'marked', replacement: fileURLToPath(new URL('./node_modules/marked/lib/marked.esm.js', import.meta.url)) },
      { find: 'highlight.js', replacement: fileURLToPath(new URL('./node_modules/highlight.js/es/index.js', import.meta.url)) },
      { find: '@', replacement: fileURLToPath(new URL('./src', import.meta.url)) },
      ...createViteSdkAliases(),
    ],
    dedupe: ['vue', 'vue-router', 'pinia', 'axios']
  },
  server: {
    port: 3000,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/media': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws': { target: 'ws://localhost:8000', ws: true }
    }
  },
  build: {
    manifest: true,
    rollupOptions: {
      input: {
        main: 'index.html',
        admin: 'admin.html'
      }
    }
  }
})
