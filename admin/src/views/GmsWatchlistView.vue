<template>
  <div class="gms-watchlist-page space-y-6">
    <div class="page-header">
      <div>
        <h1>GMS 策略版本</h1>
        <p class="page-subtitle">
          统一管理 GMS 策略版本：观察股列表与打分机制（标准版 / 增强减分版）1:1 绑定参数版本；与网站选股「GMS观察股」数据源一致。
        </p>
      </div>
    </div>

    <div class="bg-white rounded-lg shadow p-4">
      <WatchlistManagement />
    </div>
  </div>
</template>

<script setup lang="ts">
import WatchlistManagement from '@/components/gms/WatchlistManagement.vue'
</script>

<style scoped lang="postcss">
.page-header {
  h1 {
    @apply text-2xl font-bold text-gray-900;
  }

  .page-subtitle {
    @apply mt-1 text-sm text-gray-500 max-w-3xl leading-relaxed;
  }
}
</style>
