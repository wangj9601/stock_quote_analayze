<template>
  <div class="selection-results">
    <div class="page-header">
      <div>
        <h1>选股管理</h1>
        <p class="page-subtitle">
          管理端策略选股，接口与网站端
          <code class="text-xs bg-gray-100 px-1 rounded">/api/screening/*</code>
          一致。GMS 策略版本（观察股 + 打分）请在侧栏 <strong>GMS策略版本</strong> 中维护。
        </p>
      </div>
    </div>

    <div class="top-content bg-white rounded-lg shadow p-4">
      <ScreeningStrategiesPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import ScreeningStrategiesPanel from '@/components/screening/ScreeningStrategiesPanel.vue'
</script>

<style scoped lang="postcss">
.selection-results {
  @apply space-y-6;
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
