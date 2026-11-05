<template>
  <div class="signal-results" :data-strategy="strategyCode">
    <div class="toolbar">
      <el-date-picker
        v-model="tradeDate"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="交易日（空=最新）"
        clearable
      />
      <el-select
        v-model="configId"
        clearable
        filterable
        placeholder="参数版本（空=默认）"
        style="width: 260px"
      >
        <el-option
          v-for="c in configs"
          :key="c.id"
          :label="configLabel(c)"
          :value="c.id"
        />
      </el-select>
      <el-radio-group
        v-if="showMarketSwitcher"
        v-model="market"
        :disabled="loading"
        @change="onMarketChange"
      >
        <el-radio-button label="CN">A股</el-radio-button>
        <el-radio-button label="HK">港股</el-radio-button>
      </el-radio-group>
      <el-input v-model="code" clearable placeholder="代码" style="width: 140px" @keyup.enter="search" />
      <el-button type="primary" :loading="loading" @click="search">查询</el-button>
    </div>

    <div class="meta-line">
      <span>触发条数 {{ queried ? total : '—' }}</span>
      <span>交易日 {{ tradeDate || '—' }}</span>
      <span>最后写入 {{ formatWrittenAt(lastWrittenAt) }}</span>
    </div>

    <div class="table-wrap">
      <el-table
        class="signal-table"
        :data="items"
        stripe
        border
        v-loading="loading"
        max-height="520"
        style="width: 100%"
        table-layout="fixed"
      >
        <el-table-column
          v-for="col in columns"
          :key="col.prop"
          :prop="col.prop"
          :label="col.label"
          :width="col.width"
          :min-width="col.minWidth"
          :align="col.align"
          :show-overflow-tooltip="col.showOverflowTooltip"
        >
          <template #default="{ row }">
            {{ cellText(row, col) }}
          </template>
        </el-table-column>
        <template #empty>
          <span class="empty-copy">{{ emptyText }}</span>
        </template>
      </el-table>
    </div>

    <div v-if="queried" class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[50, 100, 200, 500]"
        layout="total, sizes, prev, pager, next"
        background
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

export interface SignalListQuery {
  trade_date?: string
  config_id?: number
  market?: 'CN' | 'HK'
  code?: string
  limit?: number
  offset?: number
}

export interface SignalListResponse {
  items?: Record<string, unknown>[]
  total?: number
  trade_date?: string
  config_id?: number
  last_written_at?: string | null
  has_any_trace?: boolean
}

export interface SignalConfigRow {
  id: number
  name: string
  is_default?: boolean
  precompute_enabled?: boolean
  is_active?: boolean
}

export interface SignalColumn {
  prop: string
  label: string
  width?: number | string
  minWidth?: number | string
  align?: 'left' | 'center' | 'right'
  showOverflowTooltip?: boolean
  formatter?: (row: Record<string, unknown>, value: unknown) => string
}

const props = withDefaults(
  defineProps<{
    strategyCode: 'URT' | 'CSB' | 'RPE'
    listSignals: (query: SignalListQuery) => Promise<SignalListResponse>
    listConfigs: () => Promise<SignalConfigRow[]>
    showMarketSwitcher?: boolean
    columns: SignalColumn[]
  }>(),
  { showMarketSwitcher: false }
)

const configs = ref<SignalConfigRow[]>([])
const tradeDate = ref<string>('')
const configId = ref<number | undefined>(undefined)
const market = ref<'CN' | 'HK'>('CN')
const code = ref('')
const items = ref<Record<string, unknown>[]>([])
const total = ref(0)
const lastWrittenAt = ref<string | null>(null)
const hasAnyTrace = ref<boolean | null>(null)
const queried = ref(false)
const queryError = ref('')
const loading = ref(false)
const page = ref(1)
const pageSize = ref(50)
/** 首屏与「查询」主动改页时，避免分页 watch 再打一次请求 */
const suspendPaging = ref(true)

let reqSeq = 0

const emptyText = computed(() => {
  if (!queried.value) return ''
  if (queryError.value) return queryError.value
  if (total.value > 0) return ''
  if (hasAnyTrace.value === true) return '当日无触发信号'
  if (hasAnyTrace.value === false) {
    return '当日可能尚未预计算或无扫描记录；若任务异常请到采集流程核对'
  }
  return '当日无触发信号；若任务异常请到采集流程核对'
})

function pickDefaultConfig(rows: SignalConfigRow[]): number | undefined {
  const active = rows.filter((r) => r.is_active !== false)
  const source = active.length ? active : rows
  const both = source.find((r) => r.is_default && r.precompute_enabled)
  if (both) return both.id
  const byDefault = source.find((r) => r.is_default)
  if (byDefault) return byDefault.id
  const byPrecompute = source.find((r) => r.precompute_enabled)
  if (byPrecompute) return byPrecompute.id
  return source[0]?.id
}

