<template>
  <div class="sbbr-screening">
    <p class="intro">
      与网站选股页同一接口 <code>/api/screening/sbbr-strategy</code>：做小（总市值 20～300 亿或流通股 &gt;5
      亿股）→ 筑底 → 共振弱转强入场。可按基准日回溯，展开明细，并按前复权重算 KDE 支撑/阻力。
    </p>

    <el-form label-width="110px" class="scope-form">
      <el-form-item label="范围">
        <el-select v-model="form.scope" style="width: 240px" @change="onScopeChange">
          <el-option label="全市场（做小宇宙）" value="market" />
          <el-option label="自选股" value="watchlist" />
          <el-option label="储备箱" value="reserve" />
          <el-option label="行业板块" value="industry_board" />
          <el-option label="概念板块" value="concept_board" />
          <el-option label="个股" value="single" />
        </el-select>
      </el-form-item>
      <el-form-item label="基准日">
        <el-date-picker
          v-model="form.date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="留空=最新交易日"
          style="width: 220px"
        />
        <span class="form-hint">按该日及之前行情回溯；非交易日自动对齐</span>
      </el-form-item>
      <el-form-item label="配置版本">
        <el-select v-model="form.configId" clearable placeholder="默认配置" style="width: 280px">
          <el-option
            v-for="c in configs"
            :key="c.id"
            :label="`${c.name} (#${c.id})${c.is_default ? ' · 默认' : ''}`"
            :value="c.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.scope === 'watchlist' || form.scope === 'reserve'" label="网站用户" required>
        <el-select
          v-model="form.userId"
          filterable
          placeholder="选择用户"
          style="width: 320px"
          :loading="loadingUsers"
        >
          <el-option
            v-for="u in scopeUsers"
            :key="u.user_id"
            :label="userOptionLabel(u)"
            :value="u.user_id"
          />
        </el-select>
        <span class="form-hint">管理员账号不在网站用户表，需指定要查看的用户</span>
      </el-form-item>
      <el-form-item v-if="form.scope === 'industry_board'" label="行业板块" required>
        <BoardPickerDialog v-model="industryCodes" board-type="industry" />
      </el-form-item>
      <el-form-item v-if="form.scope === 'concept_board'" label="概念板块" required>
        <BoardPickerDialog v-model="conceptCodes" board-type="concept" />
      </el-form-item>
      <el-form-item v-if="form.scope === 'single'" label="股票" required>
        <el-input
          v-model="form.stockCode"
          clearable
          placeholder="代码或名称，如 000001 或 平安银行"
          style="width: 320px"
          @keyup.enter="refresh"
        />
        <span class="form-hint">绕过做小宇宙硬筛，仍展示策略明细</span>
      </el-form-item>
      <el-form-item v-if="form.scope !== 'single'" label="A股板型">
        <el-checkbox-group v-model="form.segments">
          <el-checkbox v-for="seg in BOARD_SEGMENTS" :key="seg.value" :value="seg.value" :label="seg.value">
            {{ seg.label }}
          </el-checkbox>
        </el-checkbox-group>
        <span class="form-hint">不选=不限板型</span>
      </el-form-item>
      <el-form-item label="过滤">
        <el-checkbox v-model="form.entryOnly">仅入场信号</el-checkbox>
        <el-checkbox v-model="form.traceOnly" :disabled="form.scope !== 'market'">
          优先读预计算
        </el-checkbox>
        <span class="form-hint">预计算仅全市场；无数据时自动回退实时计算</span>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="refresh">刷新筛选</el-button>
        <el-button :loading="qfqLoading" :disabled="!rows.length" @click="refreshQfq">按前复权计算</el-button>
        <el-button :disabled="!rows.length" @click="exportCsv">导出 CSV</el-button>
        <el-button :disabled="!selected.length" @click="openBatchAnalysis">批量个股分析</el-button>
      </el-form-item>
    </el-form>

    <div v-if="metaText" class="meta-line">{{ metaText }}</div>
    <el-alert v-if="noticeMsg" :title="noticeMsg" type="warning" show-icon closable @close="noticeMsg = ''" />
    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon closable @close="errorMsg = ''" />

    <div class="count-line">共 {{ rows.length }} 只</div>
    <el-table
      :data="rows"
      stripe
      border
      v-loading="loading || qfqLoading"
      max-height="640"
      row-key="code"
      @selection-change="onSelectionChange"
    >
      <el-table-column type="selection" width="42" />
      <el-table-column type="expand" width="42">
        <template #default="{ row }">
          <SbbrScoreDetail :stock="row" />
        </template>
      </el-table-column>
      <el-table-column label="代码" width="96" fixed>
        <template #default="{ row }">
          <el-link type="primary" :href="stockHref(row)" target="_blank" :underline="false">
            {{ row.code }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column label="名称" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">
          <span>{{ row.name || '' }}</span>
          <el-tag
            v-for="t in row.role_tags || []"
            :key="t.id || t.label"
            size="small"
            class="name-tag"
            :type="String(t.id) === 'board_mid' || t.label === '中军' ? 'warning' : 'info'"
            :title="t.reason || ''"
          >
            {{ t.label || t.id }}
          </el-tag>
          <el-tag v-if="row.size_ok === false" size="small" type="danger" class="name-tag" title="未通过做小过滤">
            未过做小
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="所属行业" min-width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ row.industry_board_name || row.sector_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="总市值(亿)" width="100" align="right">
        <template #default="{ row }">{{ fmt(row.total_mv) }}</template>
      </el-table-column>
      <el-table-column label="流通股(亿股)" width="110" align="right">
        <template #default="{ row }">{{ fmt(row.circ_shares_yi) }}</template>
      </el-table-column>
      <el-table-column label="筑底模式" width="120" show-overflow-tooltip>
        <template #default="{ row }">{{ bottomModeShort(row.bottom_mode) }}</template>
      </el-table-column>
      <el-table-column label="入场" width="72">
        <template #default="{ row }">
          <el-tag :type="row.entry_signal ? 'success' : 'info'" size="small">
            {{ row.entry_signal ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="收盘" width="80" align="right">
        <template #default="{ row }">{{ fmt(row.close) }}</template>
      </el-table-column>
      <el-table-column label="箱体支撑" width="90" align="right">
        <template #default="{ row }">{{ fmt(row.box_support) }}</template>
      </el-table-column>
      <el-table-column label="箱体阻力" width="90" align="right">
        <template #default="{ row }">{{ fmt(row.box_resistance) }}</template>
      </el-table-column>
      <el-table-column label="KDE支撑" width="90" align="right">
        <template #default="{ row }">{{ fmt(row.nearest_support) }}</template>
      </el-table-column>
      <el-table-column label="KDE阻力" width="90" align="right">
        <template #default="{ row }">{{ fmt(row.nearest_resistance) }}</template>
      </el-table-column>
      <el-table-column label="防守下沿" width="90" align="right">
        <template #default="{ row }">{{ fmt(row.defense_low) }}</template>
      </el-table-column>
      <el-table-column label="量比" width="72" align="right">
        <template #default="{ row }">{{ fmt(row.volume_ratio) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-link type="primary" :href="historyHref(row)" target="_blank" :underline="false">历史</el-link>
          <el-link type="primary" :href="stockHref(row)" target="_blank" :underline="false" class="op-gap">
            个股
          </el-link>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import BoardPickerDialog from '@/components/common/BoardPickerDialog.vue'
import sbbrApi, { type SbbrScopeUser } from '@/services/sbbrApi'
import SbbrScoreDetail from './SbbrScoreDetail.vue'

const BOARD_SEGMENTS = [
  { value: 'MAIN', label: '主板' },
  { value: 'CYB', label: '创业板' },
  { value: 'SZ_SME', label: '中小板' },
  { value: 'KCB', label: '科创板' },
  { value: 'BJ', label: '北证' },
]
const SEG_LABELS: Record<string, string> = Object.fromEntries(BOARD_SEGMENTS.map((s) => [s.value, s.label]))
const BATCH_STORAGE_KEY = 'ssa_trade_analysis_batch'
const QFQ_CHUNK = 8

type Scope = 'market' | 'watchlist' | 'reserve' | 'industry_board' | 'concept_board' | 'single'

const form = reactive({
  scope: 'market' as Scope,
  date: '' as string,
  configId: undefined as number | undefined,
  userId: undefined as number | undefined,
  stockCode: '',
  segments: [] as string[],
  entryOnly: false,
  traceOnly: false,
})

const configs = ref<any[]>([])
const watchlistUsers = ref<SbbrScopeUser[]>([])
const reserveUsers = ref<SbbrScopeUser[]>([])
const industryCodes = ref<string[]>([])
const conceptCodes = ref<string[]>([])
const rows = ref<any[]>([])
const selected = ref<any[]>([])
const loading = ref(false)
const qfqLoading = ref(false)
const loadingUsers = ref(false)
const errorMsg = ref('')
const noticeMsg = ref('')
const metaText = ref('')

const scopeUsers = computed(() => (form.scope === 'reserve' ? reserveUsers.value : watchlistUsers.value))

function fmt(v: unknown) {
  if (v == null || v === '') return '-'
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : String(v)
}

function bottomModeShort(mode: unknown) {
  if (mode === 'range_accumulation') return '横盘收集'
  if (mode === 'panic_accumulation') return '打压恐慌'
  return mode ? String(mode) : '-'
}

function userOptionLabel(u: SbbrScopeUser) {
  const n = form.scope === 'reserve' ? u.reserve_count : u.watchlist_count
  return `${u.username}（${n ?? 0}只）`
}

function stockHref(row: any) {
  const q = new URLSearchParams()
  if (row.code) q.set('code', String(row.code))
  if (row.name) q.set('name', String(row.name))
  q.set('tab', 'analysis')
  return `/stock.html?${q.toString()}`
}

function historyHref(row: any) {
  const q = new URLSearchParams()
  if (row.code) q.set('code', String(row.code))
  if (row.name) q.set('name', String(row.name))
  return `/stock_sbbr_trace.html?${q.toString()}`
}

function onSelectionChange(list: any[]) {
  selected.value = list
}

function onScopeChange() {
  form.userId = undefined
  errorMsg.value = ''
  noticeMsg.value = ''
  if (form.scope !== 'market') form.traceOnly = false
  if (form.scope === 'watchlist' || form.scope === 'reserve') {
    void loadScopeUsers()
  }
}

async function loadConfigs() {
  try {
    const data = await sbbrApi.listConfigs()
    configs.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '加载配置失败')
  }
}

async function loadScopeUsers() {
  loadingUsers.value = true
  try {
    const data = await sbbrApi.listScopeUsers()
    watchlistUsers.value = data.watchlist_users || []
    reserveUsers.value = data.reserve_users || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '加载用户失败')
  } finally {
    loadingUsers.value = false
  }
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('admin_token')
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) h.Authorization = `Bearer ${token}`
  return h
}

