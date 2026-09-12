<template>
  <div class="dashboard-view">
    <!-- 行业 / 概念板块资金流向（日 / 周 / 月） -->
    <div class="fund-flow-charts">
      <el-card class="fund-flow-card board-flow-card">
        <template #header>
          <div class="fund-flow-card-header stock-flow-header">
            <div class="stock-flow-header-left">
              <span>板块资金流向趋势跟踪</span>
              <el-radio-group
                v-model="boardFlowPeriod"
                size="small"
                class="stock-flow-period"
                @change="onBoardFlowPeriodChange"
              >
                <el-radio-button
                  v-for="p in boardFlowPeriods"
                  :key="p.value"
                  :label="p.value"
                >
                  {{ p.label }}
                </el-radio-button>
              </el-radio-group>
            </div>
            <span class="fund-flow-date">
              {{ boardFlowPeriodLabel }}净流入
              <template v-if="boardFlowRangeText"> · {{ boardFlowRangeText }}</template>
            </span>
          </div>
        </template>
        <el-row :gutter="16">
          <el-col :xs="24" :sm="24" :md="12" :lg="12" :xl="12">
            <div class="board-flow-panel" v-loading="industryLoading">
              <div class="board-flow-panel-header">
                <span>行业板块</span>
                <span class="fund-flow-date">
                  <template v-if="industryCount">{{ industryCount }} 个</template>
                  <template v-else>--</template>
                </span>
              </div>
              <div
                v-show="!industryEmpty && !industryError"
                ref="industryChartRef"
                class="fund-flow-chart"
              />
              <div v-if="industryEmpty" class="fund-flow-empty">暂无板块资金流（请先日采）</div>
              <div v-else-if="industryError" class="fund-flow-empty fund-flow-error">
                {{ industryError }}
              </div>
            </div>
          </el-col>
          <el-col :xs="24" :sm="24" :md="12" :lg="12" :xl="12">
            <div class="board-flow-panel" v-loading="conceptLoading">
              <div class="board-flow-panel-header">
                <span>概念板块</span>
                <span class="fund-flow-date">
                  <template v-if="conceptCount">{{ conceptCount }} 个</template>
                  <template v-else>--</template>
                </span>
              </div>
              <div
                v-show="!conceptEmpty && !conceptError"
                ref="conceptChartRef"
                class="fund-flow-chart"
              />
              <div v-if="conceptEmpty" class="fund-flow-empty">暂无板块资金流（请先日采）</div>
              <div v-else-if="conceptError" class="fund-flow-empty fund-flow-error">
                {{ conceptError }}
              </div>
            </div>
          </el-col>
        </el-row>
      </el-card>
    </div>

    <!-- 个股资金流向趋势跟踪（日 / 周 / 月） -->
    <div class="fund-flow-charts stock-fund-flow-charts">
      <el-card class="fund-flow-card" v-loading="stockFlowLoading">
        <template #header>
          <div class="fund-flow-card-header stock-flow-header">
            <div class="stock-flow-header-left">
              <span>个股资金流向趋势跟踪</span>
              <el-radio-group
                v-model="stockFlowPeriod"
                size="small"
                class="stock-flow-period"
                @change="onStockFlowPeriodChange"
              >
                <el-radio-button
                  v-for="p in stockFlowPeriods"
                  :key="p.value"
                  :label="p.value"
                >
                  {{ p.label }}
                </el-radio-button>
              </el-radio-group>
            </div>
            <span class="fund-flow-date">
              {{ stockFlowPeriodLabel }}净流入
              <template v-if="stockFlowRangeText"> · {{ stockFlowRangeText }}</template>
              <template v-if="stockFlowCount"> · {{ stockFlowCount }} 只</template>
            </span>
          </div>
        </template>
        <div
          v-show="!stockFlowEmpty && !stockFlowError"
          ref="stockFlowChartRef"
          class="fund-flow-chart"
        />
        <div v-if="stockFlowEmpty" class="fund-flow-empty">
          暂无个股资金流（请先日采同花顺资金流向）
        </div>
        <div v-else-if="stockFlowError" class="fund-flow-empty fund-flow-error">
          {{ stockFlowError }}
        </div>
      </el-card>
    </div>

    <!-- 行业 / 概念板块趋势跟踪（中线 60 日斜率） -->
    <div class="fund-flow-charts slope-trend-charts">
      <el-row :gutter="16">
        <el-col :xs="24" :sm="24" :md="12" :lg="12" :xl="12">
          <el-card class="fund-flow-card" v-loading="industrySlopeLoading">
            <template #header>
              <div class="fund-flow-card-header">
                <span>行业板块趋势跟踪</span>
                <span class="fund-flow-date">
                  中线斜率
                  <template v-if="industrySlopeAsof"> · {{ industrySlopeAsof }}</template>
                  <template v-if="industrySlopeCount"> · {{ industrySlopeCount }} 个</template>
                </span>
              </div>
            </template>
            <div
              v-show="!industrySlopeEmpty && !industrySlopeError"
              ref="industrySlopeChartRef"
              class="fund-flow-chart"
            />
            <div v-if="industrySlopeEmpty" class="fund-flow-empty">
              暂无板块斜率（请先在行情页刷新斜率入库）
            </div>
            <div v-else-if="industrySlopeError" class="fund-flow-empty fund-flow-error">
              {{ industrySlopeError }}
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="24" :md="12" :lg="12" :xl="12">
          <el-card class="fund-flow-card" v-loading="conceptSlopeLoading">
            <template #header>
              <div class="fund-flow-card-header">
                <span>概念板块趋势跟踪</span>
                <span class="fund-flow-date">
                  中线斜率
                  <template v-if="conceptSlopeAsof"> · {{ conceptSlopeAsof }}</template>
                  <template v-if="conceptSlopeCount"> · {{ conceptSlopeCount }} 个</template>
                </span>
              </div>
            </template>
            <div
              v-show="!conceptSlopeEmpty && !conceptSlopeError"
              ref="conceptSlopeChartRef"
              class="fund-flow-chart"
            />
            <div v-if="conceptSlopeEmpty" class="fund-flow-empty">
              暂无板块斜率（请先在行情页刷新斜率入库）
            </div>
            <div v-else-if="conceptSlopeError" class="fund-flow-empty fund-flow-error">
              {{ conceptSlopeError }}
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 最近活动 -->
    <div class="recent-activity">
      <el-card>
        <template #header>
          <span>最近活动</span>
        </template>
        
        <el-timeline>
          <el-timeline-item
            v-for="activity in recentActivities"
            :key="activity.id"
            :timestamp="activity.time"
            :type="activity.type"
          >
            {{ activity.content }}
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import boardFundFlowService, {
  BOARD_FUND_FLOW_RANK_PERIODS,
  type BoardFundFlowRankPeriod,
  type BoardFundFlowTodayItem
} from '@/services/boardFundFlow.service'
import boardSectorTrendService, {
  type BoardSectorTrendItem
} from '@/services/boardSectorTrend.service'
import stockFundFlowRankService, {
  STOCK_FUND_FLOW_RANK_PERIODS,
  type StockFundFlowRankItem,
  type StockFundFlowRankPeriod
} from '@/services/stockFundFlowRank.service'

