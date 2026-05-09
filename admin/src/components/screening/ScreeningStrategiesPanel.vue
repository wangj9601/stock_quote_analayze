<template>
  <div class="screening-strategies-panel">
    <el-tabs v-model="active" type="border-card" class="inner-strategy-tabs">
      <!-- 默认：与全模块冒烟（GMS 参数表单）一致 -->
      <el-tab-pane label="GMS均值引力动量" name="gms">
        <GmsScreeningResults />
      </el-tab-pane>

      <el-tab-pane label="创业板中线" name="cyb" lazy>
        <SimpleStrategyPane
          :bullets="cybBullets"
          fetch-path="cyb-midline-strategy?months=4"
          :columns="cybCols"
          export-name="创业板中线"
        />
      </el-tab-pane>

      <el-tab-pane label="停机坪" name="parking" lazy>
        <SimpleStrategyPane
          :bullets="parkingBullets"
          fetch-path="parking-apron-strategy"
          :columns="parkingCols"
          export-name="停机坪"
        />
      </el-tab-pane>

      <el-tab-pane label="回踩年线" name="backtrace" lazy>
        <SimpleStrategyPane
          :bullets="backtraceBullets"
          fetch-path="backtrace-ma250-strategy"
          :columns="backtraceCols"
          export-name="回踩年线"
        />
      </el-tab-pane>

      <el-tab-pane label="高而窄的旗形" name="highTight" lazy>
        <SimpleStrategyPane
          :bullets="highTightBullets"
          fetch-path="high-tight-flag-strategy"
          :columns="highTightCols"
          export-name="高而窄旗形"
        />
      </el-tab-pane>

      <el-tab-pane label="持续上涨(MA30)" name="keepInc" lazy>
        <SimpleStrategyPane
          :bullets="keepBullets"
          fetch-path="keep-increasing-strategy"
          :columns="keepCols"
          export-name="持续上涨MA30"
        />
      </el-tab-pane>

      <el-tab-pane label="长下影线" name="longShadow" lazy>
        <LongLowerShadowAdmin />
      </el-tab-pane>

      <el-tab-pane label="低九策略" name="lowNine" lazy>
        <SimpleStrategyPane
          :bullets="lowNineBullets"
          fetch-path="low-nine-strategy"
          :columns="lowNineCols"
          export-name="低九策略"
        />
      </el-tab-pane>

      <el-tab-pane label="一阳穿三线" name="oneYang" lazy>
        <OneYangThreeLinesAdmin />
      </el-tab-pane>

      <el-tab-pane label="PVFARS" name="pvfrs" lazy>
        <PvfrsScreeningAdmin />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import GmsScreeningResults from '@/components/gms/GmsScreeningResults.vue'
import SimpleStrategyPane from './SimpleStrategyPane.vue'
import type { SimpleCol } from './SimpleStrategyPane.vue'
import LongLowerShadowAdmin from './LongLowerShadowAdmin.vue'
import OneYangThreeLinesAdmin from './OneYangThreeLinesAdmin.vue'
import PvfrsScreeningAdmin from './PvfrsScreeningAdmin.vue'

const active = ref('gms')

const cybBullets = [
  '股票范围：创业板（代码以 3 开头），排除 ST',
  '时间范围：最近约 4 个月',
  '接口：GET /api/screening/cyb-midline-strategy',
]

const cybCols: SimpleCol[] = [
  { type: 'code', label: '股票代码', width: 90 },
  { type: 'name', label: '股票名称', width: 100 },
  { type: 'text', prop: 'limit_up_date', label: '涨停日期', width: 110 },
  { type: 'price', prop: 'limit_up_price', label: '涨停价格', width: 92 },
  { type: 'text', prop: 'breakthrough_date', label: '突破日期', width: 110 },
  { type: 'price', prop: 'breakthrough_price', label: '突破价格', width: 92 },
  { type: 'price', prop: 'current_price', label: '当前价格', width: 92 },
  { type: 'pct', label: '当前涨跌幅', width: 100 },
  { type: 'price', prop: 'ma5', label: 'MA5', width: 88 },
  { type: 'price', prop: 'ma10', label: 'MA10', width: 88 },
  { type: 'price', prop: 'ma20', label: 'MA20', width: 88 },
  { type: 'actions', label: '操作', width: 120 },
]

