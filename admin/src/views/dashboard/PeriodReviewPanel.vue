<template>
  <div class="daily-review-panel" v-loading="loading">
    <div class="dr-toolbar">
      <el-date-picker v-model="anchor" type="date" value-format="YYYY-MM-DD" placeholder="区间内日期" size="small" />
      <el-button size="small" @click="load">加载</el-button>
      <el-button size="small" type="primary" @click="compute">重算</el-button>
      <el-button size="small" type="success" @click="save">保存观点/建议</el-button>
      <el-button size="small" @click="exportFile('md')">导出 MD</el-button>
      <el-button size="small" type="warning" @click="exportFile('pdf')">导出 PDF</el-button>
      <span class="dr-status">{{ status }}</span>
    </div>
    <p class="dr-desc">{{ hint }}</p>
    <template v-if="data">
      <el-card shadow="never" class="dr-block">
        <template #header>大盘</template>
        <p>{{ data.note }}</p>
        <p>日均成交 {{ fmt(data.vol_avg) }} 万亿，上一期日均 {{ fmt(data.prev_vol_avg) }} 万亿。</p>
        <el-table :data="data.indexes || []" size="small" border empty-text="暂无">
          <el-table-column prop="name" label="指数" />
          <el-table-column label="期初收盘"><template #default="{ row }">{{ fmt(row.start_close) }}</template></el-table-column>
          <el-table-column label="期末收盘"><template #default="{ row }">{{ fmt(row.end_close) }}</template></el-table-column>
          <el-table-column label="区间涨跌%"><template #default="{ row }"><span :class="tone(row.period_pct)">{{ fmt(row.period_pct) }}</span></template></el-table-column>
        </el-table>
      </el-card>
      <el-card shadow="never" class="dr-block">
        <template #header>趋势路径</template>
        <p>高度 {{ deltaText(data.delta?.height, '板', 0) }}；连板 {{ deltaText(data.delta?.cb_count, '家', 0) }}</p>
        <el-table :data="data.path || []" size="small" border empty-text="暂无">
          <el-table-column prop="trade_date" label="日期" />
          <el-table-column label="高度"><template #default="{ row }">{{ intText(row.height) }}</template></el-table-column>
          <el-table-column label="连板"><template #default="{ row }">{{ intText(row.cb_count) }}</template></el-table-column>
          <el-table-column prop="season" label="季节" />
          <el-table-column label="成交(万亿)"><template #default="{ row }">{{ fmt(row.vol_trillion) }}</template></el-table-column>
          <el-table-column prop="tape_label" label="盘面" />
        </el-table>
      </el-card>
      <el-card shadow="never" class="dr-block">
        <template #header>硬门槛达标天数</template>
        <el-table :data="data.gates || []" size="small" border empty-text="暂无">
          <el-table-column prop="name" label="门槛" />
          <el-table-column prop="standard" label="标准" />
          <el-table-column label="达标天数"><template #default="{ row }">{{ row.passed_days || 0 }}/{{ row.total_days || 0 }}</template></el-table-column>
        </el-table>
      </el-card>
      <el-card shadow="never" class="dr-block">
        <template #header>主线持续性</template>
        <el-table :data="data.mainlines || []" size="small" border empty-text="暂无">
          <el-table-column prop="board_name" label="概念" />
          <el-table-column prop="hit_days" label="上榜天数" />
          <el-table-column prop="tier_label" label="期末定性" />
          <el-table-column label="持续"><template #default="{ row }">{{ row.persistent ? '是' : '否' }}</template></el-table-column>
        </el-table>
        <p>{{ data.industry_confirm?.summary }}</p>
        <p>情绪 {{ (data.seasons || []).join(' → ') || '—' }}，切换 {{ data.season_switches || 0 }} 次，期末 {{ data.end_season || '—' }}。</p>
      </el-card>
      <el-card shadow="never" class="dr-block">
        <template #header>{{ nxt }}个股</template>
        <p>{{ data.picks?.disclaimer }}</p>
        <p>{{ data.picks?.note }}</p>
        <h4>不追</h4>
        <el-table :data="data.picks?.no_chase || []" size="small" border empty-text="暂无">
          <el-table-column label="个股"><template #default="{ row }"><a :href="link(row)" target="_blank">{{ row.name }} {{ row.code }}</a></template></el-table-column>
          <el-table-column label="连板"><template #default="{ row }">{{ intText(row.board_count) }}</template></el-table-column>
          <el-table-column label="立场" prop="stance" />
          <el-table-column label="区间涨跌%"><template #default="{ row }"><span :class="tone(row.period_pct)">{{ fmt(row.period_pct) }}</span></template></el-table-column>
        </el-table>
        <h4>可跟踪</h4>
        <el-table :data="data.picks?.track || []" size="small" border empty-text="暂无">
          <el-table-column label="个股"><template #default="{ row }"><a :href="link(row)" target="_blank">{{ row.name }} {{ row.code }}</a></template></el-table-column>
          <el-table-column label="行业"><template #default="{ row }">{{ industryText(row.industry) }}</template></el-table-column>
          <el-table-column prop="stance" label="立场" />
          <el-table-column label="区间涨跌%"><template #default="{ row }"><span :class="tone(row.period_pct)">{{ fmt(row.period_pct) }}</span></template></el-table-column>
          <el-table-column prop="trigger" label="触发" min-width="180" />
        </el-table>
        <h4>支线只观察</h4>
        <el-table :data="data.picks?.sideline || []" size="small" border empty-text="暂无">
          <el-table-column label="个股"><template #default="{ row }"><a :href="link(row)" target="_blank">{{ row.name }} {{ row.code }}</a></template></el-table-column>
          <el-table-column label="行业"><template #default="{ row }">{{ industryText(row.industry) }}</template></el-table-column>
          <el-table-column label="区间涨跌%"><template #default="{ row }"><span :class="tone(row.period_pct)">{{ fmt(row.period_pct) }}</span></template></el-table-column>
          <el-table-column prop="stance" label="立场" />
        </el-table>
        <h4>回避</h4>
        <el-table :data="data.picks?.avoid || []" size="small" border empty-text="暂无">
          <el-table-column label="个股"><template #default="{ row }"><a :href="link(row)" target="_blank">{{ row.name }} {{ row.code }}</a></template></el-table-column>
          <el-table-column prop="reason" label="原因" />
        </el-table>
      </el-card>
      <el-card shadow="never" class="dr-block">
        <template #header>观点与建议</template>
        <el-input v-model="viewpoint" type="textarea" :rows="4" />
        <el-input v-model="advice" type="textarea" :rows="4" style="margin-top: 8px" />
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  computePeriodReview,
  exportPeriodReview,
  getPeriodReview,
  savePeriodReviewText,
} from '@/services/marketReview.service'
import { stockDetailUrl } from '@/utils/publicStockLinks'

