import { apiService } from './api'

export interface WorkflowNodeMeta {
  key: string
  name: string
  category: string
  param_schema: Record<string, any>
  supports_scheduled: boolean
  default_params: Record<string, any>
  description?: string
}

export interface WorkflowNodeConfig {
  id?: number
  order_index: number
  node_key: string
  display_name?: string | null
  params?: Record<string, any>
  on_failure?: string
  retry_count?: number
  wait_seconds?: number
  enabled?: boolean
}

export interface CollectionWorkflow {
  id: number
  name: string
  description?: string | null
  enabled: boolean
  trigger_type: 'manual' | 'cron' | string
  cron_dow?: string | null
  cron_hour?: string | null
  cron_minute?: number | null
  skip_on_holiday?: string
  created_at?: string | null
  updated_at?: string | null
  nodes?: WorkflowNodeConfig[]
  node_count?: number
  last_run?: WorkflowRun | null
}

export interface WorkflowNodeRun {
  id: number
  node_key: string
  order_index: number
  status: string
  progress: number
  message?: string | null
  error?: string | null
  started_at?: string | null
  finished_at?: string | null
  result?: Record<string, any>
}

export interface WorkflowRun {
  run_id: string
  workflow_id: number
  workflow_name?: string
  status: string
  trigger_source: string
  current_node_index?: number | null
  started_at?: string | null
  finished_at?: string | null
  error_message?: string | null
  context?: Record<string, any>
  node_runs?: WorkflowNodeRun[]
}

class CollectionWorkflowService {
  listNodes() {
    return apiService.get('/collection-workflows/nodes') as Promise<{
      success: boolean
      data: WorkflowNodeMeta[]
    }>
  }

  listWorkflows() {
    return apiService.get('/collection-workflows') as Promise<{
      success: boolean
      data: CollectionWorkflow[]
    }>
  }

  getWorkflow(id: number) {
    return apiService.get(`/collection-workflows/${id}`) as Promise<{
      success: boolean
      data: CollectionWorkflow
    }>
  }

  createWorkflow(body: Partial<CollectionWorkflow> & { nodes?: WorkflowNodeConfig[] }) {
    return apiService.post('/collection-workflows', body)
  }

  updateWorkflow(id: number, body: Partial<CollectionWorkflow>) {
    return apiService.put(`/collection-workflows/${id}`, body)
  }

  deleteWorkflow(id: number) {
    return apiService.delete(`/collection-workflows/${id}`)
  }

  saveNodes(id: number, nodes: WorkflowNodeConfig[]) {
    return apiService.put(`/collection-workflows/${id}/nodes`, { nodes })
  }

  runWorkflow(id: number, override_params?: Record<string, any>) {
    return apiService.post(`/collection-workflows/${id}/run`, {
      override_params: override_params || null,
    }) as Promise<{ success: boolean; data: { run_id: string } }>
  }

  duplicateWorkflow(id: number) {
    return apiService.post(`/collection-workflows/${id}/duplicate`)
  }

  listRuns(workflowId?: number, limit = 50) {
    const q = new URLSearchParams()
    if (workflowId != null) q.set('workflow_id', String(workflowId))
    q.set('limit', String(limit))
    return apiService.get(`/collection-workflows/runs?${q.toString()}`) as Promise<{
      success: boolean
      data: WorkflowRun[]
    }>
  }

  getRun(runId: string) {
    return apiService.get(`/collection-workflows/runs/${runId}`) as Promise<{
      success: boolean
      data: WorkflowRun
    }>
  }

  cancelRun(runId: string) {
    return apiService.post(`/collection-workflows/runs/${runId}/cancel`)
  }

  activeExecution() {
    return apiService.get('/collection-workflows/active-execution')
  }
}

export const collectionWorkflowService = new CollectionWorkflowService()