function configLabel(row: SignalConfigRow): string {
  const tags: string[] = []
  if (row.is_default) tags.push('默认')
  if (row.precompute_enabled) tags.push('预计算')
  const extra = tags.length ? ` · ${tags.join('/')}` : ''
  return `${row.name || '未命名'} (#${row.id})${extra}`
}

function formatWrittenAt(raw: string | null | undefined): string {
  if (!raw) return '—'
  return String(raw)
    .replace('T', ' ')
    .replace(/\.\d+/, '')
    .replace(/(\+00:00|Z)$/, '')
}

function cellText(row: Record<string, unknown>, col: SignalColumn): string {
  const value = row[col.prop]
  if (col.formatter) return col.formatter(row, value)
  if (value == null || value === '') return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '—'
    if (Number.isInteger(value)) return String(value)
    const rounded = Math.round(value * 10000) / 10000
    return String(rounded)
  }
  if (col.prop.endsWith('_at')) return formatWrittenAt(String(value))
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function errorMessage(err: unknown): string {
  if (err && typeof err === 'object') {
    const ax = err as {
      response?: { data?: { detail?: unknown; message?: string } }
      message?: string
    }
    const detail = ax.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          if (d && typeof d === 'object' && 'msg' in d) return String((d as { msg?: unknown }).msg ?? d)
          return String(d)
        })
        .join('; ')
    }
    if (typeof ax.message === 'string' && ax.message.trim()) return ax.message
  }
  return '查询失败'
}

function buildQuery(): SignalListQuery {
  const query: SignalListQuery = {
    limit: pageSize.value,
    offset: (page.value - 1) * pageSize.value,
  }
  const date = (tradeDate.value || '').trim()
  if (date) query.trade_date = date
  if (configId.value != null) query.config_id = configId.value
  const codeText = code.value.trim()
  if (codeText) query.code = codeText
  if (props.showMarketSwitcher) query.market = market.value
  return query
}

async function loadConfigOptions() {
  try {
    const rows = await props.listConfigs()
    configs.value = Array.isArray(rows) ? rows : []
    if (configId.value == null) configId.value = pickDefaultConfig(configs.value)
  } catch (err: unknown) {
    configs.value = []
    ElMessage.error(errorMessage(err) || '加载参数版本失败')
  }
}

async function load() {
  const seq = ++reqSeq
  loading.value = true
  queryError.value = ''
  try {
    const data = await props.listSignals(buildQuery())
    if (seq !== reqSeq) return
    items.value = Array.isArray(data?.items) ? data.items : []
    total.value = Number(data?.total ?? items.value.length)
    if (!Number.isFinite(total.value) || total.value < 0) total.value = items.value.length
    if (data?.trade_date) tradeDate.value = String(data.trade_date).slice(0, 10)
    if (data?.config_id != null && !Number.isNaN(Number(data.config_id))) {
      configId.value = Number(data.config_id)
    }
    lastWrittenAt.value = data?.last_written_at ?? null
    hasAnyTrace.value = typeof data?.has_any_trace === 'boolean' ? data.has_any_trace : null
    queried.value = true
  } catch (err: unknown) {
    if (seq !== reqSeq) return
    const text = errorMessage(err)
    queryError.value = text
    items.value = []
    total.value = 0
    lastWrittenAt.value = null
    hasAnyTrace.value = null
    queried.value = true
    ElMessage.error(text || '查询失败')
  } finally {
    if (seq === reqSeq) loading.value = false
  }
}

async function search() {
  suspendPaging.value = true
  page.value = 1
  try {
    await load()
  } finally {
    suspendPaging.value = false
  }
}

function onMarketChange() {
  void search()
}

watch([page, pageSize], () => {
  if (suspendPaging.value) return
  void load()
})

onMounted(async () => {
  try {
    await loadConfigOptions()
    await load()
  } finally {
    suspendPaging.value = false
  }
})
</script>

<style scoped>
.toolbar {
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.meta-line {
  margin: 0 0 8px;
  color: #4b5563;
  font-size: 13px;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}
.table-wrap {
  width: 100%;
  min-width: 0;
}
.signal-table {
  width: 100% !important;
}
.signal-table :deep(.el-table__row) {
  cursor: default;
}
.signal-table :deep(.cell) {
  padding-left: 8px;
  padding-right: 8px;
}
.empty-copy {
  color: #4b5563;
  line-height: 1.5;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
