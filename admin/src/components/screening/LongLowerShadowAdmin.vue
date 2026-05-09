<template>
  <div class="space-y-4">
    <el-card shadow="never">
      <template #header><span class="font-semibold">参数</span></template>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <div class="text-xs text-gray-500 mb-1">下影线/实体比下限</div>
          <el-input-number v-model="lowerShadowRatio" :min="0.1" :max="10" :step="0.1" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">上影线/实体比上限</div>
          <el-input-number v-model="upperShadowRatio" :min="0" :max="5" :step="0.05" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">最小振幅（小数，如 0.02；大于 0.5 时按百分比自动换算）</div>
          <el-input-number v-model="minAmplitude" :min="0" :max="100" :step="0.001" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">最近交易日数</div>
          <el-input-number v-model="recentDays" :min="1" :max="30" :step="1" class="w-full" />
        </div>
      </div>
    </el-card>

    <SimpleStrategyPane
      title="长下影线"
      :bullets="[
        '股票范围：全部A股（排除 ST）',
        '调用接口：GET /api/screening/long-lower-shadow-strategy',
        '请先设置上方参数，再点击下方「刷新筛选」',
      ]"
      :fetch-path="fetchPath"
      :columns="cols"
      export-name="长下影线"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import SimpleStrategyPane, { type SimpleCol } from './SimpleStrategyPane.vue'

const lowerShadowRatio = ref(1.0)
const upperShadowRatio = ref(0.3)
const minAmplitude = ref(0.02)
const recentDays = ref(2)

const fetchPath = computed(() => {
  let amp = minAmplitude.value
  if (amp > 0.5) amp = amp / 100
  const q = new URLSearchParams({
    lower_shadow_ratio: String(lowerShadowRatio.value),
    upper_shadow_ratio: String(upperShadowRatio.value),
    min_amplitude: String(amp),
    recent_days: String(recentDays.value),
  })
  return `long-lower-shadow-strategy?${q.toString()}`
})

const cols: SimpleCol[] = [
  { type: 'code', label: '股票代码', width: 90 },
  { type: 'name', label: '股票名称', width: 100 },
  { type: 'text', prop: 'pattern_date', label: '形态日', width: 110 },
  { type: 'price', prop: 'pattern_close', label: '收盘', width: 88 },
  { type: 'price', prop: 'lower_shadow', label: '下影', width: 88 },
  { type: 'price', prop: 'body_length', label: '实体', width: 88 },
  {
    type: 'custom',
    label: '影/体',
    width: 72,
    render: (r) => (r.shadow_body_ratio != null ? Number(r.shadow_body_ratio).toFixed(2) : '—'),
  },
  {
    type: 'custom',
    label: '振幅',
    width: 72,
    render: (r) => (r.amplitude != null ? `${(Number(r.amplitude) * 100).toFixed(2)}%` : '—'),
  },
  { type: 'price', prop: 'current_price', label: '当前价', width: 88 },
  { type: 'pct', label: '涨跌幅', width: 92 },
  { type: 'price', prop: 'ma20', label: 'MA20', width: 88 },
  {
    type: 'custom',
    label: '偏离MA20',
    width: 96,
    render: (r) =>
      r.deviation_from_ma20 != null ? `${(Number(r.deviation_from_ma20) * 100).toFixed(2)}%` : '—',
  },
  { type: 'actions', label: '操作', width: 120 },
]
</script>
