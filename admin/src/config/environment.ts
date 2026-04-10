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

// 打印环境信息（仅开发环境）
export const logEnvironmentInfo = () => {
  if (ENVIRONMENT.isDevelopment) {
    console.log('🌍 当前环境:', ENVIRONMENT.current)
    console.log('🔗 API地址:', getCurrentEnvConfig().apiBaseUrl)
    console.log('🐛 调试模式:', getCurrentEnvConfig().enableDebug)
  }
}