const parkingBullets = ['股票范围：全部A股', '接口：GET /api/screening/parking-apron-strategy']

const parkingCols: SimpleCol[] = [
  { type: 'code', label: '股票代码', width: 90 },
  { type: 'name', label: '股票名称', width: 100 },
  { type: 'text', prop: 'limit_up_date', label: '涨停日期', width: 110 },
  { type: 'price', prop: 'limit_up_price', label: '涨停价格', width: 92 },
  { type: 'price', prop: 'current_price', label: '当前价格', width: 92 },
  { type: 'pct', label: '当前涨跌幅', width: 100 },
  { type: 'actions', label: '操作', width: 120 },
]

const backtraceBullets = ['股票范围：全部A股', '接口：GET /api/screening/backtrace-ma250-strategy']

const backtraceCols: SimpleCol[] = [
  { type: 'code', label: '股票代码', width: 90 },
  { type: 'name', label: '股票名称', width: 100 },
  { type: 'text', prop: 'highest_date', label: '最高价日期', width: 110 },
  { type: 'price', prop: 'highest_price', label: '最高价', width: 92 },
  { type: 'text', prop: 'lowest_date', label: '最低价日期', width: 110 },
  { type: 'price', prop: 'lowest_price', label: '最低价', width: 92 },
  { type: 'price', prop: 'current_price', label: '当前价格', width: 92 },
  { type: 'pct', label: '当前涨跌幅', width: 100 },
  { type: 'actions', label: '操作', width: 120 },
]

const highTightBullets = ['接口：GET /api/screening/high-tight-flag-strategy']

const highTightCols: SimpleCol[] = [
  { type: 'code', label: '股票代码', width: 90 },
  { type: 'name', label: '股票名称', width: 100 },
  { type: 'price', prop: 'current_price', label: '当前价格', width: 92 },
  { type: 'pct', label: '当前涨跌幅', width: 100 },
  { type: 'price', prop: 'period_low', label: '区间低', width: 92 },
  {
    type: 'custom',
    label: '价比',
    width: 88,
    render: (r) => (r.price_ratio != null ? Number(r.price_ratio).toFixed(2) : '—'),
  },
  { type: 'actions', label: '操作', width: 120 },
]

const keepBullets = ['接口：GET /api/screening/keep-increasing-strategy']

const keepCols: SimpleCol[] = [
  { type: 'code', label: '股票代码', width: 90 },
  { type: 'name', label: '股票名称', width: 100 },
  { type: 'price', prop: 'current_price', label: '当前价格', width: 92 },
  { type: 'pct', label: '当前涨跌幅', width: 100 },
  { type: 'price', prop: 'current_ma30', label: '当前MA30', width: 96 },
  { type: 'price', prop: 'ma30_before_30', label: '30日前MA30', width: 108 },
  {
    type: 'custom',
    label: 'MA30升幅',
    width: 100,
    render: (r) =>
      r.ma30_increase_ratio != null ? `${(Number(r.ma30_increase_ratio) * 100).toFixed(2)}%` : '—',
  },
  { type: 'actions', label: '操作', width: 120 },
]

const lowNineBullets = ['接口：GET /api/screening/low-nine-strategy']

const lowNineCols: SimpleCol[] = [
  { type: 'code', label: '股票代码', width: 90 },
  { type: 'name', label: '股票名称', width: 100 },
  { type: 'text', prop: 'pattern_start_date', label: '形态起始日', width: 110 },
  { type: 'text', prop: 'pattern_end_date', label: '形态结束日', width: 110 },
  { type: 'price', prop: 'pattern_start_price', label: '起始价', width: 92 },
  {
    type: 'custom',
    label: '九日跌幅',
    width: 92,
    render: (r) => (r.nine_day_decline != null ? `${Number(r.nine_day_decline).toFixed(2)}%` : '—'),
  },
  { type: 'price', prop: 'nine_day_high', label: '九日高', width: 88 },
  { type: 'price', prop: 'nine_day_low', label: '九日低', width: 88 },
  { type: 'price', prop: 'current_price', label: '当前价格', width: 92 },
  { type: 'pct', label: '当前涨跌幅', width: 100 },
  { type: 'actions', label: '操作', width: 120 },
]
</script>

<style scoped lang="postcss">
.inner-strategy-tabs :deep(.el-tabs__content) {
  @apply pt-4;
}
</style>
