<template>
  <div class="dashboard-view">
    <!-- <div class="dashboard-header">
      <h1 class="text-2xl font-bold text-gray-900">仪表板</h1>
    </div> -->

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <el-row :gutter="16">
        <el-col :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon users">
                <el-icon><User /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.users || 0 }}</div>
                <div class="stat-label">用户总数</div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon logs">
                <el-icon><Document /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.logs || 0 }}</div>
                <div class="stat-label">日志总数</div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon quotes">
                <el-icon><TrendCharts /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.quotes || 0 }}</div>
                <div class="stat-label">行情数据</div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon system">
                <el-icon><Monitor /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.system || '正常' }}</div>
                <div class="stat-label">系统状态</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 行业 / 概念板块资金流向 -->
    <div class="fund-flow-charts">
      <el-row :gutter="16">
        <el-col :xs="24" :sm="24" :md="12" :lg="12" :xl="12">
          <el-card class="fund-flow-card" v-loading="industryLoading">
            <template #header>
              <div class="fund-flow-card-header">
                <span>行业板块资金流向</span>
                <span class="fund-flow-date">
                  {{ industryTradeDate || '--' }}
                  <template v-if="industryCount"> · {{ industryCount }} 个</template>
                </span>
              </div>
            </template>
            <div
              v-show="!industryEmpty && !industryError"
              ref="industryChartRef"
              class="fund-flow-chart"
            />
            <div v-if="industryEmpty" class="fund-flow-empty">暂无板块资金流（请先日采）</div>
            <div v-else-if="industryError" class="fund-flow-empty fund-flow-error">
              {{ industryError }}
            </div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="24" :md="12" :lg="12" :xl="12">
          <el-card class="fund-flow-card" v-loading="conceptLoading">
            <template #header>
              <div class="fund-flow-card-header">
                <span>概念板块资金流向</span>
                <span class="fund-flow-date">
                  {{ conceptTradeDate || '--' }}
                  <template v-if="conceptCount"> · {{ conceptCount }} 个</template>
                </span>
              </div>
            </template>
            <div
              v-show="!conceptEmpty && !conceptError"
              ref="conceptChartRef"
              class="fund-flow-chart"
            />
            <div v-if="conceptEmpty" class="fund-flow-empty">暂无板块资金流（请先日采）</div>
            <div v-else-if="conceptError" class="fund-flow-empty fund-flow-error">
              {{ conceptError }}
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
import {
  User,
  Document,
  TrendCharts,
  Monitor,
} from '@element-plus/icons-vue'
import boardFundFlowService, {
  type BoardFundFlowTodayItem
} from '@/services/boardFundFlow.service'

const stats = ref({
  users: 0,
  logs: 0,
  quotes: 0,
  system: '正常'
})

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
let industryChart: echarts.ECharts | null = null
let conceptChart: echarts.ECharts | null = null

const industryLoading = ref(false)
const conceptLoading = ref(false)
const industryEmpty = ref(false)
const conceptEmpty = ref(false)
const industryError = ref('')
const conceptError = ref('')
const industryTradeDate = ref('')
const conceptTradeDate = ref('')
const industryCount = ref(0)
const conceptCount = ref(0)

function loadStats() {
  stats.value = {
    users: 1250,
    logs: 45678,
    quotes: 2345,
    system: '正常'
  }
}

function sortAllByNetInflow(items: BoardFundFlowTodayItem[]) {
  return [...items]
    .filter((x) => x.main_net_inflow != null)
    .sort((a, b) => Number(a.main_net_inflow) - Number(b.main_net_inflow))
}