const recentActivities = ref<{
  id: number
  content: string
  time: string
  type: 'success' | 'primary' | 'warning' | 'info' | 'danger'
}[]>([
  {
    id: 1,
    content: '系统启动完成',
    time: '2024-01-01 08:00:00',
    type: 'success'
  },
  {
    id: 2,
    content: '数据采集任务开始',
    time: '2024-01-01 08:30:00',
    type: 'primary'
  },
  {
    id: 3,
    content: '用户登录：admin',
    time: '2024-01-01 09:00:00',
    type: 'info'
  },
  {
    id: 4,
    content: '系统备份完成',
    time: '2024-01-01 10:00:00',
    type: 'success'
  }
])

const industryChartRef = ref<HTMLDivElement | null>(null)
const conceptChartRef = ref<HTMLDivElement | null>(null)
const industrySlopeChartRef = ref<HTMLDivElement | null>(null)
const conceptSlopeChartRef = ref<HTMLDivElement | null>(null)
const stockFlowChartRef = ref<HTMLDivElement | null>(null)
let industryChart: echarts.ECharts | null = null
let conceptChart: echarts.ECharts | null = null
let industrySlopeChart: echarts.ECharts | null = null
let conceptSlopeChart: echarts.ECharts | null = null
let stockFlowChart: echarts.ECharts | null = null

