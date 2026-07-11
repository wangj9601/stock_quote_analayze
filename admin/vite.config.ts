import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Plugin } from 'vite'
import { resolve } from 'path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
/** 网站前端静态根目录（stock_gms_trace.html、stock.html、css、js 等），与 admin 同端口开发时由此提供，避免 404 */
const FRONTEND_STATIC_ROOT = path.resolve(__dirname, '../frontend')

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.ico': 'image/x-icon',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.json': 'application/json',
  '.woff2': 'font/woff2',
  '.woff': 'font/woff',
  '.map': 'application/json',
}

function createFrontendStaticMiddleware() {
  const rootNorm = path.normalize(FRONTEND_STATIC_ROOT)
  return (req: any, res: any, next: () => void) => {
    if (req.method !== 'GET' && req.method !== 'HEAD') return next()
    const rawUrl = req.url || ''
    if (
      rawUrl.startsWith('/api') ||
      rawUrl.startsWith('/@') ||
      rawUrl.startsWith('/src/') ||
      rawUrl.startsWith('/node_modules/') ||
      rawUrl.startsWith('/assets/')
    ) {
      return next()
    }
    const pathname = rawUrl.split('?')[0] || ''
    if (!pathname || pathname === '/') return next()
    // 避免与 Vite 提供的管理端入口冲突（仓库 frontend 也有 index.html）
    if (pathname === '/index.html') return next()
    const rel = pathname.replace(/^\//, '')
    const filePath = path.normalize(path.join(FRONTEND_STATIC_ROOT, rel))
    if (!filePath.startsWith(rootNorm)) return next()
    let st: fs.Stats
    try {
      st = fs.statSync(filePath)
    } catch {
      return next()
    }
    if (!st.isFile()) return next()
    const ext = path.extname(filePath).toLowerCase()
    res.setHeader('Content-Type', MIME[ext] || 'application/octet-stream')
    fs.createReadStream(filePath).pipe(res)
  }
}

/** 开发/预览时让 /stock_gms_trace.html、/stock.html、/css/*、/js/* 等指向仓库 frontend 目录 */
function vitePluginServeFrontendStatic(): Plugin {
  return {
    name: 'serve-frontend-static-alongside-admin',
    configureServer(server) {
      server.middlewares.use(createFrontendStaticMiddleware())
    },
    configurePreviewServer(server) {
      server.middlewares.use(createFrontendStaticMiddleware())
    },
  }
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, '..'), '')
  const backendPort = env.BACKEND_PORT || env.VITE_BACKEND_PORT || '5000'
  const apiDevProxy = {
    '/api': {
      target: `http://localhost:${backendPort}`,
      changeOrigin: true,
      secure: false,
    },
  } as const

  return {
    plugins: [vue(), vitePluginServeFrontendStatic()],
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
  }
})