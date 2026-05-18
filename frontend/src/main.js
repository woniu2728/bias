import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { primeCsrfProtection } from './api'
import { useForumStore } from './stores/forum'
import { useForumUiStore } from './stores/forumUi'
import '@fortawesome/fontawesome-free/css/all.min.css'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

primeCsrfProtection().catch(() => {})
useForumStore(pinia).initialize()
useForumUiStore(pinia)

app.mount('#app')