function buildChartOption(rows: BoardFundFlowTodayItem[], titleHint: string) {
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
        return `${p?.name || ''}<br/>净流入：${sign}${v.toFixed(2)} 亿`
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
      name: '净流入(亿)',
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
  if (kind === 'industry') {
    industryChart = ensureChart(industryChartRef.value, industryChart)
    industryChart?.setOption(buildChartOption(rows, '行业'), true)
    industryChart?.resize()
  } else {
    conceptChart = ensureChart(conceptChartRef.value, conceptChart)
    conceptChart?.setOption(buildChartOption(rows, '概念'), true)
    conceptChart?.resize()
  }
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
    const resp = await boardFundFlowService.getToday({ board_kind: kind })
    if (!resp.success) {
      throw new Error(resp.message || '加载失败')
    }
    const items = resp.data?.items || []
    const td = resp.data?.trade_date || ''
    if (isIndustry) {
      industryTradeDate.value = td
      industryCount.value = items.length
    } else {
      conceptTradeDate.value = td
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

function handleResize() {
  industryChart?.resize()
  conceptChart?.resize()
}

onMounted(() => {
  loadStats()
  void loadKind('industry')
  void loadKind('concept')
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  industryChart?.dispose()
  conceptChart?.dispose()
  industryChart = null
  conceptChart = null
})
</script>

<style scoped>
.dashboard-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.dashboard-header {
  margin-bottom: 1.5rem;
}

.stats-grid {
  margin-bottom: 1.5rem;
}

.fund-flow-charts {
  margin-bottom: 1.5rem;
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

.stat-card {
  height: 6rem;
}

.stat-content {
  display: flex;
  align-items: center;
  height: 100%;
}

.stat-icon {
  width: 3rem;
  height: 3rem;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 1rem;
}

.stat-icon.users {
  background-color: rgb(219 234 254);
  color: rgb(37 99 235);
}

.stat-icon.logs {
  background-color: rgb(220 252 231);
  color: rgb(22 163 74);
}

.stat-icon.quotes {
  background-color: rgb(254 249 195);
  color: rgb(202 138 4);
}

.stat-icon.system {
  background-color: rgb(243 232 255);
  color: rgb(147 51 234);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: rgb(17 24 39);
}

.stat-label {
  font-size: 0.875rem;
  color: rgb(107 114 128);
  margin-top: 0.25rem;
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
  
  .stats-grid {
    margin-bottom: 1.25rem;
  }
}

@media (max-width: 768px) {
  .dashboard-view {
    gap: 1rem;
    padding: 16px;
  }
  
  .stats-grid {
    margin-bottom: 1rem;
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
  
  .stat-card {
    height: 5rem;
    margin-bottom: 16px;
  }
  
  .stat-icon {
    width: 2.5rem;
    height: 2.5rem;
    margin-right: 0.75rem;
  }
  
  .stat-value {
    font-size: 1.25rem;
  }
  
  .stat-label {
    font-size: 0.75rem;
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
  
  .stats-grid {
    margin-bottom: 0.875rem;
  }
  
  .stat-card {
    height: 4.75rem;
  }
  
  .stat-icon {
    width: 2.25rem;
    height: 2.25rem;
    margin-right: 0.625rem;
  }
  
  .stat-value {
    font-size: 1.125rem;
  }
  
  .stat-label {
    font-size: 0.7rem;
  }
}

@media (max-width: 480px) {
  .dashboard-view {
    gap: 0.75rem;
    padding: 12px;
  }
  
  .stats-grid {
    margin-bottom: 0.75rem;
  }
  
  .stat-card {
    height: 4.5rem;
  }
  
  .stat-icon {
    width: 2rem;
    height: 2rem;
    margin-right: 0.5rem;
  }
  
  .stat-value {
    font-size: 1rem;
  }
  
  .stat-label {
    font-size: 0.65rem;
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
  
  .stats-grid {
    margin-bottom: 0.625rem;
  }
  
  .stat-card {
    height: 4rem;
  }
  
  .stat-icon {
    width: 1.75rem;
    height: 1.75rem;
    margin-right: 0.375rem;
  }
  
  .stat-value {
    font-size: 0.875rem;
  }
  
  .stat-label {
    font-size: 0.6rem;
  }
}
</style> 