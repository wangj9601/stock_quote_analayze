<template>
  <div class="gms-watchlist-page space-y-6">
    <div class="page-header">
      <div>
        <h1>观察股管理</h1>
        <p class="page-subtitle">
          GMS 策略<strong>启用版本</strong>下的观察股维护（A/HK）；与选股管理中 GMS「GMS观察股」数据源一致。
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
