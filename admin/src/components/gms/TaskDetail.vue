<template>
  <el-dialog
    v-model="visible"
    title="任务详情"
    width="720px"
    destroy-on-close
    @close="handleClose"
  >
    <div v-if="loading" class="flex justify-center p-8"><el-icon class="is-loading"><Loading /></el-icon></div>
    <div v-else-if="task" class="task-detail">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="任务ID">{{ task.task_id?.slice(0, 8) }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ task.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="task.status === 'completed' ? 'success' : task.status === 'failed' ? 'danger' : 'primary'">
            {{ task.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="进度">{{ task.progress ?? 0 }}%</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ formatDate(task.created_at) }}</el-descriptions-item>
        <template v-if="task.config">
          <el-descriptions-item label="市场">{{ task.config.market }}</el-descriptions-item>
          <el-descriptions-item label="日期范围">{{ task.config.start_date }} ~ {{ task.config.end_date }}</el-descriptions-item>
          <el-descriptions-item label="目标阈值">{{ (task.config.target_pct * 100) }}%</el-descriptions-item>
          <el-descriptions-item label="持有窗口">{{ task.config.horizon_days }} 日</el-descriptions-item>
        </template>
      </el-descriptions>

      <template v-if="task.summary">
        <h4 class="mt-4 mb-2">汇总</h4>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="样本数">{{ task.summary.total_samples }}</el-descriptions-item>
          <el-descriptions-item label="命中数">{{ task.summary.hit_count }}</el-descriptions-item>
          <el-descriptions-item label="命中率">{{ (task.summary.hit_rate * 100).toFixed(2) }}%</el-descriptions-item>
        </el-descriptions>
        <h4 class="mt-4 mb-2">按买入类型</h4>
        <el-table :data="buyTypeRows" size="small" border>
          <el-table-column prop="name" label="类型" />
          <el-table-column prop="total" label="样本数" width="80" />
          <el-table-column prop="hit" label="命中" width="80" />
          <el-table-column prop="hit_rate" label="命中率">
            <template #default="scope">{{ (scope.row.hit_rate * 100).toFixed(2) }}%</template>
          </el-table-column>
        </el-table>
        <h4 class="mt-4 mb-2">按分数分桶</h4>
        <el-table :data="scoreBucketRows" size="small" border>
          <el-table-column prop="name" label="分桶" />
          <el-table-column prop="total" label="样本数" width="80" />
          <el-table-column prop="hit" label="命中" width="80" />
          <el-table-column prop="hit_rate" label="命中率">
            <template #default="scope">{{ (scope.row.hit_rate * 100).toFixed(2) }}%</template>
          </el-table-column>
        </el-table>
      </template>

      <h4 class="mt-4 mb-2">日志</h4>
      <div class="log-box">
        <div v-for="(log, i) in logs" :key="i" class="log-line">{{ log.text }}</div>
        <div v-if="logs.length === 0" class="text-gray-400">暂无日志</div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed, inject } from 'vue'
import { Loading } from '@element-plus/icons-vue'

const props = defineProps<{ modelValue: boolean; taskId: string }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void; (e: 'closed'): void }>()

const gmsApi = inject<any>('gmsApi')
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

const task = ref<any>(null)
const logs = ref<any[]>([])
const loading = ref(false)

const buyTypeRows = computed(() => {
  const s = task.value?.summary?.by_buy_type
  if (!s || typeof s !== 'object') return []
  return Object.entries(s).map(([name, v]: [string, any]) => ({
    name,
    total: v.total ?? 0,
    hit: v.hit ?? 0,
    hit_rate: v.hit_rate ?? 0
  }))
})

const scoreBucketRows = computed(() => {
  const s = task.value?.summary?.by_score_bucket
  if (!s || typeof s !== 'object') return []
  return Object.entries(s).map(([name, v]: [string, any]) => ({
    name,
    total: v.total ?? 0,
    hit: v.hit ?? 0,
    hit_rate: v.hit_rate ?? 0
  }))
})

function formatDate(v: string) {
  if (!v) return '-'
  return v.replace('Z', '').slice(0, 19)
}

async function load() {
  if (!props.taskId) return
  loading.value = true
  task.value = null
  logs.value = []
  try {
    task.value = await gmsApi.getBacktestTask(props.taskId)
    const logList = await gmsApi.getBacktestLogs(props.taskId)
    logs.value = Array.isArray(logList) ? logList : []
  } finally {
    loading.value = false
  }
}

function handleClose() {
  emit('closed')
}

watch(
  () => [props.modelValue, props.taskId],
  ([v, id]) => {
    if (v && id) load()
  },
  { immediate: true }
)
</script>

<style scoped>
.log-box { max-height: 200px; overflow-y: auto; border: 1px solid var(--el-border-color); border-radius: 4px; padding: 8px; font-size: 12px; }
.log-line { padding: 2px 0; }
.mt-4 { margin-top: 1rem; }
.mb-2 { margin-bottom: 0.5rem; }
</style>