async function readError(res: Response) {
  const text = await res.text()
  try {
    const j = JSON.parse(text) as { detail?: unknown; message?: string }
    if (typeof j.detail === 'string') return j.detail
    if (Array.isArray(j.detail)) return j.detail.map((x: any) => x.msg || '').join('; ')
    return j.message || text || `请求失败(${res.status})`
  } catch {
    return text || `请求失败(${res.status})`
  }
}

function buildQuery(traceOnly: boolean) {
  const isSingle = form.scope === 'single'
  const q = new URLSearchParams({
    scope: form.scope,
    entry_only: String(form.entryOnly),
    require_bottom: isSingle ? 'false' : 'true',
    require_size: isSingle ? 'false' : 'true',
    max_results: form.scope === 'industry_board' || form.scope === 'concept_board' ? '2000' : isSingle ? '10' : '200',
  })
  if (form.date) q.set('date', form.date)
  if (form.configId) q.set('config_id', String(form.configId))
  if (form.stockCode.trim()) q.set('stock_code', form.stockCode.trim())
  if (traceOnly && form.scope === 'market') q.set('trace_only', 'true')
  if (!isSingle) form.segments.forEach((seg) => q.append('cn_board_segment', seg))
  industryCodes.value.forEach((c) => q.append('industry_board_code', c))
  conceptCodes.value.forEach((c) => q.append('concept_board_code', c))
  if (form.scope === 'industry_board' && industryCodes.value.length) q.set('board_code_source', 'tonghuashun')
  if (form.scope === 'concept_board' && conceptCodes.value.length) q.set('board_code_source', 'tonghuashun')
  if ((form.scope === 'watchlist' || form.scope === 'reserve') && form.userId) {
    q.set('watchlist_user_id', String(form.userId))
  }
  return q
}

