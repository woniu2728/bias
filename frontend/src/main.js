import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { primeCsrfProtection } from './api'
import { loadEnabledForumExtensions } from './forum/extensionLoader'
import { useForumStore } from './stores/forum'
import { useForumUiStore } from './stores/forumUi'
import '@fortawesome/fontawesome-free/css/all.min.css'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

primeCsrfProtection().catch(() => {})
const forumStore = useForumStore(pinia)
const forumExtensionModules = import.meta.glob('../../extensions/*/frontend/forum/index.js')
useForumUiStore(pinia)

async function bootstrap() {
  await forumStore.initialize()
  try {
    await loadEnabledForumExtensions({
      forumStore,
      importers: forumExtensionModules,
    })
  } catch (error) {
    console.error('加载前台扩展入口失败:', error)
  }

  app.mount('#app')
}

bootstrap()
