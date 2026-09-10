import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import * as ElementPlusIcons from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './styles/index.scss'

const app = createApp(App)
app.use(router)
app.use(ElementPlus)

// 注册所有 Element Plus 图标
for (const [key, comp] of Object.entries(ElementPlusIcons)) {
  app.component(key, comp)
}

app.mount('#app')