const industryLoading = ref(false)
const conceptLoading = ref(false)
const industryEmpty = ref(false)
const conceptEmpty = ref(false)
const industryError = ref('')
const conceptError = ref('')
const industryCount = ref(0)
const conceptCount = ref(0)

const boardFlowPeriods = BOARD_FUND_FLOW_RANK_PERIODS
const boardFlowPeriod = ref<BoardFundFlowRankPeriod>('day')
const boardFlowPeriodLabel = ref('日')
const boardFlowRangeText = ref('')

const industrySlopeLoading = ref(false)
const conceptSlopeLoading = ref(false)
const industrySlopeEmpty = ref(false)
const conceptSlopeEmpty = ref(false)
const industrySlopeError = ref('')
const conceptSlopeError = ref('')
const industrySlopeAsof = ref('')
const conceptSlopeAsof = ref('')
const industrySlopeCount = ref(0)
const conceptSlopeCount = ref(0)

const stockFlowPeriods = STOCK_FUND_FLOW_RANK_PERIODS
const stockFlowPeriod = ref<StockFundFlowRankPeriod>('day')
const stockFlowLoading = ref(false)
const stockFlowEmpty = ref(false)
const stockFlowError = ref('')
const stockFlowCount = ref(0)
const stockFlowPeriodLabel = ref('日')
const stockFlowRangeText = ref('')

function sortAllByNetInflow(items: BoardFundFlowTodayItem[]) {
  return [...items]
    .filter((x) => x.main_net_inflow != null)
    .sort((a, b) => Number(a.main_net_inflow) - Number(b.main_net_inflow))
}

function buildChartOption(
  rows: BoardFundFlowTodayItem[],
  titleHint: string,
  periodLabel: string
) {
  const names = rows.map((r) => String(r.board_name || r.board_code || '--'))
  const values = rows.map((r) => {
    const yuan = Number(r.main_net_inflow) || 0
    return Math.round((yuan / 1e8) * 100) / 100
  })
  const useZoom = rows.length > 20
  // dataZoom 初始窗口：优先露出净流入最强的一段（数组末尾 = 图顶部）
  const windowSize = 20
  const startPct = useZoom
    ? Math.max(0, ((rows.length - windowSize) / rows.length) * 100)
    : 0
  return {
    title: {
      show: false,
      text: titleHint
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params]
        const p = list[0] as { name?: string; value?: number }
        const v = Number(p?.value)
        const sign = v > 0 ? '+' : ''
        return `${p?.name || ''}<br/>${periodLabel}净流入：${sign}${v.toFixed(2)} 亿`
      }
    },
    grid: {
      left: 96,
      right: useZoom ? 36 : 28,
      top: 12,
      bottom: 28
    },
    dataZoom: useZoom
      ? [
          {
            type: 'slider',
            yAxisIndex: 0,
            width: 14,
            right: 4,
            start: startPct,
            end: 100,
            brushSelect: false
          },
          {
            type: 'inside',
            yAxisIndex: 0,
            start: startPct,
            end: 100
          }
        ]
      : [],
    xAxis: {
      type: 'value',
      name: `${periodLabel}净流入(亿)`,
      nameLocation: 'middle',
      nameGap: 22,
      axisLabel: { fontSize: 11 },
      splitLine: { lineStyle: { type: 'dashed', color: '#e5e7eb' } }
    },
    yAxis: {
      type: 'category',
      data: names,
      axisLabel: {
        fontSize: 11,
        width: 88,
        overflow: 'truncate'
      }
    },
    series: [
      {
        type: 'bar',
        data: values.map((v) => ({
          value: v,
          itemStyle: {
            color: v >= 0 ? '#dc2626' : '#16a34a',
            borderRadius: v >= 0 ? [0, 3, 3, 0] : [3, 0, 0, 3]
          }
        })),
        barMaxWidth: 14
      }
    ]
  }
}

