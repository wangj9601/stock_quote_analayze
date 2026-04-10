// 环境检测和配置
export const ENVIRONMENT = {
  // 检测是否为生产环境
  isProduction: import.meta.env.PROD,
  
  // 检测是否为开发环境
  isDevelopment: import.meta.env.DEV,
  
  // 检测是否为测试环境
  isTest: import.meta.env.MODE === 'test',
  
  // 获取当前模式
  mode: import.meta.env.MODE || 'development',
  
  // 获取当前环境
  current: import.meta.env.PROD ? 'production' : 'development'
}

// 环境特定的配置
export const ENV_CONFIG = {
  development: {
    // 与 Vite server.proxy 配合，请求发往当前 dev 主机再由代理转到后端
    apiBaseUrl: '/api/admin',
    enableDebug: true,
    logLevel: 'debug'
  },
  production: {
    // 与页面同域，由 Nginx 反代到后端；需固定域名时可设 VITE_API_BASE_URL 覆盖
    apiBaseUrl: '/api/admin',
    enableDebug: false,
    logLevel: 'info'
  },
  test: {
    apiBaseUrl: '/api/admin',
    enableDebug: true,
    logLevel: 'debug'
  }
}

// 获取当前环境的配置
export const getCurrentEnvConfig = () => {
  return ENV_CONFIG[ENVIRONMENT.current as keyof typeof ENV_CONFIG] || ENV_CONFIG.development
}

/**
 * 实际用于 Axios 的 API 根路径。
 * 若 .env 中 VITE_API_BASE_URL 指向 localhost，但通过局域网 IP 访问 Vite（如 http://192.168.x.x:8001），
 * 浏览器会把 localhost 当成「用户本机」，导致 ERR_CONNECTION_REFUSED；此时忽略该环境变量，改用相对路径走当前页的 dev server 代理。
 */
export function getResolvedApiBaseUrl(): string {
  const fallback = getCurrentEnvConfig().apiBaseUrl
  const raw = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim()
  if (!raw) return fallback

  try {
    const url = new URL(raw.includes('://') ? raw : `http://${raw}`)
    const apiIsLoopback = url.hostname === 'localhost' || url.hostname === '127.0.0.1'
    if (typeof window !== 'undefined' && apiIsLoopback) {
      const pageHost = window.location.hostname
      const pageIsLoopback = pageHost === 'localhost' || pageHost === '127.0.0.1'
      if (!pageIsLoopback) {
        return fallback
      }
    }
  } catch {
    return raw || fallback
  }

  return raw
}

// 打印环境信息（仅开发环境）
export const logEnvironmentInfo = () => {
  if (ENVIRONMENT.isDevelopment) {
    console.log('🌍 当前环境:', ENVIRONMENT.current)
    console.log('🔗 API地址(解析后):', getResolvedApiBaseUrl())
    if ((import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim()) {
      console.log('📎 VITE_API_BASE_URL(原始):', import.meta.env.VITE_API_BASE_URL)
    }
    console.log('🐛 调试模式:', getCurrentEnvConfig().enableDebug)
  }
}
