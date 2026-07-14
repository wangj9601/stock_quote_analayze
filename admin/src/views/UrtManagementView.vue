<template>
  <div class="urt-management">
    <div class="page-header">
      <h2>URT 上升趋势策略</h2>
      <p class="subtitle">参数配置、信号预计算与回测管理</p>
    </div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="策略参数" name="config">
        <UrtStrategyConfiguration />
      </el-tab-pane>
      <el-tab-pane label="回测管理" name="backtest">
        <UrtBacktestManagement />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import UrtStrategyConfiguration from '@/components/urt/StrategyConfiguration.vue'
import UrtBacktestManagement from '@/components/urt/BacktestManagement.vue'

const activeTab = ref('config')
</script>

<style scoped>
.urt-management {
  padding: 16px 20px;
}
.page-header h2 {
  margin: 0 0 4px;
  font-size: 20px;
}
.subtitle {
  margin: 0 0 16px;
  color: #6b7280;
  font-size: 13px;
}
</style>
