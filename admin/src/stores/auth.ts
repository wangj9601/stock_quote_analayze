import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import { authService } from '@/services/auth.service'
import type { LoginRequest, LoginResponse, UserInfo } from '@/types/auth.types'

function mapLoginProfile(response: LoginResponse): UserInfo | null {
  if (response.user) return response.user
  if (!response.admin) return null
  return {
    id: response.admin.id,
    username: response.admin.username,
    role: response.admin.role,
    created_at: response.admin.created_at,
    updated_at: response.admin.created_at,
  }
}

function formatLoginError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((item) => item?.msg || String(item)).join('；')
    }
    if (err.response?.status === 401) return '用户名或密码错误'
    if (err.response?.status === 422) return '登录请求格式错误，请刷新页面后重试'
  }
  return err instanceof Error ? err.message : '登录失败'
}

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const token = ref<string | null>(null)
  const user = ref<UserInfo | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const isInitialized = ref(false) // 新增：标记是否已初始化

  // 计算属性
  const isAuthenticated = computed(() => {
    // 只有在初始化完成后才检查认证状态
    if (!isInitialized.value) return false
    return !!token.value
  })

  // 动作
  const login = async (credentials: LoginRequest) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await authService.login(credentials)
      const profile = mapLoginProfile(response)
      if (!response.access_token) {
        throw new Error('登录响应缺少 access_token')
      }

      token.value = response.access_token
      user.value = profile

      localStorage.setItem('admin_token', response.access_token)
      if (profile) {
        localStorage.setItem('admin_user', JSON.stringify(profile))
      } else {
        localStorage.removeItem('admin_user')
      }

      return response
    } catch (err) {
      const message = formatLoginError(err)
      error.value = message
      throw new Error(message)
    } finally {
      loading.value = false
    }
  }

  const logout = async () => {
    try {
      await authService.logout()
    } catch (err) {
      console.error('Logout error:', err)
      // 即使后端请求失败，也要清除本地状态
    } finally {
      // 清除状态
      token.value = null
      user.value = null
      error.value = null
      
      // 清除本地存储
      localStorage.removeItem('admin_token')
      localStorage.removeItem('admin_user')
    }
  }

  const initAuth = async () => {
    console.log('🔄 开始初始化认证状态...')
    
    // 检查本地存储中的认证信息
    const savedToken = localStorage.getItem('admin_token')
    const savedUser = localStorage.getItem('admin_user')
    
    if (savedToken && savedUser) {
      try {
        // 验证token是否仍然有效
        console.log('🔍 发现本地存储的认证信息，正在验证...')
        const response = await authService.verifyToken()
        const isValid = response.valid
        
        if (isValid) {
          token.value = savedToken
          user.value = JSON.parse(savedUser)
          console.log('✅ 本地认证信息验证成功')
        } else {
          console.log('❌ 本地认证信息已过期，清除...')
          localStorage.removeItem('admin_token')
          localStorage.removeItem('admin_user')
        }
      } catch (err) {
        console.error('❌ 验证本地认证信息失败:', err)
        // 清除无效的认证信息
        localStorage.removeItem('admin_token')
        localStorage.removeItem('admin_user')
      }
    } else {
      console.log('ℹ️ 本地存储中无认证信息')
    }
    
    // 标记初始化完成
    isInitialized.value = true
    console.log('✅ 认证状态初始化完成，认证状态:', isAuthenticated.value)
  }

  const clearError = () => {
    error.value = null
  }

  return {
    // 状态
    token,
    user,
    loading,
    error,
    isInitialized,
    // 计算属性
    isAuthenticated,
    // 动作
    login,
    logout,
    initAuth,
    clearError
  }
}) 