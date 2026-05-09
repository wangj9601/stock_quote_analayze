<template>
  <div class="space-y-4">
    <el-card shadow="never">
      <template #header><span class="font-semibold">一阳穿三线 · 参数</span></template>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <div class="text-xs text-gray-500 mb-1">最小涨幅 (%)</div>
          <el-input-number v-model="minIncreasePercent" :min="0" :max="50" :step="0.1" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">最小实体占比</div>
          <el-input-number v-model="minBodyRatio" :min="0.1" :max="1" :step="0.05" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">最少穿越均线数</div>
          <el-input-number v-model="minCrossLines" :min="2" :max="6" :step="1" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">最小成交量倍数</div>
          <el-input-number v-model="minVolumeRatio" :min="0.1" :max="10" :step="0.1" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">换手率下限 (%)</div>
          <el-input-number v-model="minTurnoverRate" :min="0" :max="50" :step="0.5" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">换手率上限 (%)</div>
          <el-input-number v-model="maxTurnoverRate" :min="0" :max="100" :step="0.5" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">检查最近 N 个交易日</div>
          <el-input-number v-model="recentDays" :min="1" :max="10" :step="1" class="w-full" />
        </div>
      </div>
      <div class="mt-4">
        <div class="text-xs text-gray-500 mb-2">均线周期（用于穿越判定）</div>
        <el-checkbox-group v-model="maPeriods">
          <el-checkbox label="5">MA5</el-checkbox>
          <el-checkbox label="10">MA10</el-checkbox>
          <el-checkbox label="20">MA20</el-checkbox>
          <el-checkbox label="30">MA30</el-checkbox>
          <el-checkbox label="60">MA60</el-checkbox>
          <el-checkbox label="120">MA120</el-checkbox>
        </el-checkbox-group>
      </div>
      <div class="mt-3 flex gap-2">
        <el-button size="small" @click="resetDefaults">重置默认</el-button>
      </div>
    </el-card>

    <SimpleStrategyPane
      :bullets="[
        '接口：GET /api/screening/one-yang-three-lines',
        '参数见上方；与网站端选股页一阳穿三线逻辑一致',
      ]"
      :fetch-path="fetchPath"
      :columns="cols"
      export-name="一阳穿三线"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import SimpleStrategyPane, { type SimpleCol } from './SimpleStrategyPane.vue'

const minIncreasePercent = ref(3.0)
const minBodyRatio = ref(0.7)
const minCrossLines = ref(3)
const minVolumeRatio = ref(2.0)
const minTurnoverRate = ref(3.0)
const maxTurnoverRate = ref(10.0)
const recentDays = ref(1)
const maPeriods = ref<string[]>(['5', '10', '20', '30', '60', '120'])

function resetDefaults() {
  minIncreasePercent.value = 3.0
  minBodyRatio.value = 0.7
  minCrossLines.value = 3
  minVolumeRatio.value = 2.0
  minTurnoverRate.value = 3.0
  maxTurnoverRate.value = 10.0
  recentDays.value = 1
  maPeriods.value = ['5', '10', '20', '30', '60', '120']
}

const fetchPath = computed(() => {
  const q = new URLSearchParams({
    min_increase_percent: String(minIncreasePercent.value),
    min_body_ratio: String(minBodyRatio.value),
    min_cross_lines: String(minCrossLines.value),
    min_volume_ratio: String(minVolumeRatio.value),
    min_turnover_rate: String(minTurnoverRate.value),
    max_turnover_rate: String(maxTurnoverRate.value),
    recent_days: String(recentDays.value),
    ma_periods: maPeriods.value.join(','),
  })
  return `one-yang-three-lines?${q.toString()}`
})

const cols: SimpleCol[] = [
  { type: 'code', label: '股票代码', width: 90 },
  { type: 'name', label: '股票名称', width: 100 },
  { type: 'text', prop: 'signal_date', label: '信号日', width: 110 },
  { type: 'price', prop: 'current_price', label: '当前价', width: 88 },
  { type: 'text', prop: 'crossed_lines', label: '穿越均线', minWidth: 120 },
  {
    type: 'custom',
    label: '量比',
    width: 72,
    render: (r) => (r.volume_ratio != null ? Number(r.volume_ratio).toFixed(2) : '—'),
  },
  {
    type: 'custom',
    label: '换手率',
    width: 80,
    render: (r) => (r.turnover_rate != null ? `${Number(r.turnover_rate).toFixed(2)}%` : '—'),
  },
  { type: 'text', prop: 'position_type', label: '位置', width: 72 },
  {
    type: 'custom',
    label: '回撤',
    width: 72,
    render: (r) => (r.retracement != null ? `${Number(r.retracement).toFixed(2)}%` : '—'),
  },
  {
    type: 'custom',
    label: 'BIAS30',
    width: 80,
    render: (r) => (r.bias30 != null ? `${Number(r.bias30).toFixed(2)}%` : '—'),
  },
  { type: 'text', prop: 'signal_score', label: '评分', width: 72 },
  {
    type: 'custom',
    label: '风险提示',
    minWidth: 160,
    render: (r) => {
      const w = r.risk_warnings as unknown
      if (Array.isArray(w)) return w.join('；') || '—'
      return '—'
    },
  },
  { type: 'actions', label: '操作', width: 120 },
]
</script>
