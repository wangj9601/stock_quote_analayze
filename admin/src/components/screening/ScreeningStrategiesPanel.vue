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

      <!-- 已下线：停机坪、回踩年线、高而窄的旗形、持续上涨(MA30) -->
      <!-- 已隐藏：长下影线、低九策略、PVFARS（管理端不展示，网站端 screening 仍可保留） -->

      <el-tab-pane label="一阳穿三线" name="oneYang" lazy>
        <OneYangThreeLinesAdmin />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import GmsScreeningResults from '@/components/gms/GmsScreeningResults.vue'
import SimpleStrategyPane from './SimpleStrategyPane.vue'
import type { SimpleCol } from './SimpleStrategyPane.vue'
import OneYangThreeLinesAdmin from './OneYangThreeLinesAdmin.vue'

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
</script>

<style scoped lang="postcss">
.inner-strategy-tabs :deep(.el-tabs__content) {
  @apply pt-4;
}
</style>
