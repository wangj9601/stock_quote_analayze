<template>
  <div class="collection-workflow-view">
    <div class="header-row">
      <div>
        <h2 class="page-title">采集流程</h2>
        <p class="page-desc">编排采集节点顺序，一次启动或定时串行执行，减少逐步手动启动。</p>
      </div>
      <div class="header-actions">
        <el-button @click="loadAll">刷新</el-button>
        <el-button type="primary" @click="openCreate">新建流程</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="流程列表" name="list">
        <el-table :data="workflows" v-loading="loadingList" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column label="触发" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="row.trigger_type === 'cron' ? 'warning' : 'info'">
                {{ row.trigger_type === 'cron' ? '定时' : '手动' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="Cron" min-width="140">
            <template #default="{ row }">
              <span v-if="row.trigger_type === 'cron'">
                {{ row.cron_dow || '*' }} {{ row.cron_hour }}:{{ String(row.cron_minute ?? 0).padStart(2, '0') }}
              </span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-switch
                :model-value="row.enabled"
                @change="(v: boolean) => toggleEnabled(row, v)"
              />
            </template>
          </el-table-column>
          <el-table-column label="节点数" width="80">
            <template #default="{ row }">{{ row.node_count ?? row.nodes?.length ?? 0 }}</template>
          </el-table-column>
          <el-table-column label="最近运行" min-width="160">
            <template #default="{ row }">
              <template v-if="row.last_run">
                <el-tag size="small" :type="statusTag(row.last_run.status)">{{ row.last_run.status }}</el-tag>
                <span class="muted ml-2">{{ formatTime(row.last_run.started_at) }}</span>
              </template>
              <span v-else class="muted">暂无</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="320" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="editWorkflow(row.id)">编辑</el-button>
              <el-button link type="success" :loading="runningId === row.id" @click="runNow(row)">运行</el-button>
              <el-button link @click="dupWorkflow(row.id)">复制</el-button>
              <el-button link type="danger" @click="removeWorkflow(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="流程编辑" name="edit" :disabled="!editing">
        <div v-if="editing" class="edit-layout">
          <el-form label-width="110px" class="meta-form">
            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="名称" required>
                  <el-input v-model="editing.name" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="触发方式">
                  <el-radio-group v-model="editing.trigger_type">
                    <el-radio value="manual">手动</el-radio>
                    <el-radio value="cron">定时</el-radio>
                  </el-radio-group>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="休市跳过">
                  <el-select v-model="editing.skip_on_holiday" style="width: 100%">
                    <el-option label="不跳过" value="NONE" />
                    <el-option label="A股休市跳过" value="CN" />
                    <el-option label="港股休市跳过" value="HK" />
                    <el-option label="两边都休市才跳过" value="BOTH" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row v-if="editing.trigger_type === 'cron'" :gutter="16">
              <el-col :span="8">
                <el-form-item label="星期">
                  <el-input v-model="editing.cron_dow" placeholder="mon-fri" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="小时">
                  <el-input v-model="editing.cron_hour" placeholder="15 或 11,15" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="分钟">
                  <el-input-number v-model="editing.cron_minute" :min="0" :max="59" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="说明">
              <el-input v-model="editing.description" type="textarea" :rows="2" />
            </el-form-item>
            <el-form-item label="启用">
              <el-switch v-model="editing.enabled" />
            </el-form-item>
          </el-form>

          <div class="editor-grid">
            <div class="panel node-library">
              <div class="panel-head">
                <h3>节点库</h3>
                <el-button link type="primary" :loading="loadingNodes" @click="loadNodes">刷新</el-button>
              </div>
              <el-input v-model="nodeFilter" placeholder="搜索节点" clearable class="mb-2" />
              <div v-if="loadingNodes" class="muted panel-hint">正在加载节点…</div>
              <el-alert
                v-else-if="nodesLoadError"
                type="error"
                :closable="false"
                show-icon
                class="mb-2"
                :title="nodesLoadError"
              />
              <div v-else-if="!Object.keys(groupedNodes).length" class="panel-hint">
                <p>暂无可用节点。</p>
                <p class="muted">请确认 backend_api 已部署采集流程模块并已重启，接口应返回：</p>
                <code class="hint-code">GET /api/admin/collection-workflows/nodes</code>
              </div>
              <div v-for="(group, cat) in groupedNodes" :key="cat" class="cat-block">
                <div class="cat-title">{{ categoryLabel(String(cat)) }}</div>
                <div
                  v-for="n in group"
                  :key="n.key"
                  class="node-chip"
                  @click="addNode(n)"
                >
                  <span>{{ n.name }}</span>
                  <el-tag size="small" type="info">{{ n.key }}</el-tag>
                </div>
              </div>
            </div>

            <div class="panel node-chain">
              <h3>流程节点（可拖拽排序）</h3>
              <div
                v-for="(n, idx) in editing.nodes || []"
                :key="`${n.node_key}-${idx}`"
                class="chain-item"
                :class="{ active: selectedIndex === idx }"
                draggable="true"
                @dragstart="onDragStart(idx)"
                @dragover.prevent
                @drop="onDrop(idx)"
                @click="selectedIndex = idx"
              >
                <span class="ord">{{ idx + 1 }}</span>
                <div class="chain-main">
                  <div class="chain-name">{{ n.display_name || n.node_key }}</div>
                  <div class="muted">{{ n.node_key }} · fail={{ n.on_failure }} · retry={{ n.retry_count }}</div>
                </div>
                <div class="chain-ops">
                  <el-button link @click.stop="moveNode(idx, -1)" :disabled="idx === 0">上移</el-button>
                  <el-button
                    link
                    @click.stop="moveNode(idx, 1)"
                    :disabled="idx === (editing.nodes?.length || 0) - 1"
                  >下移</el-button>
                  <el-button link type="danger" @click.stop="removeNode(idx)">移除</el-button>
                </div>
              </div>
              <el-empty v-if="!(editing.nodes && editing.nodes.length)" description="从左侧添加节点" />
            </div>

            <div class="panel node-props">
              <h3>节点参数</h3>
              <template v-if="selectedNode">
                <el-form label-width="100px" size="small">
                  <el-form-item label="显示名">
                    <el-input v-model="selectedNode.display_name" />
                  </el-form-item>
                  <el-form-item label="失败策略">
                    <el-select v-model="selectedNode.on_failure" style="width: 100%">
                      <el-option label="停止整条流程" value="stop" />
                      <el-option label="继续下一节点" value="continue" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="重试次数">
                    <el-input-number v-model="selectedNode.retry_count" :min="0" :max="5" />
                  </el-form-item>
                  <el-form-item label="前置等待(秒)">
                    <el-input-number v-model="selectedNode.wait_seconds" :min="0" :max="3600" />
                  </el-form-item>
                  <el-form-item label="启用">
                    <el-switch v-model="selectedNode.enabled" />
                  </el-form-item>
                  <template v-for="(schema, key) in selectedParamProps" :key="key">
                    <el-form-item :label="schema.title || String(key)">
                      <el-switch
                        v-if="schema.type === 'boolean'"
                        v-model="selectedNode.params![String(key)]"
                      />
                      <el-date-picker
                        v-else-if="schema.format === 'date'"
                        v-model="selectedNode.params![String(key)]"
                        type="date"
                        value-format="YYYY-MM-DD"
                        style="width: 100%"
                      />
                      <el-select
                        v-else-if="schema.type === 'array' && schema.items?.enum"
                        v-model="selectedNode.params![String(key)]"
                        multiple
                        style="width: 100%"
                      >
                        <el-option
                          v-for="opt in schema.items.enum"
                          :key="opt"
                          :label="opt"
                          :value="opt"
                        />
                      </el-select>
                      <el-input
                        v-else
                        v-model="selectedNode.params![String(key)]"
                        :type="schema.type === 'string' && String(key) === 'stock_codes' ? 'textarea' : 'text'"
                        :rows="3"
                      />
                    </el-form-item>
                  </template>
                </el-form>
              </template>
              <el-empty v-else description="选中中间节点以编辑参数" />
            </div>
          </div>

          <div class="edit-actions">
            <el-button @click="activeTab = 'list'">返回列表</el-button>
            <el-button type="primary" :loading="saving" @click="saveEditing(false)">保存流程</el-button>
            <el-button type="success" :loading="runningId === editing.id" @click="saveEditing(true)">保存并运行</el-button>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="运行监控" name="runs">
        <div class="runs-toolbar">
          <el-select v-model="runFilterWf" clearable placeholder="按流程筛选" style="width: 220px" @change="loadRuns">
            <el-option v-for="w in workflows" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
          <el-button @click="loadRuns">刷新</el-button>
        </div>
        <el-table :data="runs" v-loading="loadingRuns" @row-click="selectRun" highlight-current-row>
          <el-table-column prop="run_id" label="Run ID" min-width="180" />
          <el-table-column prop="workflow_name" label="流程" min-width="140" />
          <el-table-column prop="trigger_source" label="来源" width="90" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTag(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="开始" min-width="150">
            <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column label="结束" min-width="150">
            <template #default="{ row }">{{ formatTime(row.finished_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'running' || row.status === 'pending'"
                link
                type="danger"
                @click.stop="cancelRun(row.run_id)"
              >取消</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="currentRunDetail" class="run-detail">
          <h3>运行详情 · {{ currentRunDetail.run_id }}</h3>
          <p v-if="currentRunDetail.error_message" class="error-text">{{ currentRunDetail.error_message }}</p>
          <el-timeline>
            <el-timeline-item
              v-for="nr in currentRunDetail.node_runs || []"
              :key="nr.id"
              :type="timelineType(nr.status)"
              :timestamp="formatTime(nr.started_at)"
            >
              <div>
                <strong>#{{ nr.order_index + 1 }} {{ nr.node_key }}</strong>
                <el-tag size="small" class="ml-2" :type="statusTag(nr.status)">{{ nr.status }}</el-tag>
              </div>
              <div class="muted">{{ nr.message }}</div>
              <div v-if="nr.error" class="error-text">{{ nr.error }}</div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  collectionWorkflowService,
  type CollectionWorkflow,
  type WorkflowNodeConfig,
  type WorkflowNodeMeta,
  type WorkflowRun,
} from '@/services/collectionWorkflow.service'

const activeTab = ref('list')
const loadingList = ref(false)
const loadingRuns = ref(false)
const saving = ref(false)
const runningId = ref<number | null>(null)

const workflows = ref<CollectionWorkflow[]>([])
const nodeMetas = ref<WorkflowNodeMeta[]>([])
const loadingNodes = ref(false)
const nodesLoadError = ref('')
const nodeFilter = ref('')
const editing = ref<CollectionWorkflow | null>(null)
const selectedIndex = ref<number | null>(null)
const dragFrom = ref<number | null>(null)

const runs = ref<WorkflowRun[]>([])
const runFilterWf = ref<number | undefined>()
const currentRunDetail = ref<WorkflowRun | null>(null)
let pollTimer: number | null = null

const categoryLabel = (c: string) =>
  ({
    cn: 'A股',
    hk: '港股',
    etf: 'ETF',
    agg: '周期聚合',
    strategy: '策略预计算',
    news: '新闻',
    maintain: '维护',
    api: '按需/API',
  }[c] || c)

const groupedNodes = computed(() => {
  const q = nodeFilter.value.trim().toLowerCase()
  const map: Record<string, WorkflowNodeMeta[]> = {}
  for (const n of nodeMetas.value) {
    if (q && !(`${n.name} ${n.key}`.toLowerCase().includes(q))) continue
    ;(map[n.category] ||= []).push(n)
  }
  return map
})

const selectedNode = computed(() => {
  if (!editing.value?.nodes || selectedIndex.value == null) return null
  return editing.value.nodes[selectedIndex.value] || null
})

const selectedParamProps = computed(() => {
  const node = selectedNode.value
  if (!node) return {}
  const meta = nodeMetas.value.find((m) => m.key === node.node_key)
  return (meta?.param_schema?.properties || {}) as Record<string, any>
})

function statusTag(s: string) {
  if (s === 'completed' || s === 'skipped') return 'success'
  if (s === 'running' || s === 'pending') return 'warning'
  if (s === 'failed' || s === 'cancelled') return 'danger'
  return 'info'
}

function timelineType(s: string) {
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'running') return 'primary'
  if (s === 'skipped') return 'info'
  return 'warning'
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  return v.replace('T', ' ').slice(0, 19)
}

async function loadAll() {
  await Promise.all([loadWorkflows(), loadNodes()])
}

async function loadWorkflows() {
  loadingList.value = true
  try {
    const res = await collectionWorkflowService.listWorkflows()
    workflows.value = res.data || []
  } catch (e: any) {
    ElMessage.error(e?.message || '加载流程失败')
  } finally {
    loadingList.value = false
  }
}

function normalizeApiList<T>(res: unknown): T[] {
  if (Array.isArray(res)) return res as T[]
  if (res && typeof res === 'object' && Array.isArray((res as { data?: unknown }).data)) {
    return (res as { data: T[] }).data
  }
  return []
}

function extractApiError(e: unknown): string {
  const err = e as { response?: { status?: number; data?: { detail?: string } }; message?: string }
  const status = err.response?.status
  const detail = err.response?.data?.detail
  if (status === 404) {
    return '接口 404：后端未注册 /api/admin/collection-workflows，请合并 PR 并重启 backend_api'
  }
  return detail || err.message || '请求失败'
}

async function loadNodes() {
  loadingNodes.value = true
  nodesLoadError.value = ''
  try {
    const res = await collectionWorkflowService.listNodes()
    const list = normalizeApiList<WorkflowNodeMeta>(res)
    nodeMetas.value = list
    if (!list.length) {
      nodesLoadError.value = '节点库为空：请检查后端 collection_workflow_api 是否已加载'
    }
  } catch (e: unknown) {
    nodeMetas.value = []
    nodesLoadError.value = extractApiError(e)
    ElMessage.error(nodesLoadError.value)
  } finally {
    loadingNodes.value = false
  }
}

async function loadRuns() {
  loadingRuns.value = true
  try {
    const res = await collectionWorkflowService.listRuns(runFilterWf.value)
    runs.value = res.data || []
  } catch (e: any) {
    ElMessage.error(e?.message || '加载运行历史失败')
  } finally {
    loadingRuns.value = false
  }
}

function openCreate() {
  editing.value = {
    id: 0,
    name: '新采集流程',
    description: '',
    enabled: true,
    trigger_type: 'manual',
    cron_dow: 'mon-fri',
    cron_hour: '15',
    cron_minute: 35,
    skip_on_holiday: 'CN',
    nodes: [],
  }
  selectedIndex.value = null
  activeTab.value = 'edit'
}

async function editWorkflow(id: number) {
  try {
    const res = await collectionWorkflowService.getWorkflow(id)
    const data = res.data
    data.nodes = (data.nodes || []).map((n) => ({
      ...n,
      params: { ...(n.params || {}) },
      on_failure: n.on_failure || 'stop',
      retry_count: n.retry_count ?? 0,
      wait_seconds: n.wait_seconds ?? 0,
      enabled: n.enabled !== false,
    }))
    editing.value = data
    selectedIndex.value = data.nodes.length ? 0 : null
    activeTab.value = 'edit'
  } catch (e: any) {
    ElMessage.error(e?.message || '加载流程详情失败')
  }
}

function addNode(meta: WorkflowNodeMeta) {
  if (!editing.value) return
  const nodes = editing.value.nodes || (editing.value.nodes = [])
  nodes.push({
    order_index: nodes.length,
    node_key: meta.key,
    display_name: meta.name,
    params: { ...(meta.default_params || {}) },
    on_failure: 'stop',
    retry_count: 0,
    wait_seconds: 0,
    enabled: true,
  })
  selectedIndex.value = nodes.length - 1
}

function removeNode(idx: number) {
  if (!editing.value?.nodes) return
  editing.value.nodes.splice(idx, 1)
  reindex()
  if (selectedIndex.value === idx) selectedIndex.value = null
  else if (selectedIndex.value != null && selectedIndex.value > idx) selectedIndex.value -= 1
}

function moveNode(idx: number, delta: number) {
  const nodes = editing.value?.nodes
  if (!nodes) return
  const j = idx + delta
  if (j < 0 || j >= nodes.length) return
  const tmp = nodes[idx]
  nodes[idx] = nodes[j]
  nodes[j] = tmp
  reindex()
  selectedIndex.value = j
}

function onDragStart(idx: number) {
  dragFrom.value = idx
}

function onDrop(toIdx: number) {
  const from = dragFrom.value
  if (from == null || !editing.value?.nodes || from === toIdx) return
  const nodes = editing.value.nodes
  const [item] = nodes.splice(from, 1)
  nodes.splice(toIdx, 0, item)
  reindex()
  selectedIndex.value = toIdx
  dragFrom.value = null
}

function reindex() {
  editing.value?.nodes?.forEach((n, i) => {
    n.order_index = i
  })
}

async function saveEditing(andRun = false) {
  if (!editing.value) return
  if (!editing.value.name?.trim()) {
    ElMessage.warning('请填写流程名称')
    return
  }
  saving.value = true
  try {
    reindex()
    const payload = {
      name: editing.value.name,
      description: editing.value.description,
      enabled: editing.value.enabled,
      trigger_type: editing.value.trigger_type,
      cron_dow: editing.value.cron_dow,
      cron_hour: editing.value.cron_hour,
      cron_minute: editing.value.cron_minute,
      skip_on_holiday: editing.value.skip_on_holiday,
      nodes: editing.value.nodes || [],
    }
    if (!editing.value.id) {
      const res: any = await collectionWorkflowService.createWorkflow(payload)
      editing.value = res.data
      ElMessage.success('已创建流程')
    } else {
      await collectionWorkflowService.updateWorkflow(editing.value.id, payload)
      await collectionWorkflowService.saveNodes(editing.value.id, payload.nodes as WorkflowNodeConfig[])
      ElMessage.success('已保存流程')
    }
    await loadWorkflows()
    if (andRun && editing.value.id) {
      await runNow(editing.value)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function runNow(row: CollectionWorkflow | null) {
  if (!row?.id) {
    await saveEditing(true)
    return
  }
  runningId.value = row.id
  try {
    if (editing.value?.id === row.id) {
      await saveEditing(false)
    }
    const res = await collectionWorkflowService.runWorkflow(row.id)
    ElMessage.success(`已启动：${res.data.run_id}`)
    activeTab.value = 'runs'
    await loadRuns()
    await selectRun({ run_id: res.data.run_id } as WorkflowRun)
    startPolling()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '启动失败')
  } finally {
    runningId.value = null
  }
}

async function toggleEnabled(row: CollectionWorkflow, v: boolean) {
  try {
    await collectionWorkflowService.updateWorkflow(row.id, { enabled: v })
    row.enabled = v
  } catch (e: any) {
    ElMessage.error(e?.message || '更新失败')
  }
}

async function dupWorkflow(id: number) {
  try {
    await collectionWorkflowService.duplicateWorkflow(id)
    ElMessage.success('已复制')
    await loadWorkflows()
  } catch (e: any) {
    ElMessage.error(e?.message || '复制失败')
  }
}

async function removeWorkflow(row: CollectionWorkflow) {
  try {
    await ElMessageBox.confirm(`确认删除流程「${row.name}」？`, '删除确认', { type: 'warning' })
    await collectionWorkflowService.deleteWorkflow(row.id)
    ElMessage.success('已删除')
    if (editing.value?.id === row.id) {
      editing.value = null
      activeTab.value = 'list'
    }
    await loadWorkflows()
  } catch {
    /* cancel */
  }
}

async function selectRun(row: WorkflowRun) {
  try {
    const res = await collectionWorkflowService.getRun(row.run_id)
    currentRunDetail.value = res.data
  } catch (e: any) {
    ElMessage.error(e?.message || '加载运行详情失败')
  }
}

async function cancelRun(runId: string) {
  try {
    await collectionWorkflowService.cancelRun(runId)
    ElMessage.success('已请求取消')
    await loadRuns()
    if (currentRunDetail.value?.run_id === runId) {
      await selectRun({ run_id: runId } as WorkflowRun)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '取消失败')
  }
}

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    if (activeTab.value !== 'runs') return
    await loadRuns()
    if (currentRunDetail.value?.run_id) {
      const st = currentRunDetail.value.status
      if (st === 'running' || st === 'pending') {
        await selectRun(currentRunDetail.value)
      }
    }
  }, 3000)
}

