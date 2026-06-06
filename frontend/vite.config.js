import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@bias/core': fileURLToPath(new URL('./src/common/sdk.js', import.meta.url)),
      '@bias/admin/components': fileURLToPath(new URL('./src/admin/componentsSdk.js', import.meta.url)),
      '@bias/admin': fileURLToPath(new URL('./src/admin/sdk.js', import.meta.url)),
      '@bias/forum': fileURLToPath(new URL('./src/forum/sdk.js', import.meta.url))
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/media': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
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
