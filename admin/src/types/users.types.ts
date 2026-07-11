export interface User {
  id: number
  username: string
  email: string
  role: string
  role_id?: number | null
  status: 'active' | 'disabled' | 'suspended'
  created_at: string
  updated_at?: string
  last_login?: string
  wechat_userid?: string
}

export interface CreateUserRequest {
  username: string
  email: string
  password: string
  role?: string
  role_id?: number | null
}

export interface UpdateUserRequest {
  email?: string
  role?: string
  role_id?: number | null
  status?: 'active' | 'disabled' | 'suspended'
  wechat_userid?: string
}

export interface UsersResponse {
  data: User[]
  total: number
  page: number
  pageSize: number
} 