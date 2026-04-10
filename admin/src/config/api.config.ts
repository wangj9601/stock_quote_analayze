// API配置文件
export const API_CONFIG = {
  development: {
    baseURL: '/api/admin',
    timeout: 30000
  },
  production: {
    baseURL: '/api/admin',
    timeout: 30000
  },
  test: {
    baseURL: '/api/admin',
    timeout: 30000
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
