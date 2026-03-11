export interface User {
  id: number
  username: string
  email: string
  role: 'admin' | 'user' | 'guest'
  status: 'active' | 'disabled' | 'suspended'
  created_at: string
  updated_at?: string
  last_login?: string
  wechat_userid?: string  // 企业微信成员UserID，用于微信通知
}

export interface CreateUserRequest {
  username: string
  email: string
  password: string
  role: 'admin' | 'user' | 'guest'
}

export interface UpdateUserRequest {
  email?: string
  role?: 'admin' | 'user' | 'guest'
  status?: 'active' | 'disabled' | 'suspended'
  wechat_userid?: string  // 企业微信成员UserID，用于微信通知
}

export interface UsersResponse {
  data: User[]
  total: number
  page: number
  pageSize: number
} 