const props = defineProps<{ periodType: 'week' | 'month' }>()
const nxt = computed(() => (props.periodType === 'month' ? '下月' : '下周'))
const hint = computed(() =>
  props.periodType === 'month'
    ? '按自然月汇总已有每日复盘。个股是下月计划，不是按月末收盘价买入。'
    : '按自然周汇总已有每日复盘。个股是下周计划，不是把每日明日名单拼在一起。'
)

const anchor = ref(yesterday())
const loading = ref(false)
const status = ref('')
const data = ref<any>(null)
const viewpoint = ref('')
const advice = ref('')

function yesterday() {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function industryText(v: any) {
  const s = String(v ?? '').trim()
  if (!s || ['nan', 'none', 'null', '-', '--', 'nat'].includes(s.toLowerCase())) return '—'
  return s
}

function fmt(v: any) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return Number.isFinite(n) ? n.toFixed(2) : String(v)
}

function intText(v: any) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  return Number.isFinite(n) ? String(Math.round(n)) : String(v)
}

function tone(v: any) {
  const n = Number(v)
  if (!Number.isFinite(n) || n === 0) return ''
  return n > 0 ? 'dr-up' : 'dr-down'
}

function deltaText(pair: any, unit = '', digits = 2) {
  if (!pair || (pair.from == null && pair.to == null)) return '—'
  const show = (v: any) => {
    if (v == null || v === '') return '—'
    const n = Number(v)
    if (!Number.isFinite(n)) return String(v)
    return digits === 0 ? String(Math.round(n)) : n.toFixed(digits)
  }
  if (pair.from == null || pair.to == null) return `${show(pair.from)} → ${show(pair.to)}`
  const diff = Number(pair.to) - Number(pair.from)
  const sign = diff > 0 ? '+' : ''
  return `${show(pair.from)} → ${show(pair.to)}（${sign}${show(diff)}${unit}）`
}

function link(row: any) {
  return stockDetailUrl(row.code, row.name)
}

function apply(payload: any) {
  data.value = payload || null
  viewpoint.value = payload?.viewpoint_md || ''
  advice.value = payload?.advice_md || ''
}

async function load() {
  if (!anchor.value) return
  loading.value = true
  try {
    const res = await getPeriodReview(props.periodType, anchor.value)
    if (!res.success) {
      data.value = null
      status.value = res.message || '暂无快照'
      return
    }
    apply(res.data)
    status.value = `已加载 ${res.data?.period_key || ''}`
  } catch (e: any) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function compute() {
  if (!anchor.value) return
  loading.value = true
  status.value = '正在汇总…'
  try {
    const res = await computePeriodReview(props.periodType, anchor.value)
    if (!res.success) {
      ElMessage.error(res.message || '重算失败')
      status.value = res.message || '重算失败'
      return
    }
    apply(res.data)
    status.value = `已重算 ${res.data?.period_key || ''}`
  } catch (e: any) {
    ElMessage.error(e?.message || '重算失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!anchor.value) return
  loading.value = true
  try {
    const res = await savePeriodReviewText(props.periodType, anchor.value, {
      viewpoint_md: viewpoint.value,
      advice_md: advice.value,
    })
    if (!res.success) {
      ElMessage.error(res.message || '保存失败')
      return
    }
    apply(res.data)
    ElMessage.success('已保存')
    status.value = '观点/建议已保存'
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    loading.value = false
  }
}

async function exportFile(ext: 'md' | 'pdf') {
  if (!anchor.value) return
  loading.value = true
  try {
    const res = await exportPeriodReview(props.periodType, anchor.value, ext)
    if (!res.ok) {
      ElMessage.error(res.message || '导出失败')
      return
    }
    status.value = res.filename || '已下载'
  } catch (e: any) {
    ElMessage.error(e?.message || '导出失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.daily-review-panel { display: flex; flex-direction: column; gap: 12px; }
.dr-toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.dr-status, .dr-desc { color: #64748b; font-size: 13px; }
.dr-block { margin-top: 4px; }
.dr-up { color: #dc2626; font-weight: 600; }
.dr-down { color: #16a34a; font-weight: 600; }
</style>
