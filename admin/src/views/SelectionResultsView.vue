<template>
  <div class="selection-results">
    <div class="page-header">
      <div>
        <h1>选股管理</h1>
        <p class="page-subtitle">
          管理端策略选股与 3 倍量观察股维护。策略选股接口与网站端
          <code class="text-xs bg-gray-100 px-1 rounded">/api/screening/*</code>
          一致；GMS 策略版本（观察股 + 打分）请在侧栏 <strong>GMS策略版本</strong> 中维护。
        </p>
      </div>
    </div>

    <el-tabs v-model="activeTab" type="border-card" class="selection-tabs" @tab-change="onTabChange">
      <el-tab-pane label="策略选股" name="strategies">
        <div class="top-content bg-white rounded-lg shadow p-4">
          <ScreeningStrategiesPanel />
        </div>
      </el-tab-pane>
      <el-tab-pane label="3倍量观察股" name="triple-volume">
        <TripleVolumeObservePanel />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ScreeningStrategiesPanel from '@/components/screening/ScreeningStrategiesPanel.vue'
import TripleVolumeObservePanel from '@/components/triple-volume/TripleVolumeObservePanel.vue'

const route = useRoute()
const router = useRouter()
const activeTab = ref<'strategies' | 'triple-volume'>('strategies')

function onTabChange(name: string | number) {
  const tab = typeof name === 'number' ? String(name) : name
  router.replace({ path: '/selection-results', query: { ...route.query, tab } }).catch(() => {})
}

watch(
  () => route.query.tab,
  (tab) => {
    if (tab === 'triple-volume') {
      activeTab.value = 'triple-volume'
    } else {
      activeTab.value = 'strategies'
    }
  },
  { immediate: true }
)
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

.selection-tabs :deep(.el-tabs__content) {
  padding-top: 16px;
}
</style>
