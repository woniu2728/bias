import { createApp } from 'vue'
import { createPinia } from 'pinia'
import AdminApp from './AdminApp.vue'
import router from './router'
import api from '../api'
import { createRuntimeApplication } from '../common/application'
import { setRuntimeApplication } from '../common/applicationRegistry'
import { primeCsrfProtection } from '../api'
import { useForumStore } from '../stores/forum'
import { useForumUiStore } from '../stores/forumUi'
import { useResourceStore } from '../stores/resource'
import '@fortawesome/fontawesome-free/css/all.min.css'
import '../assets/main.css'

const app = createApp(AdminApp)
const pinia = createPinia()

app.use(pinia)
app.use(router)

primeCsrfProtection().catch(() => {})
const forumStore = useForumStore(pinia)
const resourceStore = useResourceStore(pinia)
useForumUiStore(pinia)
const runtimeApp = createRuntimeApplication({
  kind: 'admin',
  vueApp: app,
  router,
  pinia,
  api,
  resourceStore,
  forumStore,
})
setRuntimeApplication('admin', runtimeApp)

runtimeApp.boot(async () => {
  await forumStore.initialize()
}).finally(() => {
  app.mount('#app')
})
