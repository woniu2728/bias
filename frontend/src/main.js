import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import api from './api'
import { createRuntimeApplication } from './common/application'
import { setRuntimeApplication } from './common/applicationRegistry'
import { primeCsrfProtection } from './api'
import { loadEnabledForumExtensions } from './forum/extensionLoader'
import * as forumRegistry from './forum/registry'
import { useForumStore } from './stores/forum'
import { useForumUiStore } from './stores/forumUi'
import { useResourceStore } from './stores/resource'
import { generatedForumExtensionModules } from 'virtual:bias-extension-import-map'
import '@fortawesome/fontawesome-free/css/all.min.css'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

primeCsrfProtection().catch(() => {})
const forumStore = useForumStore(pinia)
const resourceStore = useResourceStore(pinia)
const forumExtensionModules = {
  ...import.meta.glob('../../extensions/*/frontend/forum/index.js'),
  ...generatedForumExtensionModules,
}
useForumUiStore(pinia)
const runtimeApp = createRuntimeApplication({
  kind: 'forum',
  vueApp: app,
  router,
  pinia,
  api,
  registry: forumRegistry,
  resourceStore,
  forumStore,
})
setRuntimeApplication('forum', runtimeApp)

async function bootstrap() {
  await runtimeApp.boot(async () => {
    await forumStore.initialize()
    try {
      await loadEnabledForumExtensions({
        app: runtimeApp,
        forumStore,
        importers: forumExtensionModules,
        registry: forumRegistry,
        router,
      })
    } catch (error) {
      runtimeApp.handleError(error, 'forum-extension-bootstrap')
      console.error('加载前台扩展入口失败:', error)
    }
  })

  app.use(router)
  app.mount('#app')
}

bootstrap()
