import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { getCurrentEnvConfig, getResolvedApiBaseUrl, logEnvironmentInfo } from '@/config/environment'
import { getApiConfig } from '@/config/api'

class ApiService {
  private api: AxiosInstance
  private isLoggingOut = false

  constructor() {
    // 打印环境信息
    logEnvironmentInfo()
    
    const apiConfig = getApiConfig()
    
    this.api = axios.create({
      baseURL: getResolvedApiBaseUrl(),
      timeout: apiConfig.timeout,
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    // 调试信息
    console.log('🏗️ ApiService初始化')
    console.log('📍 BaseURL:', this.api.defaults.baseURL)
    console.log('⚙️ 环境配置:', getCurrentEnvConfig())

    // 请求拦截器
    this.api.interceptors.request.use(
      (config) => {
        const reqUrl = String(config.url ?? '')
        const isPublicAuthRequest =
          reqUrl.includes('/auth/login') || reqUrl.includes('/auth/logout')

        try {
          const token = localStorage.getItem('admin_token')
          if (token) {
            config.headers.Authorization = `Bearer ${token}`
          } else if (!isPublicAuthRequest && getCurrentEnvConfig().enableDebug) {
            console.warn('未找到认证 token，请求:', reqUrl)
          }
        } catch (error) {
          console.error('获取认证 token 失败:', error)
        }

        // URLSearchParams / FormData 不能用默认 application/json
        if (config.data instanceof URLSearchParams) {
          config.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        } else if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
          delete config.headers['Content-Type']
        }

        return config
      },
      (error) => Promise.reject(error)
    )

    // 响应拦截器
    this.api.interceptors.response.use(
      (response) => response.data,
      (error) => {
        // 避免在登出请求时触发无限循环
        const reqUrl = String(error.config?.url ?? '')
        const isLoginAttempt = reqUrl.includes('/auth/login')
        // 登录接口返回 401：交给登录页展示错误，切勿整页跳转（否则会刷新掉表单错误提示）
        if (error.response?.status === 401 && !this.isLoggingOut && !isLoginAttempt) {
          console.log('🔒 收到401未授权响应，清除认证状态')
          // 清除本地存储的认证信息
          localStorage.removeItem('admin_token')
          localStorage.removeItem('admin_user')
          // 重定向到登录页面
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }

  get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.api.get(url, config)
  }

  post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.api.post(url, data, config)
  }

  put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.api.put(url, data, config)
  }

  patch<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.api.patch(url, data, config)
  }

  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.api.delete(url, config)
  }
}

export const apiService = new ApiService() 