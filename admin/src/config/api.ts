// API配置文件
export const API_CONFIG = {
  // 开发环境
  development: {
    baseURL: 'http://localhost:5000',
    timeout: 300000
  },
  // 生产环境 - 移除 /api 前缀，因为后端路由已统一包含
  production: {
    baseURL: 'https://www.icemaplecity.com',
    timeout: 300000
  },
  // 测试环境
  test: {
    baseURL: 'http://localhost:5000',
    timeout: 300000
  }
}

// 获取当前环境
const getCurrentEnv = (): keyof typeof API_CONFIG => {
  if (import.meta.env.DEV) return 'development'
  if (import.meta.env.PROD) return 'production'
  return 'development'
}

// 导出当前环境的配置
export const getApiConfig = () => {
  const env = getCurrentEnv()
  return API_CONFIG[env]
}

// 导出默认API基础URL
export const API_BASE = getApiConfig().baseURL

// 调试信息
console.log('当前环境:', import.meta.env.MODE)
console.log('API基础URL:', API_BASE)

