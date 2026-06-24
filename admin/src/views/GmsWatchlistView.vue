<template>
  <div class="gms-watchlist-page space-y-6">
    <div class="page-header">
      <div>
        <h1>GMS 策略版本</h1>
        <p class="page-subtitle">
          统一管理 GMS 策略版本与观察股；打分参数仅两个共享版本：<strong>default</strong>（标准版）与 <strong>gms_penalty</strong>（减分版），修改原地保存不新建版本。
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
