
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import './archive-theme.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

// 图标由各页面/组件按需 import，不再全量注册（可显著减小首包）

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

app.mount('#app')
