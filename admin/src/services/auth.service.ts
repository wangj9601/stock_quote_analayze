import { apiService } from './api'
import type { LoginRequest, LoginResponse } from '@/types/auth.types'

export class AuthService {
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const body = new URLSearchParams()
    body.append('username', credentials.username)
    body.append('password', credentials.password)

    return apiService.post<LoginResponse>('/auth/login', body, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })
  }

  async logout(): Promise<void> {
    // 设置登出标志，避免响应拦截器触发无限循环
    ;(apiService as any).isLoggingOut = true
    try {
      return await apiService.post('/auth/logout')
    } finally {
      // 重置标志
      ;(apiService as any).isLoggingOut = false
    }
  }

  async verifyToken(): Promise<{ valid: boolean }> {
    return apiService.get('/auth/verify')
  }
}

export const authService = new AuthService() 