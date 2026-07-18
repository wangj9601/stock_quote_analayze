<template>
  <el-dialog
    v-model="visible"
    title="URT 任务详情"
    width="760px"
    destroy-on-close
    @close="handleClose"
  >
    <div v-if="loading" class="flex justify-center p-8">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>
    <div v-else-if="task" class="task-detail">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="任务ID">{{ task.task_id?.slice(0, 8) }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ task.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType">{{ task.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="进度">{{ displayProgress(task.progress) }}%</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ task.created_at || '-' }}</el-descriptions-item>
        <template v-if="task.config">
          <el-descriptions-item label="股票池">{{ stockPoolLabel }}</el-descriptions-item>
          <el-descriptions-item v-if="cnBoardLabel" label="A股板块">{{ cnBoardLabel }}</el-descriptions-item>
          <el-descriptions-item label="日期范围">{{ task.config.start_date }} ~ {{ task.config.end_date }}</el-descriptions-item>
          <el-descriptions-item label="目标涨幅">{{ ((task.config.target_pct || 0) * 100).toFixed(1) }}%</el-descriptions-item>
          <el-descriptions-item label="观察日数">{{ task.config.horizon_days }}</el-descriptions-item>
          <el-descriptions-item label="最低得分">{{ task.config.min_score ?? task.summary?.min_score ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="优先读缓存">{{ task.config.use_trace ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item v-if="poolSizeLabel" label="股票池规模">{{ poolSizeLabel }}</el-descriptions-item>
        </template>
      </el-descriptions>

      <template v-if="task.summary">
        <h4 class="mt-4 mb-2">汇总统计</h4>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="信号数">{{ task.summary.total_signals ?? task.summary.total_samples ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="命中数">{{ task.summary.target_hits ?? task.summary.hit_count ?? 0 }}</el-descriptions-item>
          <el-descriptions-item label="命中率">{{ pct(task.summary.hit_rate) }}</el-descriptions-item>
          <el-descriptions-item label="胜率">{{ pct(task.summary.win_rate) }}</el-descriptions-item>
          <el-descriptions-item label="均盈亏">{{ task.summary.avg_pnl_pct ?? '-' }}%</el-descriptions-item>
          <el-descriptions-item label="目标涨幅">{{ ((task.summary.target_pct || 0) * 100).toFixed(1) }}%</el-descriptions-item>
        </el-descriptions>

        <h4 v-if="scoreBucketRows.length" class="mt-4 mb-2">按分数分桶</h4>
        <el-table v-if="scoreBucketRows.length" :data="scoreBucketRows" size="small" border>
          <el-table-column prop="name" label="分桶" />
          <el-table-column prop="total" label="样本数" width="90" />
          <el-table-column prop="hit" label="命中" width="80" />
          <el-table-column label="命中率" width="100">
            <template #default="{ row }">{{ pct(row.hit_rate) }}</template>
          </el-table-column>
        </el-table>

        <h4 v-if="exitReasonRows.length" class="mt-4 mb-2">离场原因分布</h4>
        <el-table v-if="exitReasonRows.length" :data="exitReasonRows" size="small" border>
          <el-table-column prop="name" label="原因" />
          <el-table-column prop="count" label="笔数" width="100" />
        </el-table>
      </template>

      <h4 class="mt-4 mb-2">日志</h4>
      <div class="log-box">
        <div v-for="(log, i) in logs" :key="i" class="log-line">{{ log.text || log.message || log }}</div>
        <div v-if="!logs.length" class="text-gray-400">暂无日志</div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, inject, onUnmounted, ref, watch } from 'vue'
import { Loading } from '@element-plus/icons-vue'

const props = defineProps<{ modelValue: boolean; taskId: string }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'closed'): void
  (e: 'task-updated', task: any): void
}>()

const urtApi = inject<any>('urtApi')
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const task = ref<any>(null)
const logs = ref<any[]>([])
const loading = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

const statusType = computed(() => {
  const s = task.value?.status
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'danger'
  if (s === 'cancelled') return 'info'
  return 'primary'
})

const STOCK_POOL_LABELS: Record<string, string> = {
  all: '全市场',
  watchlist: '自选股',
  industry_board: '行业板块',
  concept_board: '概念板块',
  single: '单股回测',
  custom: '自定义列表',
}

const CN_BOARD_LABELS: Record<string, string> = {
  MAIN: '主板',
  CYB: '创业板',
  SZ_SME: '中小板',
  KCB: '科创板',
  BJ: '北证',
}

const stockPoolLabel = computed(() => {
  const mode = String(task.value?.config?.stock_pool_mode || 'all')
  const base = STOCK_POOL_LABELS[mode] || mode
  const pool = task.value?.config?.stock_pool
  if (Array.isArray(pool) && pool.length && mode !== 'all') {
    return `${base}（${pool.length} 只）`
  }
  return base
})

const cnBoardLabel = computed(() => {
  const seg = String(task.value?.config?.cn_board_segment || '').toUpperCase()
  if (!seg || seg === 'ALL') return ''
  return CN_BOARD_LABELS[seg] || seg
})

const poolSizeLabel = computed(() => {
  const n = task.value?.summary?.stock_pool_size
  if (n == null) return ''
  return String(n)
})

const scoreBucketRows = computed(() => {
  const buckets = task.value?.summary?.by_score_bucket || {}
  return Object.keys(buckets).map((name) => ({
    name,
    total: buckets[name]?.total ?? 0,
    hit: buckets[name]?.hit ?? 0,
    hit_rate: buckets[name]?.hit_rate ?? 0,
  }))
})

const exitReasonRows = computed(() => {
  const dist = task.value?.summary?.exit_reason_dist || {}
  return Object.keys(dist).map((name) => ({ name, count: dist[name] }))
})

function pct(v: any) {
  if (v == null || Number.isNaN(Number(v))) return '-'
  return `${(Number(v) * 100).toFixed(2)}%`
}

function displayProgress(p: any) {
  const n = Number(p)
  if (Number.isNaN(n)) return 0
  return Math.max(0, Math.min(100, Math.round(n)))
}

function isActive(status?: string) {
  return status === 'pending' || status === 'running'
}

async function load() {
  if (!props.taskId || !urtApi) return
  loading.value = !task.value
  try {
    task.value = await urtApi.getBacktest(props.taskId)
    try {
      logs.value = await urtApi.getBacktestLogs(props.taskId)
    } catch {
      logs.value = (task.value?.logs || []).map((x: any) =>
        typeof x === 'object' ? { text: x.message || x.text, ts: x.ts } : { text: String(x) }
      )
    }
    emit('task-updated', task.value)
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    if (isActive(task.value?.status)) void load()
    else stopPolling()
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function handleClose() {
  stopPolling()
  emit('closed')
}

watch(
  () => [props.modelValue, props.taskId] as const,
  ([open]) => {
    if (open && props.taskId) {
      task.value = null
      void load().then(() => {
        if (isActive(task.value?.status)) startPolling()
      })
    } else {
      stopPolling()
    }
  },
  { immediate: true }
)

onUnmounted(stopPolling)
</script>

<style scoped>
.mt-4 { margin-top: 16px; }
.mb-2 { margin-bottom: 8px; }
.flex { display: flex; }
.justify-center { justify-content: center; }
.p-8 { padding: 32px; }
.log-box {
  max-height: 220px;
  overflow: auto;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 12px;
  line-height: 1.5;
}
.log-line { white-space: pre-wrap; }
.text-gray-400 { color: #9ca3af; }
</style>
