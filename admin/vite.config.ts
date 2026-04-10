import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

/** 本地 dev / preview 时将 /api 转到后端，与前端相对路径 /api/admin 配合 */
const apiDevProxy = {
  '/api': {
    target: 'http://localhost:5000',
    changeOrigin: true,
    secure: false,
  },
} as const

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  // 添加基础路径配置，支持生产环境部署
  base: process.env.NODE_ENV === 'production' ? '/admin/' : '/',
  server: {
    port: 8001,
    host: true,
    proxy: apiDevProxy,
  },
  // 新增：生产预览端口配置
  preview: {
    port: 8001,
    host: true,
    proxy: apiDevProxy,
  },
  build: {
    outDir: 'dist',
    sourcemap: false, // 生产环境关闭sourcemap
    // 确保资源路径正确
    assetsDir: 'assets',
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
          elementPlus: ['element-plus'],
        },
      },
    },
  },
  css: {
    postcss: './postcss.config.cjs',
  },
}) 