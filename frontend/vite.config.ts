import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// LBP_M 前端构建配置：Vue3 + Vite + 路径别名 + 后端代理
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 3899,
    proxy: {
      '/api': {
        target: 'http://192.168.11.118:8000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://192.168.11.118:8000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://192.168.11.118:8000',
        changeOrigin: true,
      },
    },
  },
})
