<template>
  <div class="dashboard-view">
    <el-tabs v-model="dashboardTab" class="dashboard-tabs" @tab-change="onDashboardTabChange">
      <el-tab-pane label="资金流向" name="fund-flow">
    <!-- 行业 / 概念板块资金流向（日 / 周 / 月） -->
    <div class="fund-flow-charts">
      <el-card class="fund-flow-card board-flow-card">
        <template #header>
          <div class="ff-card-header">
            <div class="ff-card-title-row">
              <span class="ff-card-title">板块资金流向趋势跟踪</span>
              <span class="fund-flow-date">
                <template v-if="boardFlowView === 'trend'">
                  近 {{ boardTrendDaysText }} 交易日净流入
                </template>
                <template v-else>
                  {{ boardFlowPeriodLabel }}净流入
                </template>
                <template v-if="boardFlowRangeText"> · {{ boardFlowRangeText }}</template>
                <span v-if="boardFlowView === 'rank' || boardFlowView === 'list'" class="board-flow-hint">
                  · 点击图形/列表行查看成分股
                </span>
              </span>
            </div>
            <div class="ff-toolbar">
              <el-radio-group
                v-model="boardFlowPeriod"
                size="small"
                class="stock-flow-period"
                @change="onBoardFlowPeriodChange"
              >
                <el-radio-button
                  v-for="p in boardFlowPeriods"
                  :key="p.value"
                  :value="p.value"
                >
                  {{ p.label }}
                </el-radio-button>
              </el-radio-group>
              <el-radio-group v-model="boardFlowView" size="small" class="ff-view-toggle">
                <el-radio-button value="rank">排行</el-radio-button>
                <el-radio-button value="trend">趋势</el-radio-button>
                <el-radio-button value="structure">结构</el-radio-button>
                <el-radio-button value="list">列表</el-radio-button>
              </el-radio-group>
            </div>
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
                v-show="boardChartVisible && !industryEmpty && !industryError"
                ref="industryChartRef"
                class="fund-flow-chart"
                :class="{ 'fund-flow-chart--clickable': boardFlowView === 'rank' }"
              />
              <el-table
                v-if="boardFlowView === 'list' && !industryEmpty && !industryError"
                :data="industryTableRows"
                size="small"
                stripe
                max-height="480"
                class="ff-rank-table"
                @row-click="onBoardFlowRowClick"
              >
                <el-table-column type="index" label="排名" width="58" />
                <el-table-column prop="board_code" label="代码" width="100" />
                <el-table-column prop="board_name" label="名称" min-width="110" />
                <el-table-column label="净流入(亿)" width="110" align="right">
                  <template #default="{ row }">
                    <span :class="netClass(row.main_net_inflow)">{{ formatYi(row.main_net_inflow) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="涨跌幅%" width="90" align="right">
                  <template #default="{ row }">
                    <span :class="netClass(row.change_percent)">{{ formatPct(row.change_percent) }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="days_count" label="覆盖日" width="80" align="right" />
              </el-table>
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
                v-show="boardChartVisible && !conceptEmpty && !conceptError"
                ref="conceptChartRef"
                class="fund-flow-chart"
                :class="{ 'fund-flow-chart--clickable': boardFlowView === 'rank' }"
              />
              <el-table
                v-if="boardFlowView === 'list' && !conceptEmpty && !conceptError"
                :data="conceptTableRows"
                size="small"
                stripe
                max-height="480"
                class="ff-rank-table"
                @row-click="onBoardFlowRowClick"
              >
                <el-table-column type="index" label="排名" width="58" />
                <el-table-column prop="board_code" label="代码" width="100" />
                <el-table-column prop="board_name" label="名称" min-width="110" />
                <el-table-column label="净流入(亿)" width="110" align="right">
                  <template #default="{ row }">
                    <span :class="netClass(row.main_net_inflow)">{{ formatYi(row.main_net_inflow) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="涨跌幅%" width="90" align="right">
                  <template #default="{ row }">
                    <span :class="netClass(row.change_percent)">{{ formatPct(row.change_percent) }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="days_count" label="覆盖日" width="80" align="right" />
              </el-table>
              <div v-if="conceptEmpty" class="fund-flow-empty">暂无板块资金流（请先日采）</div>
              <div v-else-if="conceptError" class="fund-flow-empty fund-flow-error">
                {{ conceptError }}
              </div>
            </div>
          </el-col>
        </el-row>
      </el-card>
    </div>

    <el-dialog
      v-model="constituentsVisible"
      :title="constituentsTitle"
      width="920px"
      destroy-on-close
      class="board-constituents-dialog"
      @closed="onConstituentsDialogClosed"
    >
      <div class="constituents-meta" v-if="constituentsMetaText">{{ constituentsMetaText }}</div>
      <div v-loading="constituentsLoading">
        <div
          v-show="!constituentsEmpty && !constituentsError"
          ref="constituentsChartRef"
          class="constituents-chart"
        />
        <div v-if="constituentsEmpty" class="constituents-empty">
          {{ constituentsEmptyMsg || '暂无成分股资金流' }}
        </div>
        <div v-else-if="constituentsError" class="constituents-empty fund-flow-error">
          {{ constituentsError }}
        </div>
        <el-table
          v-if="!constituentsEmpty && !constituentsError && constituentsRows.length"
          :data="constituentsTableRows"
          size="small"
          max-height="320"
          stripe
          class="constituents-table"
        >
          <el-table-column type="index" label="排名" width="60" />
          <el-table-column prop="code" label="代码" width="90" />
          <el-table-column prop="name" label="名称" min-width="100" />
          <el-table-column label="净流入(亿)" width="110" align="right">
            <template #default="{ row }">
              <span :class="netClass(row.net_amount)">{{ formatYi(row.net_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="流入(亿)" width="100" align="right">
            <template #default="{ row }">{{ formatYi(row.inflow_amount) }}</template>
          </el-table-column>
          <el-table-column label="流出(亿)" width="100" align="right">
            <template #default="{ row }">{{ formatYi(row.outflow_amount) }}</template>
          </el-table-column>
          <el-table-column label="涨跌幅%" width="90" align="right">
            <template #default="{ row }">
              <span :class="netClass(row.change_percent)">{{ formatPct(row.change_percent) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="days_count" label="覆盖交易日" width="100" align="right" />
        </el-table>
      </div>
    </el-dialog>

    <!-- 个股资金流向趋势跟踪（日 / 周 / 月） -->
    <div class="fund-flow-charts stock-fund-flow-charts">
      <el-card class="fund-flow-card" v-loading="stockFlowLoading">
        <template #header>
          <div class="ff-card-header">
            <div class="ff-card-title-row">
              <span class="ff-card-title">个股资金流向趋势跟踪</span>
              <span class="fund-flow-date">
                <template v-if="stockFlowView === 'trend'">
                  近 {{ stockTrendDaysText }} 交易日净流入
                </template>
                <template v-else>
                  {{ stockFlowPeriodLabel }}净流入
                </template>
                <template v-if="stockFlowRangeText"> · {{ stockFlowRangeText }}</template>
                <template v-if="stockFlowCount && stockFlowView !== 'trend'"> · {{ stockFlowCount }} 只</template>
              </span>
            </div>
            <div class="ff-toolbar">
              <el-radio-group
                v-model="stockFlowPeriod"
                size="small"
                class="stock-flow-period"
                @change="onStockFlowPeriodChange"
              >
                <el-radio-button
                  v-for="p in stockFlowPeriods"
                  :key="p.value"
                  :value="p.value"
                >
                  {{ p.label }}
                </el-radio-button>
              </el-radio-group>
              <el-radio-group v-model="stockFlowView" size="small" class="ff-view-toggle">
                <el-radio-button value="rank">排行</el-radio-button>
                <el-radio-button value="trend">趋势</el-radio-button>
                <el-radio-button value="structure">结构</el-radio-button>
                <el-radio-button value="list">列表</el-radio-button>
              </el-radio-group>
            </div>
          </div>
        </template>
        <div
          v-show="stockChartVisible && !stockFlowEmpty && !stockFlowError"
          ref="stockFlowChartRef"
          class="fund-flow-chart"
        />
        <el-table
          v-if="stockFlowView === 'list' && !stockFlowEmpty && !stockFlowError"
          :data="stockFlowTableRows"
          size="small"
          stripe
          max-height="480"
          class="ff-rank-table"
        >
          <el-table-column type="index" label="排名" width="58" />
          <el-table-column prop="code" label="代码" width="90" />
          <el-table-column prop="name" label="名称" min-width="110" />
          <el-table-column label="净流入(亿)" width="110" align="right">
            <template #default="{ row }">
              <span :class="netClass(row.net_amount)">{{ formatYi(row.net_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="流入(亿)" width="100" align="right">
            <template #default="{ row }">{{ formatYi(row.inflow_amount) }}</template>
          </el-table-column>
          <el-table-column label="流出(亿)" width="100" align="right">
            <template #default="{ row }">{{ formatYi(row.outflow_amount) }}</template>
          </el-table-column>
          <el-table-column prop="days_count" label="覆盖日" width="80" align="right" />
        </el-table>
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
      <div class="ff-card-header slope-toolbar-bar">
        <span class="ff-card-title">板块斜率趋势跟踪</span>
        <el-radio-group v-model="slopeView" size="small" class="ff-view-toggle">
          <el-radio-button value="chart">图形</el-radio-button>
          <el-radio-button value="list">列表</el-radio-button>
        </el-radio-group>
      </div>
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
              v-show="slopeView === 'chart' && !industrySlopeEmpty && !industrySlopeError"
              ref="industrySlopeChartRef"
              class="fund-flow-chart"
            />
            <el-table
              v-if="slopeView === 'list' && !industrySlopeEmpty && !industrySlopeError"
              :data="industrySlopeTableRows"
              size="small"
              stripe
              max-height="480"
              class="ff-rank-table"
            >
              <el-table-column type="index" label="排名" width="58" />
              <el-table-column prop="board_code" label="代码" width="100" />
              <el-table-column prop="board_name" label="名称" min-width="110" />
              <el-table-column label="中线斜率" width="120" align="right">
                <template #default="{ row }">
                  <span :class="netClass(row.sector_slope)">{{ formatSlope(Number(row.sector_slope)) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="环境" min-width="90">
                <template #default="{ row }">{{ row.board_env_label || row.board_env || '—' }}</template>
              </el-table-column>
            </el-table>
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
              v-show="slopeView === 'chart' && !conceptSlopeEmpty && !conceptSlopeError"
              ref="conceptSlopeChartRef"
              class="fund-flow-chart"
            />
            <el-table
              v-if="slopeView === 'list' && !conceptSlopeEmpty && !conceptSlopeError"
              :data="conceptSlopeTableRows"
              size="small"
              stripe
              max-height="480"
              class="ff-rank-table"
            >
              <el-table-column type="index" label="排名" width="58" />
              <el-table-column prop="board_code" label="代码" width="100" />
              <el-table-column prop="board_name" label="名称" min-width="110" />
              <el-table-column label="中线斜率" width="120" align="right">
                <template #default="{ row }">
                  <span :class="netClass(row.sector_slope)">{{ formatSlope(Number(row.sector_slope)) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="环境" min-width="90">
                <template #default="{ row }">{{ row.board_env_label || row.board_env || '—' }}</template>
              </el-table-column>
            </el-table>
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
      </el-tab-pane>

      <el-tab-pane label="复盘" name="market-review">
        <el-tabs v-model="reviewSubTab">
          <el-tab-pane label="每日复盘" name="daily">
            <DailyReviewPanel />
          </el-tab-pane>
          <el-tab-pane label="每周复盘" name="weekly" lazy>
            <PeriodReviewPanel period-type="week" />
          </el-tab-pane>
          <el-tab-pane label="每月复盘" name="monthly" lazy>
            <PeriodReviewPanel period-type="month" />
          </el-tab-pane>
        </el-tabs>
      </el-tab-pane>

      <el-tab-pane label="龙虎榜" name="dragon-tiger" lazy>
        <DragonTigerPanel />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import DailyReviewPanel from '@/views/dashboard/DailyReviewPanel.vue'
import PeriodReviewPanel from '@/views/dashboard/PeriodReviewPanel.vue'
import DragonTigerPanel from '@/views/dashboard/DragonTigerPanel.vue'
import boardFundFlowService, {
  BOARD_FUND_FLOW_RANK_PERIODS,
  type BoardConstituentFundFlowItem,
  type BoardFundFlowRankPeriod,
  type BoardFundFlowTodayItem,
  type BoardFundFlowTrendSeriesData
} from '@/services/boardFundFlow.service'
import boardSectorTrendService, {
  type BoardSectorTrendItem
} from '@/services/boardSectorTrend.service'
import stockFundFlowRankService, {
  STOCK_FUND_FLOW_RANK_PERIODS,
  type StockFundFlowRankItem,
  type StockFundFlowRankPeriod,
  type StockFundFlowTrendSeriesData
} from '@/services/stockFundFlowRank.service'

const dashboardTab = ref('fund-flow')
const reviewSubTab = ref('daily')
type FundFlowChartViewMode = 'rank' | 'trend' | 'structure' | 'list'
type SlopeViewMode = 'chart' | 'list'
const boardFlowView = ref<FundFlowChartViewMode>('rank')
const stockFlowView = ref<FundFlowChartViewMode>('rank')
const slopeView = ref<SlopeViewMode>('chart')
const boardChartVisible = computed(
  () =>
    boardFlowView.value === 'rank' ||
    boardFlowView.value === 'trend' ||
    boardFlowView.value === 'structure'
)
const stockChartVisible = computed(
  () =>
    stockFlowView.value === 'rank' ||
    stockFlowView.value === 'trend' ||
    stockFlowView.value === 'structure'
)
const TREND_DAYS_BY_PERIOD: Record<BoardFundFlowRankPeriod, number> = {
  day: 20,
  week: 40,
  month: 60
}
const TOP_LINE_COLORS = ['#2563eb', '#d97706', '#7c3aed', '#0891b2', '#be185d']
const WATERFALL_SIDES = 5

const industryChartRef = ref<HTMLDivElement | null>(null)
const conceptChartRef = ref<HTMLDivElement | null>(null)
const industrySlopeChartRef = ref<HTMLDivElement | null>(null)
const conceptSlopeChartRef = ref<HTMLDivElement | null>(null)
const stockFlowChartRef = ref<HTMLDivElement | null>(null)
const constituentsChartRef = ref<HTMLDivElement | null>(null)
let industryChart: echarts.ECharts | null = null
let conceptChart: echarts.ECharts | null = null
let industrySlopeChart: echarts.ECharts | null = null
let conceptSlopeChart: echarts.ECharts | null = null
let stockFlowChart: echarts.ECharts | null = null
let constituentsChart: echarts.ECharts | null = null
let industryClickBound = false
let conceptClickBound = false

const industryRows = ref<BoardFundFlowTodayItem[]>([])
const conceptRows = ref<BoardFundFlowTodayItem[]>([])

const constituentsVisible = ref(false)
const constituentsLoading = ref(false)
const constituentsEmpty = ref(false)
const constituentsError = ref('')
const constituentsEmptyMsg = ref('')
const constituentsTitle = ref('板块成分股资金流向')
const constituentsMetaText = ref('')
const constituentsRows = ref<BoardConstituentFundFlowItem[]>([])
const constituentsPeriodLabel = ref('日')

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
const boardTrendDaysText = computed(
  () => String(TREND_DAYS_BY_PERIOD[boardFlowPeriod.value] || 20)
)
const industryTrendCache = ref<BoardFundFlowTrendSeriesData | null>(null)
const conceptTrendCache = ref<BoardFundFlowTrendSeriesData | null>(null)

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
const stockFlowRows = ref<StockFundFlowRankItem[]>([])
const stockTrendCache = ref<StockFundFlowTrendSeriesData | null>(null)
const stockTrendDaysText = computed(
  () => String(TREND_DAYS_BY_PERIOD[stockFlowPeriod.value] || 20)
)
const industrySlopeRows = ref<BoardSectorTrendItem[]>([])
const conceptSlopeRows = ref<BoardSectorTrendItem[]>([])

/** 列表按净流入强→弱（与前台市场分析一致） */
const industryTableRows = computed(() =>
  [...industryRows.value].sort(
    (a, b) => Number(b.main_net_inflow || 0) - Number(a.main_net_inflow || 0)
  )
)
const conceptTableRows = computed(() =>
  [...conceptRows.value].sort(
    (a, b) => Number(b.main_net_inflow || 0) - Number(a.main_net_inflow || 0)
  )
)
const stockFlowTableRows = computed(() =>
  [...stockFlowRows.value].sort(
    (a, b) => Number(b.net_amount || 0) - Number(a.net_amount || 0)
  )
)
const industrySlopeTableRows = computed(() =>
  [...industrySlopeRows.value].sort(
    (a, b) => Number(b.sector_slope || 0) - Number(a.sector_slope || 0)
  )
)
const conceptSlopeTableRows = computed(() =>
  [...conceptSlopeRows.value].sort(
    (a, b) => Number(b.sector_slope || 0) - Number(a.sector_slope || 0)
  )
)

function sortAllByNetInflow(items: BoardFundFlowTodayItem[]) {
  return [...items]
    .filter((x) => x.main_net_inflow != null)
    .sort((a, b) => Number(a.main_net_inflow) - Number(b.main_net_inflow))
}

function yuanToYi(yuan: number | null | undefined): number | null {
  if (yuan == null || !Number.isFinite(Number(yuan))) return null
  return Math.round((Number(yuan) / 1e8) * 100) / 100
}

function formatYiSigned(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(Number(v))) return '--'
  const n = Number(v)
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(2)} 亿`
}

function buildChartOption(
  rows: BoardFundFlowTodayItem[],
  titleHint: string,
  periodLabel: string
) {
  const names = rows.map((r) => String(r.board_name || r.board_code || '--'))
  const values = rows.map((r) => yuanToYi(r.main_net_inflow) || 0)
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
        return `${p?.name || ''}<br/>${periodLabel}净流入：${sign}${v.toFixed(2)} 亿<br/><span style="color:#94a3b8">点击查看成分股资金流向</span>`
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
            color: v >= 0 ? '#c23b3b' : '#2f9e6b',
            borderRadius: v >= 0 ? [0, 2, 2, 0] : [2, 0, 0, 2]
          }
        })),
        barMaxWidth: 8
      }
    ]
  }
}

/** 趋势图双 Y 轴：左=TopN，右=合计，避免合计量级压扁标的线 */
function buildFundTrendOption(opts: {
  dates: string[]
  aggregateYi: Array<number | null>
  topSeries: Array<{ name: string; values: Array<number | null> }>
  aggName: string
}) {
  const { dates, aggregateYi, topSeries, aggName } = opts
  const muted = '#6b7280'
  const split = '#e5e7eb'
  const aggColor = '#4b5563'
  const series: echarts.SeriesOption[] = []
  topSeries.forEach((ent, idx) => {
    const color = TOP_LINE_COLORS[idx % TOP_LINE_COLORS.length]
    const base: echarts.SeriesOption = {
      name: ent.name,
      type: 'line',
      yAxisIndex: 0,
      data: ent.values,
      smooth: 0.25,
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 2.2, color },
      itemStyle: { color },
      emphasis: { focus: 'series', lineStyle: { width: 3 } },
      z: 3
    }
    if (idx === 0) {
      ;(base as { markLine?: unknown }).markLine = {
        silent: true,
        symbol: 'none',
        label: { show: false },
        data: [
          {
            yAxis: 0,
            lineStyle: { color: 'rgba(55,65,81,0.35)', width: 1, type: 'solid' }
          }
        ]
      }
    }
    series.push(base)
  })
  series.push({
    name: aggName,
    type: 'line',
    yAxisIndex: 1,
    data: aggregateYi,
    smooth: 0.2,
    showSymbol: false,
    connectNulls: false,
    lineStyle: { width: 1.6, color: aggColor, type: 'dashed' },
    itemStyle: { color: aggColor },
    areaStyle: {
      color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: 'rgba(75,85,99,0.12)' },
        { offset: 1, color: 'rgba(75,85,99,0.01)' }
      ])
    },
    emphasis: { focus: 'series' },
    z: 1
  })
  return {
    backgroundColor: 'transparent',
    color: TOP_LINE_COLORS,
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        crossStyle: { color: muted },
        lineStyle: { color: muted, type: 'dashed' }
      },
      formatter: (params: unknown) => {
        const list = (Array.isArray(params) ? params : [params]) as Array<{
          seriesName?: string
          value?: number | null
          axisValueLabel?: string
          marker?: string
        }>
        const head = list[0]?.axisValueLabel || ''
        const lines = list.map((p) => {
          const axisHint = p.seriesName === aggName ? '（右轴）' : ''
          return `${p.marker || ''}${p.seriesName || ''}${axisHint}：${formatYiSigned(
            p.value == null ? null : Number(p.value)
          )}`
        })
        return [head, ...lines].join('<br/>')
      }
    },
    legend: {
      type: 'scroll',
      top: 4,
      left: 8,
      right: 8,
      itemWidth: 14,
      itemHeight: 8,
      itemGap: 12,
      textStyle: { fontSize: 12, color: '#374151' }
    },
    grid: { left: 56, right: 58, top: 44, bottom: 32 },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: split } },
      axisTick: { show: false },
      axisLabel: {
        fontSize: 10,
        color: muted,
        hideOverlap: true,
        formatter: (v: string) => (v && v.length >= 10 ? v.slice(5) : v)
      }
    },
    yAxis: [
      {
        type: 'value',
        name: '标的(亿)',
        nameGap: 8,
        nameTextStyle: { fontSize: 11, color: muted },
        axisLabel: { fontSize: 11, color: muted },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { type: 'dashed', color: split } },
        scale: true
      },
      {
        type: 'value',
        name: '合计(亿)',
        nameGap: 8,
        nameTextStyle: { fontSize: 11, color: muted },
        axisLabel: { fontSize: 11, color: muted },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false },
        scale: true
      }
    ],
    series
  }
}

function buildBoardTrendOption(data: BoardFundFlowTrendSeriesData) {
  return buildFundTrendOption({
    dates: data.dates || [],
    aggregateYi: (data.aggregate?.main_net_inflow || []).map((v) => yuanToYi(v)),
    topSeries: (data.top_entities || []).map((ent, idx) => ({
      name: String(ent.board_name || ent.board_code || `Top${idx + 1}`),
      values: (ent.main_net_inflow || []).map((v) => yuanToYi(v))
    })),
    aggName: '全板合计'
  })
}

function buildWaterfallOption(
  steps: Array<{ name: string; valueYi: number }>,
  periodLabel: string
) {
  const names = steps.map((s) => s.name)
  const helpers: number[] = []
  const display: Array<{
    value: number
    itemStyle: { color: string; borderRadius: number[] }
  }> = []
  let running = 0
  steps.forEach((step, idx) => {
    const v = step.valueYi
    const isTotal = idx === steps.length - 1
    if (isTotal) {
      helpers.push(v >= 0 ? 0 : v)
      display.push({
        value: Math.abs(v),
        itemStyle: { color: '#374151', borderRadius: [3, 3, 3, 3] }
      })
      return
    }
    if (v >= 0) {
      helpers.push(running)
      display.push({
        value: v,
        itemStyle: { color: '#c23b3b', borderRadius: [3, 3, 0, 0] }
      })
      running += v
    } else {
      helpers.push(running + v)
      display.push({
        value: Math.abs(v),
        itemStyle: { color: '#2f9e6b', borderRadius: [0, 0, 3, 3] }
      })
      running += v
    }
  })
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params]
        const p = list.find(
          (x) => (x as { seriesName?: string }).seriesName === '变动'
        ) as { dataIndex?: number } | undefined
        const idx = Number(p?.dataIndex)
        const step = Number.isFinite(idx) ? steps[idx] : undefined
        if (!step) return ''
        return `${step.name}<br/>${periodLabel}：${formatYiSigned(step.valueYi)}`
      }
    },
    grid: { left: 48, right: 20, top: 16, bottom: 64 },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: {
        fontSize: 10,
        interval: 0,
        rotate: names.length > 6 ? 28 : 0,
        width: 72,
        overflow: 'truncate'
      }
    },
    yAxis: {
      type: 'value',
      name: '净流入(亿)',
      axisLabel: { fontSize: 11 },
      splitLine: { lineStyle: { type: 'dashed', color: '#e5e7eb' } }
    },
    series: [
      {
        name: '辅助',
        type: 'bar',
        stack: 'wf',
        data: helpers,
        itemStyle: { borderColor: 'transparent', color: 'transparent' },
        emphasis: { itemStyle: { borderColor: 'transparent', color: 'transparent' } },
        barMaxWidth: 28
      },
      {
        name: '变动',
        type: 'bar',
        stack: 'wf',
        data: display,
        barMaxWidth: 28,
        label: {
          show: true,
          position: 'top',
          fontSize: 10,
          formatter: (p: { dataIndex?: number }) => {
            const idx = Number(p?.dataIndex)
            const step = Number.isFinite(idx) ? steps[idx] : undefined
            if (!step) return ''
            return formatYiSigned(step.valueYi).replace(' 亿', '')
          }
        }
      }
    ]
  }
}

function buildBoardStructureSteps(
  rows: BoardFundFlowTodayItem[],
  sides = WATERFALL_SIDES
): Array<{ name: string; valueYi: number }> {
  const sorted = [...rows]
    .filter((x) => x.main_net_inflow != null && Number.isFinite(Number(x.main_net_inflow)))
    .sort((a, b) => Number(b.main_net_inflow) - Number(a.main_net_inflow))
  const inflows = sorted.filter((x) => Number(x.main_net_inflow) > 0).slice(0, sides)
  const outflows = sorted
    .filter((x) => Number(x.main_net_inflow) < 0)
    .slice(-sides)
    .reverse()
  const steps: Array<{ name: string; valueYi: number }> = []
  inflows.forEach((r) => {
    steps.push({
      name: String(r.board_name || r.board_code || '--'),
      valueYi: yuanToYi(r.main_net_inflow) || 0
    })
  })
  outflows.forEach((r) => {
    steps.push({
      name: String(r.board_name || r.board_code || '--'),
      valueYi: yuanToYi(r.main_net_inflow) || 0
    })
  })
  const total = steps.reduce((s, x) => s + x.valueYi, 0)
  steps.push({ name: '结构净额', valueYi: Math.round(total * 100) / 100 })
  return steps
}

function ensureChart(el: HTMLDivElement | null, existing: echarts.ECharts | null) {
  if (!el) return existing
  if (existing) return existing
  return echarts.init(el)
}

function bindBoardChartClick(kind: 'industry' | 'concept', chart: echarts.ECharts | null) {
  if (!chart) return
  if (kind === 'industry') {
    if (industryClickBound) return
    industryClickBound = true
  } else {
    if (conceptClickBound) return
    conceptClickBound = true
  }
  chart.on('click', (params: { dataIndex?: number }) => {
    const rows = kind === 'industry' ? industryRows.value : conceptRows.value
    const idx = Number(params?.dataIndex)
    const row = Number.isFinite(idx) ? rows[idx] : undefined
    if (row?.board_code) {
      void openBoardConstituents(kind, row.board_code, row.board_name || '')
    }
  })
}

function paintBoardChart(kind: 'industry' | 'concept') {
  const label = boardFlowPeriodLabel.value || '日'
  const rows = kind === 'industry' ? industryRows.value : conceptRows.value
  const mode = boardFlowView.value
  if (kind === 'industry') {
    industryChart = ensureChart(industryChartRef.value, industryChart)
  } else {
    conceptChart = ensureChart(conceptChartRef.value, conceptChart)
  }
  const chart = kind === 'industry' ? industryChart : conceptChart
  if (!chart) return

  if (mode === 'trend') {
    const trend =
      kind === 'industry' ? industryTrendCache.value : conceptTrendCache.value
    if (!trend || !trend.dates?.length) {
      chart.clear()
      return
    }
    chart.setOption(buildBoardTrendOption(trend), true)
    chart.resize()
    return
  }

  if (mode === 'structure') {
    if (kind === 'industry') industryCount.value = rows.length
    else conceptCount.value = rows.length
    const steps = buildBoardStructureSteps(rows)
    if (steps.length <= 1) {
      chart.clear()
      return
    }
    chart.setOption(buildWaterfallOption(steps, label), true)
    chart.resize()
    return
  }

  // rank（默认）
  if (kind === 'industry') industryCount.value = rows.length
  else conceptCount.value = rows.length
  chart.setOption(buildChartOption(rows, kind === 'industry' ? '行业' : '概念', label), true)
  chart.resize()
  bindBoardChartClick(kind, chart)
}

function renderFundFlowChart(
  kind: 'industry' | 'concept',
  items: BoardFundFlowTodayItem[]
) {
  const rows = sortAllByNetInflow(items)
  if (kind === 'industry') industryRows.value = rows
  else conceptRows.value = rows
  paintBoardChart(kind)
}

async function loadBoardTrend(kind: 'industry' | 'concept') {
  const isIndustry = kind === 'industry'
  if (isIndustry) {
    industryLoading.value = true
    industryError.value = ''
  } else {
    conceptLoading.value = true
    conceptError.value = ''
  }
  try {
    const resp = await boardFundFlowService.getTrendSeries({
      board_kind: kind,
      period: boardFlowPeriod.value,
      top_n: 5
    })
    if (!resp.success) throw new Error(resp.message || '加载趋势失败')
    const data = resp.data
    if (!data?.dates?.length) {
      if (isIndustry) {
        industryEmpty.value = true
        industryTrendCache.value = null
      } else {
        conceptEmpty.value = true
        conceptTrendCache.value = null
      }
      return
    }
    if (isIndustry) {
      industryEmpty.value = false
      industryTrendCache.value = data
      industryCount.value = data.top_entities?.length || 0
    } else {
      conceptEmpty.value = false
      conceptTrendCache.value = data
      conceptCount.value = data.top_entities?.length || 0
    }
    boardFlowPeriodLabel.value = data.period_label || boardFlowPeriodLabel.value
    const range = formatBoardFlowRange(data.start_date, data.end_date)
    if (range) boardFlowRangeText.value = range
    await nextTick()
    paintBoardChart(kind)
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '加载趋势失败'
    if (isIndustry) industryError.value = msg
    else conceptError.value = msg
  } finally {
    if (isIndustry) industryLoading.value = false
    else conceptLoading.value = false
  }
}

function formatYi(yuan: number | null | undefined) {
  if (yuan == null || !Number.isFinite(Number(yuan))) return '--'
  const yi = Math.round((Number(yuan) / 1e8) * 100) / 100
  const sign = yi > 0 ? '+' : ''
  return `${sign}${yi.toFixed(2)}`
}

function formatPct(v: number | null | undefined) {
  if (v == null || !Number.isFinite(Number(v))) return '--'
  const n = Number(v)
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}`
}

function netClass(v: number | null | undefined) {
  if (v == null || !Number.isFinite(Number(v))) return ''
  if (Number(v) > 0) return 'net-pos'
  if (Number(v) < 0) return 'net-neg'
  return ''
}

const constituentsTableRows = computed(() =>
  [...constituentsRows.value].sort((a, b) => {
    const av = a.net_amount == null ? Number.NEGATIVE_INFINITY : Number(a.net_amount)
    const bv = b.net_amount == null ? Number.NEGATIVE_INFINITY : Number(b.net_amount)
    return bv - av
  })
)

function buildConstituentsChartOption(rows: BoardConstituentFundFlowItem[], periodLabel: string) {
  const list = rows.filter((r) => r.net_amount != null)
  const names = list.map((r) => String(r.name || r.code || '--'))
  const values = list.map((r) => Math.round((Number(r.net_amount) / 1e8) * 100) / 100)
  const meta = list.map((r) => ({
    code: r.code,
    inflow: r.inflow_amount,
    outflow: r.outflow_amount,
    days: r.days_count
  }))
  const useZoom = list.length > 20
  const windowSize = 20
  const startPct = useZoom
    ? Math.max(0, ((list.length - windowSize) / list.length) * 100)
    : 0
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : [params]
        const p = arr[0] as { name?: string; value?: number; dataIndex?: number }
        const idx = Number(p?.dataIndex)
        const m = Number.isFinite(idx) ? meta[idx] : undefined
        const v = Number(p?.value)
        const sign = v > 0 ? '+' : ''
        return [
          `${p?.name || ''}${m?.code ? `（${m.code}）` : ''}`,
          `${periodLabel}净流入：${sign}${v.toFixed(2)} 亿`,
          `流入：${formatYi(m?.inflow)} 亿`,
          `流出：${formatYi(m?.outflow)} 亿`,
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
          { type: 'inside', yAxisIndex: 0, start: startPct, end: 100 }
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
      axisLabel: { fontSize: 11, width: 96, overflow: 'truncate' }
    },
    series: [
      {
        type: 'bar',
        data: values.map((v) => ({
          value: v,
          itemStyle: {
            color: v >= 0 ? '#c23b3b' : '#2f9e6b',
            borderRadius: v >= 0 ? [0, 3, 3, 0] : [3, 0, 0, 3]
          }
        })),
        barMaxWidth: 14
      }
    ]
  }
}

async function openBoardConstituents(
  kind: 'industry' | 'concept',
  boardCode: string,
  boardName: string
) {
  constituentsVisible.value = true
  constituentsLoading.value = true
  constituentsEmpty.value = false
  constituentsError.value = ''
  constituentsEmptyMsg.value = ''
  constituentsRows.value = []
  constituentsTitle.value = `${boardName || boardCode} · 成分股资金流向`
  constituentsMetaText.value = ''
  try {
    const resp = await boardFundFlowService.getConstituents({
      board_kind: kind,
      board_code: boardCode,
      period: boardFlowPeriod.value
    })
    if (!resp.success) throw new Error(resp.message || '加载失败')
    const data = resp.data
    const items = data?.items || []
    const name = data?.board_name || boardName || boardCode
    constituentsTitle.value = `${name} · 成分股资金流向`
    constituentsPeriodLabel.value = data?.period_label || boardFlowPeriodLabel.value || '日'
    const range = formatBoardFlowRange(data?.start_date, data?.end_date)
    const withFlow = items.filter((x) => x.net_amount != null).length
    const kindLabel = kind === 'concept' ? '概念' : '行业'
    constituentsMetaText.value = [
      kindLabel,
      `${constituentsPeriodLabel.value}净流入`,
      range || null,
      data?.member_count != null ? `成分 ${data.member_count} 只` : null,
      withFlow ? `有资金流 ${withFlow} 只` : null,
      '同花顺'
    ]
      .filter(Boolean)
      .join(' · ')

    if (!items.length) {
      constituentsEmpty.value = true
      constituentsEmptyMsg.value =
        data?.message || '暂无成分股资金流（请先同步成分股并日采同花顺资金流向）'
      return
    }
    constituentsRows.value = [...items].sort(
      (a, b) => Number(b.net_amount || 0) - Number(a.net_amount || 0)
    )
    await nextTick()
    constituentsChart = ensureChart(constituentsChartRef.value, constituentsChart)
    constituentsChart?.setOption(
      buildConstituentsChartOption(constituentsRows.value, constituentsPeriodLabel.value),
      true
    )
    constituentsChart?.resize()
  } catch (e: unknown) {
    constituentsError.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    constituentsLoading.value = false
  }
}

function onBoardFlowRowClick(row: BoardFundFlowTodayItem) {
  if (!row?.board_code) return
  const kind =
    row.board_kind === 'concept' || row.board_kind === 'industry'
      ? row.board_kind
      : String(row.board_code || '').startsWith('88')
        ? 'industry'
        : 'concept'
  void openBoardConstituents(kind, row.board_code, row.board_name || '')
}

function onConstituentsDialogClosed() {
  constituentsChart?.dispose()
  constituentsChart = null
  constituentsRows.value = []
}

function formatBoardFlowRange(start: string | null | undefined, end: string | null | undefined) {
  if (start && end && start !== end) return `${start} ~ ${end}`
  return end || start || ''
}

async function loadKind(kind: 'industry' | 'concept') {
  if (boardFlowView.value === 'trend') {
    await loadBoardTrend(kind)
    return
  }
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
      if (isIndustry) {
        industryEmpty.value = true
        industryRows.value = []
        industryChart?.clear()
      } else {
        conceptEmpty.value = true
        conceptRows.value = []
        conceptChart?.clear()
      }
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
  industryTrendCache.value = null
  conceptTrendCache.value = null
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
            color: v >= 0 ? '#c23b3b' : '#2f9e6b',
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
    industrySlopeRows.value = rows
    industrySlopeChart = ensureChart(industrySlopeChartRef.value, industrySlopeChart)
    industrySlopeChart?.setOption(buildSlopeChartOption(rows, '行业趋势'), true)
    industrySlopeChart?.resize()
  } else {
    conceptSlopeRows.value = rows
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
      if (isIndustry) {
        industrySlopeEmpty.value = true
        industrySlopeRows.value = []
      } else {
        conceptSlopeEmpty.value = true
        conceptSlopeRows.value = []
      }
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
  const values = rows.map((r) => yuanToYi(r.net_amount) || 0)
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
        return [
          `${p?.name || ''}${m?.code ? `（${m.code}）` : ''}`,
          `${periodLabel}净流入：${sign}${v.toFixed(2)} 亿`,
          `流入：${formatYiSigned(yuanToYi(m?.inflow))}`,
          `流出：${formatYiSigned(yuanToYi(m?.outflow))}`,
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
            color: v >= 0 ? '#c23b3b' : '#2f9e6b',
            borderRadius: v >= 0 ? [0, 2, 2, 0] : [2, 0, 0, 2]
          }
        })),
        barMaxWidth: 8
      }
    ]
  }
}

function buildStockTrendOption(data: StockFundFlowTrendSeriesData) {
  return buildFundTrendOption({
    dates: data.dates || [],
    aggregateYi: (data.aggregate?.net_amount || []).map((v) => yuanToYi(v)),
    topSeries: (data.top_entities || []).map((ent, idx) => ({
      name: String(ent.name || ent.code || `Top${idx + 1}`),
      values: (ent.net_amount || []).map((v) => yuanToYi(v))
    })),
    aggName: '全市场合计'
  })
}

function buildStockStructureSteps(
  rows: StockFundFlowRankItem[],
  sides = WATERFALL_SIDES
): Array<{ name: string; valueYi: number }> {
  const sorted = [...rows]
    .filter((x) => x.net_amount != null && Number.isFinite(Number(x.net_amount)))
    .sort((a, b) => Number(b.net_amount) - Number(a.net_amount))
  const inflows = sorted.filter((x) => Number(x.net_amount) > 0).slice(0, sides)
  const outflows = sorted
    .filter((x) => Number(x.net_amount) < 0)
    .slice(-sides)
    .reverse()
  const steps: Array<{ name: string; valueYi: number }> = []
  inflows.forEach((r) => {
    steps.push({
      name: String(r.name || r.code || '--'),
      valueYi: yuanToYi(r.net_amount) || 0
    })
  })
  outflows.forEach((r) => {
    steps.push({
      name: String(r.name || r.code || '--'),
      valueYi: yuanToYi(r.net_amount) || 0
    })
  })
  const total = steps.reduce((s, x) => s + x.valueYi, 0)
  steps.push({ name: '结构净额', valueYi: Math.round(total * 100) / 100 })
  return steps
}

function paintStockChart() {
  const label = stockFlowPeriodLabel.value || '日'
  stockFlowChart = ensureChart(stockFlowChartRef.value, stockFlowChart)
  if (!stockFlowChart) return
  const mode = stockFlowView.value
  if (mode === 'trend') {
    const trend = stockTrendCache.value
    if (!trend?.dates?.length) {
      stockFlowChart.clear()
      return
    }
    stockFlowChart.setOption(buildStockTrendOption(trend), true)
    stockFlowChart.resize()
    return
  }
  if (mode === 'structure') {
    stockFlowCount.value = stockFlowRows.value.length
    const steps = buildStockStructureSteps(stockFlowRows.value)
    if (steps.length <= 1) {
      stockFlowChart.clear()
      return
    }
    stockFlowChart.setOption(buildWaterfallOption(steps, label), true)
    stockFlowChart.resize()
    return
  }
  stockFlowCount.value = stockFlowRows.value.length
  stockFlowChart.setOption(buildStockFlowChartOption(stockFlowRows.value, label), true)
  stockFlowChart.resize()
}

function renderStockFlowChart(items: StockFundFlowRankItem[], _periodLabel: string) {
  stockFlowRows.value = sortStockFlowByNet(items)
  paintStockChart()
}

async function loadStockTrend() {
  stockFlowLoading.value = true
  stockFlowError.value = ''
  stockFlowEmpty.value = false
  try {
    const resp = await stockFundFlowRankService.getTrendSeries({
      period: stockFlowPeriod.value,
      top_n: 5
    })
    if (!resp.success) throw new Error(resp.message || '加载趋势失败')
    const data = resp.data
    if (!data?.dates?.length) {
      stockFlowEmpty.value = true
      stockTrendCache.value = null
      stockFlowChart?.clear()
      return
    }
    stockTrendCache.value = data
    stockFlowPeriodLabel.value = data.period_label || '日'
    stockFlowRangeText.value = formatBoardFlowRange(data.start_date, data.end_date)
    stockFlowCount.value = data.top_entities?.length || 0
    await nextTick()
    paintStockChart()
  } catch (e: unknown) {
    stockFlowError.value = e instanceof Error ? e.message : '加载趋势失败'
    stockTrendCache.value = null
  } finally {
    stockFlowLoading.value = false
  }
}

async function loadStockFlowRank() {
  if (stockFlowView.value === 'trend') {
    await loadStockTrend()
    return
  }
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
    stockFlowRangeText.value = formatBoardFlowRange(data?.start_date, data?.end_date)
    stockFlowCount.value = items.length

    if (!items.length) {
      stockFlowEmpty.value = true
      stockFlowRows.value = []
      stockFlowChart?.clear()
      return
    }
    await nextTick()
    renderStockFlowChart(items, stockFlowPeriodLabel.value)
  } catch (e: unknown) {
    stockFlowError.value = e instanceof Error ? e.message : '加载失败'
    stockFlowRows.value = []
  } finally {
    stockFlowLoading.value = false
  }
}

function onStockFlowPeriodChange() {
  stockTrendCache.value = null
  void loadStockFlowRank()
}

function handleResize() {
  industryChart?.resize()
  conceptChart?.resize()
  industrySlopeChart?.resize()
  conceptSlopeChart?.resize()
  stockFlowChart?.resize()
  constituentsChart?.resize()
}

function onDashboardTabChange(name: string | number) {
  if (String(name) !== 'fund-flow') return
  window.setTimeout(() => {
    handleResize()
  }, 80)
}

watch(boardFlowView, async (mode) => {
  if (mode === 'list') return
  if (mode === 'trend') {
    void loadBoardTrend('industry')
    void loadBoardTrend('concept')
    return
  }
  // 排行/结构共用 period 窗口排名数据；从趋势切回时强制按当前周期重载
  void loadKind('industry')
  void loadKind('concept')
})

watch(stockFlowView, async (mode) => {
  if (mode === 'list') return
  if (mode === 'trend') {
    void loadStockTrend()
    return
  }
  void loadStockFlowRank()
})

watch(slopeView, async (mode) => {
  if (mode !== 'chart') return
  await nextTick()
  industrySlopeChart?.resize()
  conceptSlopeChart?.resize()
})

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
  constituentsChart?.dispose()
  industryChart = null
  conceptChart = null
  industrySlopeChart = null
  conceptSlopeChart = null
  stockFlowChart = null
  constituentsChart = null
})
</script>

<style scoped>
.dashboard-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.dashboard-tabs :deep(.el-tabs__content) {
  overflow: visible;
}

.dashboard-tabs :deep(.el-tab-pane) {
  outline: none;
}

.fund-flow-card :deep(.el-card__header) {
  overflow: visible;
}

.ff-card-header {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.65rem;
  width: 100%;
}

.ff-card-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem 1rem;
}

.ff-card-title {
  font-weight: 600;
  font-size: 0.95rem;
  color: #0f172a;
}

.ff-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.ff-view-toggle {
  margin-left: 0;
}

.ff-rank-table {
  width: 100%;
  cursor: pointer;
}

.slope-toolbar-bar {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
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

.board-flow-hint {
  color: #94a3b8;
}

.fund-flow-chart--clickable {
  cursor: pointer;
}

.constituents-meta {
  margin-bottom: 0.75rem;
  font-size: 0.8125rem;
  color: rgb(107 114 128);
}

.constituents-chart {
  width: 100%;
  height: 280px;
  margin-bottom: 0.75rem;
}

.constituents-empty {
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(107 114 128);
  font-size: 0.875rem;
  background: #f8fafc;
  border-radius: 4px;
  margin-bottom: 0.75rem;
  padding: 0 1rem;
  text-align: center;
}

.constituents-table {
  width: 100%;
}

.net-pos {
  color: #c23b3b;
}

.net-neg {
  color: #2f9e6b;
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
}

@media (max-width: 360px) {
  .dashboard-view {
    gap: 0.625rem;
    padding: 10px;
  }
}
</style> 