function stopPolling() {
  if (pollTimer != null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

watch(activeTab, (tab) => {
  if (tab === 'edit' && !nodeMetas.value.length && !loadingNodes.value) {
    loadNodes()
  }
})

onMounted(async () => {
  await loadAll()
  await loadRuns()
  startPolling()
})

onUnmounted(() => stopPolling())
</script>

<style scoped>
.collection-workflow-view {
  padding: 8px 4px 24px;
}
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 12px;
}
.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #1f2937;
}
.page-desc {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 13px;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.muted {
  color: #9ca3af;
  font-size: 12px;
}
.ml-2 {
  margin-left: 8px;
}
.mb-2 {
  margin-bottom: 8px;
}
.edit-layout {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.meta-form {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px 12px 0;
}
.editor-grid {
  display: grid;
  grid-template-columns: 240px 1fr 280px;
  gap: 12px;
  min-height: 420px;
}
.panel {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
  overflow: auto;
  max-height: 560px;
}
.panel h3 {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 600;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.panel-head h3 {
  margin: 0;
}
.panel-hint {
  font-size: 13px;
  color: #6b7280;
  padding: 8px 0;
}
.hint-code {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: #374151;
  word-break: break-all;
}
.cat-title {
  font-size: 12px;
  color: #6b7280;
  margin: 10px 0 6px;
  font-weight: 600;
}
.node-chip {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px dashed #d1d5db;
  border-radius: 6px;
  margin-bottom: 6px;
  cursor: pointer;
  font-size: 13px;
}
.node-chip:hover {
  border-color: #3b82f6;
  background: #eff6ff;
}
.chain-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: grab;
  background: #fff;
}
.chain-item.active {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
.ord {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #111827;
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  flex-shrink: 0;
}
.chain-main {
  flex: 1;
  min-width: 0;
}
.chain-name {
  font-weight: 600;
  font-size: 13px;
}
.chain-ops {
  display: flex;
  gap: 2px;
}
.edit-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.runs-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.run-detail {
  margin-top: 20px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fafafa;
}
.error-text {
  color: #dc2626;
  font-size: 13px;
}
@media (max-width: 1100px) {
  .editor-grid {
    grid-template-columns: 1fr;
    max-height: none;
  }
  .panel {
    max-height: none;
  }
}
</style>
