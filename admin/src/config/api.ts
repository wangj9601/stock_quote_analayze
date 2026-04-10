// API配置文件
export const API_CONFIG = {
  development: {
    baseURL: '',
    timeout: 300000
  },
  // 生产环境：空字符串，由 gmsApi 等使用「/api/admin/...」绝对路径，请求发往当前站点
  production: {
    baseURL: '',
    timeout: 300000
  },
  test: {
    baseURL: '',
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