function applyMeta(data: any) {
  const asof = data.asof_date || data.search_date || '-'
  const srcLabel =
    data.source_label || (data.source === 'trace' ? '预计算' : data.source === 'live' ? '实时计算' : data.source || 'live')
  const parts = [`回溯基准日 ${asof}`, `数据来源 ${srcLabel}`, `config ${data.config_id || ''}`]
  if (data.requested_date && data.requested_date !== asof) parts.splice(1, 0, `请求日 ${data.requested_date}→已对齐`)
  if (data.data_max_date) parts.push(`行情最新日 ${data.data_max_date}`)
  if (data.stock_code) parts.push(`个股 ${data.stock_code}`)
  const segMeta =
    data.cn_board_segment_label ||
    (Array.isArray(data.cn_board_segments) && data.cn_board_segments.length
      ? data.cn_board_segments.map((s: string) => SEG_LABELS[s] || s).join('、')
      : '')
  if (segMeta) parts.push(`板型 ${segMeta}`)
  if (data.watchlist_user_id) parts.push(`用户 ${data.watchlist_user_id}`)
  if (Array.isArray(data.industry_board_codes) && data.industry_board_codes.length) {
    parts.push(`行业 ${data.industry_board_codes.join(',')}`)
  }
  if (Array.isArray(data.concept_board_codes) && data.concept_board_codes.length) {
    parts.push(`概念 ${data.concept_board_codes.join(',')}`)
  }
  const isLatest = !data.data_max_date || asof === data.data_max_date
  parts.push(isLatest ? '当前为最新行情日' : `历史回溯：仅使用 ≤${asof} 的 K 线`)
  metaText.value = parts.join(' · ')
  if (asof && asof !== '-' && (!form.date || data.date_snapped)) form.date = asof
  if (data.message) {
    if (data.success === false) errorMsg.value = String(data.message)
    else noticeMsg.value = String(data.message)
  }
}