function ensureChart(el: HTMLDivElement | null, existing: echarts.ECharts | null) {
  if (!el) return existing
  if (existing) return existing
  return echarts.init(el)
}

function renderFundFlowChart(
  kind: 'industry' | 'concept',
  items: BoardFundFlowTodayItem[]
) {
  const rows = sortAllByNetInflow(items)
  const label = boardFlowPeriodLabel.value || '日'
  if (kind === 'industry') {
    industryChart = ensureChart(industryChartRef.value, industryChart)
    industryChart?.setOption(buildChartOption(rows, '行业', label), true)
    industryChart?.resize()
  } else {
    conceptChart = ensureChart(conceptChartRef.value, conceptChart)
    conceptChart?.setOption(buildChartOption(rows, '概念', label), true)
    conceptChart?.resize()
  }
}

function formatBoardFlowRange(start: string | null | undefined, end: string | null | undefined) {
  if (start && end && start !== end) return `${start} ~ ${end}`
  return end || start || ''
}

async function loadKind(kind: 'industry' | 'concept') {
  const isIndustry = kind === 'industry'
  if (isIndustry) {
    industryLoading.value = true
    industryError.value = ''
    industryEmpty.value = false
  } else {
    conceptLoading.value = true
    conceptError.value = ''
    conceptEmpty.value = false
  }
  try {
    const resp = await boardFundFlowService.getRank({
      board_kind: kind,
      period: boardFlowPeriod.value
    })
    if (!resp.success) {
      throw new Error(resp.message || '加载失败')
    }
    const items = resp.data?.items || []
    boardFlowPeriodLabel.value = resp.data?.period_label || '日'
    const range = formatBoardFlowRange(resp.data?.start_date, resp.data?.end_date)
    if (range) boardFlowRangeText.value = range
    if (isIndustry) {
      industryCount.value = items.length
    } else {
      conceptCount.value = items.length
    }

    if (!items.length) {
      if (isIndustry) industryEmpty.value = true
      else conceptEmpty.value = true
      return
    }
    await nextTick()
    renderFundFlowChart(kind, items)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '加载失败'
    if (isIndustry) industryError.value = msg
    else conceptError.value = msg
  } finally {
    if (isIndustry) industryLoading.value = false
    else conceptLoading.value = false
  }
}

function onBoardFlowPeriodChange() {
  void loadKind('industry')
  void loadKind('concept')
}

function sortAllBySectorSlope(items: BoardSectorTrendItem[]) {
  return [...items]
    .filter((x) => x.sector_slope != null && Number.isFinite(Number(x.sector_slope)))
    .sort((a, b) => Number(a.sector_slope) - Number(b.sector_slope))
}

function pickAsofDate(rows: BoardSectorTrendItem[]) {
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    const d = rows[i]?.slope_asof_date
    if (d) return String(d)
  }
  return ''
}

