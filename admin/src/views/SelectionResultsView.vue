<template>
  <div class="selection-results">
    <div class="page-header">
      <div>
        <h1>GMS策略管理</h1>
        <p class="page-subtitle">
          「选股结果」与网站端<strong>选股 → GMS均值引力动量</strong>一致：同一接口
          <code>/api/screening/gms-strategy</code>（先 trace 快显，再按需全量计算）。导出自选用户需管理员权限。
        </p>
      </div>
    </div>

    <el-tabs v-model="activeMainTab" class="gms-strategy-tabs" @tab-change="handleMainTabChange">
      <el-tab-pane label="选股结果" name="selection">
        <GmsScreeningResults />
      </el-tab-pane>

      <!-- lazy：进入页默认只看「选股结果」时不挂载观察股管理，避免冒烟/首屏多一套列表请求与误认「全量」 -->
      <el-tab-pane label="观察股管理" name="watchlist" lazy>
        <WatchlistManagement ref="watchlistRef" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import GmsScreeningResults from '@/components/gms/GmsScreeningResults.vue'
import WatchlistManagement from '@/components/gms/WatchlistManagement.vue'

const activeMainTab = ref<'selection' | 'watchlist'>('selection')
const watchlistRef = ref<{ refresh?: () => void } | null>(null)

const handleMainTabChange = (name: string | number) => {
  if (name === 'watchlist') watchlistRef.value?.refresh?.()
}
</script>

<style scoped lang="postcss">
.selection-results {
  @apply space-y-6;
}

.gms-strategy-tabs {
  @apply bg-white rounded-lg shadow p-4;
}

.page-header {
  h1 {
    @apply text-2xl font-bold text-gray-900;
  }

  .page-subtitle {
    @apply mt-1 text-sm text-gray-500 max-w-4xl leading-relaxed;
    code {
      @apply text-xs bg-gray-100 px-1 rounded;
    }
  }
}
</style>