async function fetchScreening(q: URLSearchParams) {
  const res = await fetch(`/api/screening/sbbr-strategy?${q.toString()}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(await readError(res))
  return (await res.json()) as Record<string, any>
}

async function refresh() {
  errorMsg.value = ''
  noticeMsg.value = ''
  if (form.scope === 'industry_board' && !industryCodes.value.length) {
    ElMessage.warning('请先选择行业板块')
    return
  }
  if (form.scope === 'concept_board' && !conceptCodes.value.length) {
    ElMessage.warning('请先选择概念板块')
    return
  }
  if (form.scope === 'single' && !form.stockCode.trim()) {
    ElMessage.warning('个股范围需要填写股票代码或名称')
    return
  }
  if ((form.scope === 'watchlist' || form.scope === 'reserve') && !form.userId) {
    ElMessage.warning('请选择网站用户')
    return
  }
  loading.value = true
  try {
    let data = await fetchScreening(buildQuery(form.traceOnly && form.scope === 'market'))
    if (form.traceOnly && form.scope === 'market' && !(data.data || []).length) {
      data = await fetchScreening(buildQuery(false))
    }
    rows.value = Array.isArray(data.data) ? data.data : []
    selected.value = []
    applyMeta(data)
  } catch (e: any) {
    rows.value = []
    errorMsg.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

async function refreshQfq() {
  if (!rows.value.length) return
  qfqLoading.value = true
  errorMsg.value = ''
  const codes = [
    ...new Set(
      rows.value
        .map((r) => String(r.code || '').trim().replace(/^(SH|SZ)/i, ''))
        .filter(Boolean)
    ),
  ]
  const byCode = new Map<string, any>()
  let okCount = 0
  let failCount = 0
  try {
    for (let i = 0; i < codes.length; i += QFQ_CHUNK) {
      const chunk = codes.slice(i, i + QFQ_CHUNK)
      const res = await fetch('/api/analysis/levels/batch', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          codes: chunk,
          adjust: 'qfq',
          max_levels: 8,
          refresh_factor: false,
          factor_source: 'auto',
        }),
      })
      if (!res.ok) throw new Error(await readError(res))
      const data = await res.json()
      ;(data.items || []).forEach((it: any) => {
        const c = String(it.code || '').trim()
        if (!c) return
        byCode.set(c, it)
        if (it.success) okCount += 1
        else failCount += 1
      })
    }
    rows.value = rows.value.map((row) => {
      const c = String(row.code || '').trim().replace(/^(SH|SZ)/i, '')
      const it = byCode.get(c)
      if (!it || !it.success) return row
      return {
        ...row,
        nearest_support: it.nearest_support,
        nearest_resistance: it.nearest_resistance,
        support_levels: Array.isArray(it.support_levels) ? it.support_levels : [],
        resistance_levels: Array.isArray(it.resistance_levels) ? it.resistance_levels : [],
        price_adjust: it.price_adjust || 'qfq',
        kde_ok: true,
      }
    })
    metaText.value = `${metaText.value} · 前复权KDE 成功${okCount}/失败${failCount}`
  } catch (e: any) {
    errorMsg.value = e?.message || String(e)
  } finally {
    qfqLoading.value = false
  }
}

function csvCell(v: unknown) {
  const s = v == null ? '' : String(v)
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

function exportCsv() {
  const headers = [
    '代码',
    '名称',
    '所属行业',
    '总市值(亿)',
    '流通股(亿股)',
    '筑底模式',
    '入场',
    '收盘',
    '箱体支撑',
    '箱体阻力',
    'KDE支撑',
    'KDE阻力',
    '防守下沿',
    '量比',
    '做小通过',
    '信号日',
  ]
  const lines = [headers.join(',')]
  rows.value.forEach((r) => {
    lines.push(
      [
        r.code,
        r.name,
        r.industry_board_name || r.sector_name || '',
        r.total_mv,
        r.circ_shares_yi,
        bottomModeShort(r.bottom_mode),
        r.entry_signal ? '是' : '否',
        r.close,
        r.box_support,
        r.box_resistance,
        r.nearest_support,
        r.nearest_resistance,
        r.defense_low,
        r.volume_ratio,
        r.size_ok === false ? '否' : r.size_ok === true ? '是' : '',
        r.date || '',
      ]
        .map(csvCell)
        .join(',')
    )
  })
  const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `sbbr_signals_${form.date || 'latest'}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

async function openBatchAnalysis() {
  const list = selected.value
    .map((r) => ({ code: String(r.code || '').trim(), name: String(r.name || '').trim() }))
    .filter((s) => s.code)
  const uniq = Array.from(new Map(list.map((s) => [s.code, s])).values())
  if (!uniq.length) {
    ElMessage.warning('请先勾选至少一只股票')
    return
  }
  if (uniq.length >= 40) {
    try {
      await ElMessageBox.confirm(`将分析 ${uniq.length} 只股票，耗时可能较长，是否继续？`, '批量个股分析')
    } catch {
      return
    }
  }
  const payload = JSON.stringify({ ts: Date.now(), stocks: uniq })
  try {
    localStorage.setItem(BATCH_STORAGE_KEY, payload)
    sessionStorage.setItem(BATCH_STORAGE_KEY, payload)
  } catch {
    ElMessage.error('无法写入分析参数，请检查浏览器存储权限')
    return
  }
  const maxCodesInUrl = 30
  const codesQs = uniq
    .slice(0, maxCodesInUrl)
    .map((s) => encodeURIComponent(s.code))
    .join(',')
  const url =
    `/analysis.html?tab=stock-ai&batch=selected&popup=1` +
    (codesQs ? `&codes=${codesQs}` : '') +
    (uniq.length > maxCodesInUrl ? `&batch_count=${uniq.length}` : '')
  window.open(url, '_blank')
  ElMessage.success(`已打开个股分析：${uniq.length} 只`)
}

onMounted(() => {
  void loadConfigs()
})
</script>

<style scoped>
.sbbr-screening { padding-top: 4px; }
.intro { margin: 0 0 12px; color: #475569; font-size: 13px; line-height: 1.6; }
.intro code { background: #f1f5f9; padding: 0 4px; border-radius: 4px; }
.form-hint { margin-left: 8px; color: #64748b; font-size: 12px; }
.meta-line { margin: 4px 0 8px; color: #475569; font-size: 13px; line-height: 1.5; }
.count-line { margin: 8px 0; color: #0f172a; font-size: 13px; }
.name-tag { margin-left: 4px; }
.op-gap { margin-left: 10px; }
</style>
