export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in?: number
  user?: UserInfo
  admin?: {
    id: number
    username: string
    role: string
    created_at: string
    last_login?: string | null
  }
}

export interface UserInfo {
  id: number
  username: string
  email?: string
  role: string
  created_at: string
  updated_at: string
}

export interface AuthState {
  token: string | null
  user: UserInfo | null
  isAuthenticated: boolean
  loading: boolean
  error: string | null
} 