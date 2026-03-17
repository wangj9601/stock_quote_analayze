import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { getCurrentEnvConfig, logEnvironmentInfo } from '@/config/environment'
import { getApiConfig } from '@/config/api'

class ApiService {
  private api: AxiosInstance
  private isLoggingOut = false

  constructor() {
    // 打印环境信息
    logEnvironmentInfo()
    
    const apiConfig = getApiConfig()
    
    this.api = axios.create({
      baseURL: import.meta.env.VITE_API_BASE_URL || getCurrentEnvConfig().apiBaseUrl,
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
        // 动态获取认证token，避免在构造函数中过早调用store
        try {
          // 从localStorage直接获取token，避免在构造函数中过早调用store
          const token = localStorage.getItem('admin_token')
          if (token) {
            config.headers.Authorization = `Bearer ${token}`
            console.log('🔐 添加认证token到请求:', config.url)
            console.log('🌐 完整请求URL:', (this.api.defaults.baseURL ?? '') + (config.url ?? ''))
          } else {
            console.warn('⚠️ 未找到认证token，请求:', config.url)
            console.log('🌐 完整请求URL:', (this.api.defaults.baseURL ?? '') + (config.url ?? ''))
          }
        } catch (error) {
          console.error('❌ 获取认证token失败:', error)
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
        if (error.response?.status === 401 && !this.isLoggingOut) {
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