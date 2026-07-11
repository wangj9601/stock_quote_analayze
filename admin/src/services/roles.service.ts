import { apiService } from './api'

export interface FrontendRole {
  id: number
  code: string
  name: string
  description?: string
  is_system: boolean
  created_at: string
}

export interface PermissionTreeNode {
  id: number
  code: string
  name: string
  level: number
  parent_code?: string | null
  channel_code?: string | null
  sort_order: number
  children?: PermissionTreeNode[]
}

export class RolesService {
  async listRoles(): Promise<FrontendRole[]> {
    return apiService.get<FrontendRole[]>('/roles')
  }

  async createRole(data: { code: string; name: string; description?: string }): Promise<FrontendRole> {
    return apiService.post<FrontendRole>('/roles', data)
  }

  async updateRole(id: number, data: { name?: string; description?: string }): Promise<FrontendRole> {
    return apiService.put<FrontendRole>(`/roles/${id}`, data)
  }

  async deleteRole(id: number): Promise<{ success: boolean }> {
    return apiService.delete<{ success: boolean }>(`/roles/${id}`)
  }

  async getRolePermissions(roleId: number): Promise<{ permission_codes: string[] }> {
    return apiService.get<{ permission_codes: string[] }>(`/roles/${roleId}/permissions`)
  }

  async setRolePermissions(roleId: number, permissionCodes: string[]): Promise<{ success: boolean; count: number }> {
    return apiService.put<{ success: boolean; count: number }>(`/roles/${roleId}/permissions`, {
      permission_codes: permissionCodes
    })
  }
}

export class PermissionsService {
  async getTree(): Promise<{ tree: PermissionTreeNode[] }> {
    return apiService.get<{ tree: PermissionTreeNode[] }>('/permissions/tree')
  }

  async sync(): Promise<{ success: boolean; created: number; updated: number; total: number }> {
    return apiService.post('/permissions/sync', {})
  }
}

export const rolesService = new RolesService()
export const permissionsService = new PermissionsService()
