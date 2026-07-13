<template>
  <div class="urt-management">
    <div class="page-header">
      <h2>URT 上升趋势策略</h2>
      <p class="subtitle">连续阳线右侧交易：参数版本配置与选股试跑</p>
    </div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="策略参数" name="config">
        <UrtStrategyConfiguration />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import UrtStrategyConfiguration from '@/components/urt/StrategyConfiguration.vue'

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