function formatSlope(v: number) {
  if (!Number.isFinite(v)) return '--'
  const abs = Math.abs(v)
  const digits = abs >= 0.01 ? 4 : abs >= 0.001 ? 5 : 6
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(digits)}`
}

function buildSlopeChartOption(rows: BoardSectorTrendItem[], titleHint: string) {
  const names = rows.map((r) => String(r.board_name || r.board_code || '--'))
  const values = rows.map((r) => Number(r.sector_slope))
  const meta = rows.map((r) => ({
    source: r.slope_source || '--',
    r2: r.slope_r2,
    env: r.board_env_label || r.board_env || '--',
    window: r.sector_slope_window
  }))
  const useZoom = rows.length > 20
  const windowSize = 20
  const startPct = useZoom
    ? Math.max(0, ((rows.length - windowSize) / rows.length) * 100)
    : 0
  return {
    title: {
      show: false,
      text: titleHint
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params]
        const p = list[0] as { name?: string; value?: number; dataIndex?: number }
        const idx = Number(p?.dataIndex)
        const m = Number.isFinite(idx) ? meta[idx] : undefined
        const v = Number(p?.value)
        const r2Text =
          m?.r2 != null && Number.isFinite(Number(m.r2))
            ? Number(m.r2).toFixed(3)
            : '--'
        const win = m?.window != null ? `${m.window}日` : '中线'
        return [
          `${p?.name || ''}`,
          `斜率(${win})：${formatSlope(v)}`,
          `R²：${r2Text}`,
          `来源：${m?.source || '--'}`,
          `环境：${m?.env || '--'}`
        ].join('<br/>')
      }
    },
    grid: {
      left: 96,
      right: useZoom ? 36 : 28,
      top: 12,
      bottom: 28
    },
    dataZoom: useZoom
      ? [
          {
            type: 'slider',
            yAxisIndex: 0,
            width: 14,
            right: 4,
            start: startPct,
            end: 100,
            brushSelect: false
          },
          {
            type: 'inside',
            yAxisIndex: 0,
            start: startPct,
            end: 100
          }
        ]
      : [],
    xAxis: {
      type: 'value',
      name: '中线斜率',
      nameLocation: 'middle',
      nameGap: 22,
      axisLabel: { fontSize: 11 },
      splitLine: { lineStyle: { type: 'dashed', color: '#e5e7eb' } }
    },
    yAxis: {
      type: 'category',
      data: names,
      axisLabel: {
        fontSize: 11,
        width: 88,
        overflow: 'truncate'
      }
    },
    series: [
      {
        type: 'bar',
        data: values.map((v) => ({
          value: v,
          itemStyle: {
            color: v >= 0 ? '#dc2626' : '#16a34a',
            borderRadius: v >= 0 ? [0, 3, 3, 0] : [3, 0, 0, 3]
          }
        })),
        barMaxWidth: 14
      }
    ]
  }
}

function renderSlopeChart(kind: 'industry' | 'concept', items: BoardSectorTrendItem[]) {
  const rows = sortAllBySectorSlope(items)
  if (kind === 'industry') {
    industrySlopeChart = ensureChart(industrySlopeChartRef.value, industrySlopeChart)
    industrySlopeChart?.setOption(buildSlopeChartOption(rows, '行业趋势'), true)
    industrySlopeChart?.resize()
  } else {
    conceptSlopeChart = ensureChart(conceptSlopeChartRef.value, conceptSlopeChart)
    conceptSlopeChart?.setOption(buildSlopeChartOption(rows, '概念趋势'), true)
    conceptSlopeChart?.resize()
  }
}

async function loadSlopeKind(kind: 'industry' | 'concept') {
  const isIndustry = kind === 'industry'
  if (isIndustry) {
    industrySlopeLoading.value = true
    industrySlopeError.value = ''
    industrySlopeEmpty.value = false
  } else {
    conceptSlopeLoading.value = true
    conceptSlopeError.value = ''
    conceptSlopeEmpty.value = false
  }
  try {
    const resp = await boardSectorTrendService.getList({ board_kind: kind })
    if (!resp.success) {
      throw new Error(resp.message || '加载失败')
    }
    const items = resp.data || []
    const rows = sortAllBySectorSlope(items)
    const asof = pickAsofDate(rows)
    if (isIndustry) {
      industrySlopeAsof.value = asof
      industrySlopeCount.value = rows.length
    } else {
      conceptSlopeAsof.value = asof
      conceptSlopeCount.value = rows.length
    }

    if (!rows.length) {
      if (isIndustry) industrySlopeEmpty.value = true
      else conceptSlopeEmpty.value = true
      return
    }
    await nextTick()
    renderSlopeChart(kind, items)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '加载失败'
    if (isIndustry) industrySlopeError.value = msg
    else conceptSlopeError.value = msg
  } finally {
    if (isIndustry) industrySlopeLoading.value = false
    else conceptSlopeLoading.value = false
  }
}

function sortStockFlowByNet(items: StockFundFlowRankItem[]) {
  return [...items]
    .filter((x) => x.net_amount != null && Number.isFinite(Number(x.net_amount)))
    .sort((a, b) => Number(a.net_amount) - Number(b.net_amount))
}

function buildStockFlowChartOption(rows: StockFundFlowRankItem[], periodLabel: string) {
  const names = rows.map((r) => {
    const name = String(r.name || '').trim()
    const code = String(r.code || '')
    return name ? `${name}` : code || '--'
  })
  const values = rows.map((r) => {
    const yuan = Number(r.net_amount) || 0
    return Math.round((yuan / 1e8) * 100) / 100
  })
  const meta = rows.map((r) => ({
    code: r.code,
    inflow: r.inflow_amount,
    outflow: r.outflow_amount,
    days: r.days_count
  }))
  const useZoom = rows.length > 20
  const windowSize = 20
  const startPct = useZoom
    ? Math.max(0, ((rows.length - windowSize) / rows.length) * 100)
    : 0
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params]
        const p = list[0] as { name?: string; value?: number; dataIndex?: number }
        const idx = Number(p?.dataIndex)
        const m = Number.isFinite(idx) ? meta[idx] : undefined
        const v = Number(p?.value)
        const sign = v > 0 ? '+' : ''
        const toYi = (yuan: number | null | undefined) => {
          if (yuan == null || !Number.isFinite(Number(yuan))) return '--'
          const yi = Math.round((Number(yuan) / 1e8) * 100) / 100
          const s = yi > 0 ? '+' : ''
          return `${s}${yi.toFixed(2)} 亿`
        }
        return [
          `${p?.name || ''}${m?.code ? `（${m.code}）` : ''}`,
          `${periodLabel}净流入：${sign}${v.toFixed(2)} 亿`,
          `流入：${toYi(m?.inflow)}`,
          `流出：${toYi(m?.outflow)}`,
          m?.days != null ? `覆盖交易日：${m.days}` : ''
        ]
          .filter(Boolean)
          .join('<br/>')
      }
    },
    grid: {
      left: 108,
      right: useZoom ? 36 : 28,
      top: 12,
      bottom: 28
    },
    dataZoom: useZoom
      ? [
          {
            type: 'slider',
            yAxisIndex: 0,
            width: 14,
            right: 4,
            start: startPct,
            end: 100,
            brushSelect: false
          },
          {
            type: 'inside',
            yAxisIndex: 0,
            start: startPct,
            end: 100
          }
        ]
      : [],
    xAxis: {
      type: 'value',
      name: `${periodLabel}净流入(亿)`,
      nameLocation: 'middle',
      nameGap: 22,
      axisLabel: { fontSize: 11 },
      splitLine: { lineStyle: { type: 'dashed', color: '#e5e7eb' } }
    },
    yAxis: {
      type: 'category',
      data: names,
      axisLabel: {
        fontSize: 11,
        width: 96,
        overflow: 'truncate'
      }
    },
    series: [
      {
        type: 'bar',
        data: values.map((v) => ({
          value: v,
          itemStyle: {
            color: v >= 0 ? '#dc2626' : '#16a34a',
            borderRadius: v >= 0 ? [0, 3, 3, 0] : [3, 0, 0, 3]
          }
        })),
        barMaxWidth: 14
      }
    ]
  }
}

function renderStockFlowChart(items: StockFundFlowRankItem[], periodLabel: string) {
  const rows = sortStockFlowByNet(items)
  stockFlowChart = ensureChart(stockFlowChartRef.value, stockFlowChart)
  stockFlowChart?.setOption(buildStockFlowChartOption(rows, periodLabel), true)
  stockFlowChart?.resize()
}

async function loadStockFlowRank() {
  stockFlowLoading.value = true
  stockFlowError.value = ''
  stockFlowEmpty.value = false
  try {
    const resp = await stockFundFlowRankService.getRank({
      period: stockFlowPeriod.value,
      sides: 40
    })
    if (!resp.success) {
      throw new Error(resp.message || '加载失败')
    }
    const data = resp.data
    const items = data?.items || []
    stockFlowPeriodLabel.value = data?.period_label || '日'
    if (data?.start_date && data?.end_date && data.start_date !== data.end_date) {
      stockFlowRangeText.value = `${data.start_date} ~ ${data.end_date}`
    } else {
      stockFlowRangeText.value = data?.end_date || data?.start_date || ''
    }
    stockFlowCount.value = items.length

    if (!items.length) {
      stockFlowEmpty.value = true
      stockFlowChart?.clear()
      return
    }
    await nextTick()
    renderStockFlowChart(items, stockFlowPeriodLabel.value)
  } catch (e: unknown) {
    stockFlowError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    stockFlowLoading.value = false
  }
}

function onStockFlowPeriodChange() {
  void loadStockFlowRank()
}

function handleResize() {
  industryChart?.resize()
  conceptChart?.resize()
  industrySlopeChart?.resize()
  conceptSlopeChart?.resize()
  stockFlowChart?.resize()
}

onMounted(() => {
  void loadKind('industry')
  void loadKind('concept')
  void loadStockFlowRank()
  void loadSlopeKind('industry')
  void loadSlopeKind('concept')
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  industryChart?.dispose()
  conceptChart?.dispose()
  industrySlopeChart?.dispose()
  conceptSlopeChart?.dispose()
  stockFlowChart?.dispose()
  industryChart = null
  conceptChart = null
  industrySlopeChart = null
  conceptSlopeChart = null
  stockFlowChart = null
})
</script>

<style scoped>
.dashboard-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.fund-flow-charts {
  margin-bottom: 1.5rem;
}

.board-flow-panel {
  min-width: 0;
}

.board-flow-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-weight: 600;
  font-size: 0.875rem;
}

.slope-trend-charts {
  margin-top: 0;
}

.stock-flow-header {
  flex-wrap: wrap;
}

.stock-flow-header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.stock-flow-period {
  margin-left: 0.25rem;
}

.fund-flow-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  font-weight: 600;
}

.fund-flow-date {
  font-size: 0.8125rem;
  font-weight: 400;
  color: rgb(107 114 128);
}

.fund-flow-chart {
  width: 100%;
  height: 480px;
}

.fund-flow-empty {
  height: 480px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(107 114 128);
  font-size: 0.875rem;
  background: #f8fafc;
  border-radius: 4px;
}

.fund-flow-error {
  color: #b91c1c;
  padding: 0 1rem;
  text-align: center;
}

.recent-activity {
  margin-bottom: 1.5rem;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .dashboard-view {
    gap: 1.25rem;
    padding: 20px;
  }
}

@media (max-width: 768px) {
  .dashboard-view {
    gap: 1rem;
    padding: 16px;
  }

  .fund-flow-charts {
    margin-bottom: 1rem;
  }

  .fund-flow-chart,
  .fund-flow-empty {
    height: 300px;
  }

  .fund-flow-card {
    margin-bottom: 16px;
  }

  .board-flow-panel + .board-flow-panel,
  .el-col + .el-col .board-flow-panel {
    margin-top: 0;
  }

  .board-flow-panel {
    margin-bottom: 16px;
  }

  .recent-activity {
    margin-bottom: 1rem;
  }
}

@media (max-width: 640px) {
  .dashboard-view {
    gap: 0.875rem;
    padding: 14px;
  }
}

@media (max-width: 480px) {
  .dashboard-view {
    gap: 0.75rem;
    padding: 12px;
  }

  .recent-activity .el-card {
    margin-bottom: 0.75rem;
  }
}

@media (max-width: 360px) {
  .dashboard-view {
    gap: 0.625rem;
    padding: 10px;
  }
}
</style> 