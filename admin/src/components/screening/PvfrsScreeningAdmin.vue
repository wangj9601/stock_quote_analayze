<template>
  <div class="space-y-4">
    <el-card shadow="never">
      <template #header><span class="font-semibold">PVFARS · 股票范围</span></template>
      <el-radio-group v-model="scope" class="flex flex-wrap gap-4">
        <el-radio label="cn">全部A股</el-radio>
        <el-radio label="hk">全部港股</el-radio>
        <el-radio label="watchlist">我的自选</el-radio>
      </el-radio-group>
    </el-card>

    <el-card shadow="never">
      <template #header><span class="font-semibold">买点参数（与网站端同源接口保存）</span></template>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div>
          <div class="text-xs text-gray-500 mb-1">观察周期（天）</div>
          <el-input-number v-model="form.observation_period" :min="5" :max="60" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">Δ/d₂₀ 上限（0=不启用）</div>
          <el-input-number v-model="form.buy_ratio_d20_max" :min="0" :max="1" :step="0.001" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">横盘不参与买点</div>
          <el-switch v-model="form.buy_exclude_sideways" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">宏观位移最小值</div>
          <el-input-number v-model="form.buy_macro_displacement_min" :step="0.001" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">即时强度最小值</div>
          <el-input-number v-model="form.buy_instant_deviation_min" :step="0.001" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">最小偏离度</div>
          <el-input-number v-model="form.buy_bias_min" :min="0" :max="0.5" :step="0.01" class="w-full" />
        </div>
        <div>
          <div class="text-xs text-gray-500 mb-1">最小相对位移</div>
          <el-input-number v-model="form.buy_relative_displacement_min" :min="0" :step="0.01" class="w-full" />
        </div>
      </div>
      <div class="mt-3 flex items-center gap-2">
        <el-button type="primary" plain :loading="paramsLoading" @click="loadParams">重新加载参数</el-button>
        <el-button type="success" plain :loading="saveLoading" @click="saveParams">保存参数</el-button>
        <span class="text-sm text-gray-500">{{ paramsStatus }}</span>
      </div>
    </el-card>

    <SimpleStrategyPane
      :bullets="[
        '接口：GET /api/screening/pvfrs-strategy?scope=…',
        '参数保存：POST /api/screening/pvfrs-params',
        '得分明细可在网站端展开查看；此处列出主列表字段',
      ]"
      :fetch-path="fetchPath"
      :columns="cols"
      export-name="PVFARS"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import SimpleStrategyPane, { type SimpleCol } from './SimpleStrategyPane.vue'
import { pvfrsParamsGet, pvfrsParamsPost } from '@/services/screeningPublicApi'

const scope = ref<'cn' | 'hk' | 'watchlist'>('cn')

const form = reactive({
  observation_period: 20 as number,
  buy_ratio_d20_max: 0 as number,
  buy_exclude_sideways: false,
  buy_macro_displacement_min: 0 as number,
  buy_instant_deviation_min: 0 as number,
  buy_bias_min: 0 as number,
  buy_relative_displacement_min: 0 as number,
})

const paramsLoading = ref(false)
const saveLoading = ref(false)
const paramsStatus = ref('')

const fetchPath = computed(() => `pvfrs-strategy?scope=${encodeURIComponent(scope.value)}`)

async function loadParams() {
  paramsLoading.value = true
  paramsStatus.value = ''
  try {
    const json = await pvfrsParamsGet()
    if (!json.success || !json.data) {
      paramsStatus.value = json.message || '加载失败'
      return
    }
    const d = json.data
    if (d.observation_period != null) form.observation_period = Number(d.observation_period)
    if (d.buy_ratio_d20_max != null) form.buy_ratio_d20_max = Number(d.buy_ratio_d20_max)
    if (d.buy_exclude_sideways != null) form.buy_exclude_sideways = !!d.buy_exclude_sideways
    if (d.buy_macro_displacement_min != null) form.buy_macro_displacement_min = Number(d.buy_macro_displacement_min)
    if (d.buy_instant_deviation_min != null) form.buy_instant_deviation_min = Number(d.buy_instant_deviation_min)
    if (d.buy_bias_min != null) form.buy_bias_min = Number(d.buy_bias_min)
    if (d.buy_relative_displacement_min != null) {
      form.buy_relative_displacement_min = Number(d.buy_relative_displacement_min)
    }
    paramsStatus.value = '已从服务器加载'
  } catch (e) {
    paramsStatus.value = e instanceof Error ? e.message : '加载异常'
  } finally {
    paramsLoading.value = false
  }
}

async function saveParams() {
  saveLoading.value = true
  paramsStatus.value = ''
  try {
    const res = await pvfrsParamsPost({ ...form })
    if (res.success) {
      paramsStatus.value = '已保存'
      ElMessage.success('参数已保存')
    } else {
      paramsStatus.value = res.message || '保存失败'
    }
  } catch (e) {
    paramsStatus.value = e instanceof Error ? e.message : '保存异常'
  } finally {
    saveLoading.value = false
  }
}

onMounted(() => void loadParams())

const cols: SimpleCol[] = [
  { type: 'code', label: '股票代码', width: 96 },
  { type: 'name', label: '股票名称', width: 100 },
  {
    type: 'custom',
    label: '信号强度',
    width: 88,
    render: (r) => {
      const s = r.signal_strength
      if (s == null || typeof s !== 'number') return '—'
      return `${(s * 100).toFixed(1)}%`
    },
  },
  { type: 'price', prop: 'current_price', label: '当前价', width: 88 },
  { type: 'text', prop: 'price_dimension_status', label: '价格维', minWidth: 100 },
  { type: 'text', prop: 'frequency_dimension_status', label: '频率维', minWidth: 100 },
  { type: 'text', prop: 'volume_dimension_status', label: '成交量维', minWidth: 100 },
  { type: 'text', prop: 'resonance_status', label: '共振', width: 92 },
  { type: 'text', prop: 'entry_timing_status', label: '买点时机', minWidth: 100 },
  { type: 'text', prop: 'investment_advice', label: '建议', width: 88 },
  { type: 'pct', label: '涨跌幅', width: 92 },
  { type: 'actions', label: '操作', width: 130 },
]
</script>
