<template>
  <div class="daily-review-panel" v-loading="loading">
    <div class="dr-toolbar">
      <el-date-picker
        v-model="tradeDate"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="交易日"
        size="small"
      />
      <el-button size="small" @click="load">加载</el-button>
      <el-button size="small" type="primary" @click="compute">重算</el-button>
      <el-button size="small" @click="collectZt">补采涨停池</el-button>
      <el-button size="small" type="success" @click="save">保存观点/建议</el-button>
      <el-button size="small" @click="exportMd">导出 MD</el-button>
      <el-button size="small" type="warning" @click="exportPdf">导出 PDF</el-button>
      <span class="dr-status">{{ status }}</span>
    </div>

    <el-row :gutter="12" class="dr-metrics" v-if="data">
      <el-col :xs="12" :sm="8" :md="4" v-for="m in metricCards" :key="m.label">
        <el-card shadow="never" class="dr-metric-card">
          <div class="label">{{ m.label }}</div>
          <div class="value">{{ m.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="data" class="dr-block" shadow="never">
      <template #header>趋势摘要</template>
      <p>{{ (data.rules_json && data.rules_json.summary) || '—' }}</p>
      <p class="muted">季节：{{ data.season || '—' }} · 口径：{{ data.limit_source || '—' }}</p>
    </el-card>

    <el-card v-if="data" class="dr-block" shadow="never">
      <template #header>
        五项硬门槛
        <span class="muted">{{ (data.hard_gates && data.hard_gates.rate) || '' }}</span>
      </template>
      <el-table :data="gateRows" size="small" stripe border>
        <el-table-column prop="id" label="#" width="50" />
        <el-table-column prop="name" label="门槛" min-width="140" />
        <el-table-column prop="standard" label="标准" min-width="120" />
        <el-table-column label="今日" width="100">
          <template #default="{ row }">{{ fmt(row.value) }}</template>
        </el-table-column>
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="row.passed ? 'success' : 'danger'" size="small">
              {{ row.passed ? '达标' : '不达标' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="data" class="dr-block" shadow="never">
      <template #header>主线板块（近10日·同花顺概念）</template>
      <p class="muted">{{ (data.mainline_json && data.mainline_json.summary) || '' }}</p>
      <el-table :data="mainlineRows" size="small" stripe border>
        <el-table-column label="概念板块" min-width="120">
          <template #default="{ row }">
            <a
              v-if="row.board_code"
              class="dr-board-link"
              :href="boardHref('concept', row)"
              target="_blank"
              rel="noopener noreferrer"
              title="打开板块详情"
            >{{ row.board_name || row.board_code }}</a>
            <span v-else>{{ row.board_name || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="hits_10d" label="上榜" width="70" />
        <el-table-column prop="tier_label" label="定性" min-width="110" />
        <el-table-column prop="today_status" label="今日" min-width="100" />
        <el-table-column prop="echelon" label="梯队" width="90" />
      </el-table>
    </el-card>

    <el-card v-if="data" class="dr-block" shadow="never">
      <template #header>当日行业赛道确认</template>
      <p class="muted">{{ industryConfirmSummary }}</p>
      <el-table :data="industryConfirmRows" size="small" stripe border>
        <el-table-column label="行业板块" min-width="120">
          <template #default="{ row }">
            <a
              v-if="row.board_code"
              class="dr-board-link"
              :href="boardHref('industry', row)"
              target="_blank"
              rel="noopener noreferrer"
              title="打开板块详情"
            >{{ row.board_name || row.board_code }}</a>
            <span v-else>{{ row.board_name || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason_text" label="上榜原因" min-width="140" />
        <el-table-column label="涨跌幅%" width="100">
          <template #default="{ row }">{{ fmt(row.change_percent) }}</template>
        </el-table-column>
        <el-table-column label="净流入" width="110">
          <template #default="{ row }">{{ fmt(row.net_inflow, 0) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-row :gutter="16" v-if="data">
      <el-col :xs="24" :md="12">
        <el-card class="dr-block" shadow="never">
          <template #header>观点与盘面分析</template>
          <el-input v-model="viewpoint" type="textarea" :rows="6" />
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card class="dr-block" shadow="never">
          <template #header>操作建议</template>
          <el-input v-model="advice" type="textarea" :rows="6" />
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="markdown" class="dr-block" shadow="never">
      <template #header>Markdown 预览</template>
      <pre class="dr-md">{{ markdown }}</pre>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  collectZtPool,
  computeDailyReview,
  exportDailyReviewMd,
  exportDailyReviewPdf,
  getDailyReview,
  saveDailyReviewText,
} from '@/services/marketReview.service'
import { boardDetailUrl } from '@/utils/publicStockLinks'

const loading = ref(false)
const status = ref('')
const data = ref<any>(null)
const viewpoint = ref('')
const advice = ref('')
const markdown = ref('')

function yesterday(): string {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

const tradeDate = ref(yesterday())

const gateRows = computed(() => (data.value?.hard_gates?.items as any[]) || [])
const mainlineRows = computed(() => (data.value?.mainline_json?.rows as any[]) || [])
const industryConfirmRows = computed(
  () => (data.value?.mainline_json?.industry_confirm?.rows as any[]) || []
)
const industryConfirmSummary = computed(
  () => data.value?.mainline_json?.industry_confirm?.summary || ''
)

const metricCards = computed(() => {
  const d = data.value || {}
  return [
    { label: 'Vol(万亿)', value: fmt(d.vol_trillion) },
    { label: '涨停', value: fmt(d.limit_up_count, 0) },
    { label: 'CB', value: fmt(d.cb_count, 0) },
    { label: '高度', value: fmt(d.height, 0) },
    { label: '昨连板%', value: fmt(d.prev_cb_return) },
    { label: 'Lo', value: fmt(d.lo_value) },
    { label: 'Hi', value: fmt(d.hi_value) },
    { label: 'Sp', value: fmt(d.sp_value) },
  ]
})

function fmt(v: any, digits = 2): string {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  if (digits === 0) return String(Math.round(n))
  return n.toFixed(digits)
}

function boardHref(kind: 'industry' | 'concept', row: any): string {
  return boardDetailUrl({
    boardKind: kind,
    boardCode: String(row?.board_code || ''),
    boardName: String(row?.board_name || ''),
    boardCodeSource: 'tonghuashun',
  })
}

function applyData(d: any) {
  data.value = d
  viewpoint.value = d?.viewpoint_md || ''
  advice.value = d?.advice_md || ''
  markdown.value = d?.markdown || ''
}

async function load() {
  if (!tradeDate.value) return
  loading.value = true
  status.value = '加载中…'
  try {
    const res = await getDailyReview(tradeDate.value)
    if (!res.success || !res.data) {
      status.value = res.message || '暂无快照，请重算'
      data.value = null
      return
    }
    applyData(res.data)
    status.value = `已加载 ${tradeDate.value}`
  } catch (e: any) {
    status.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function compute() {
  if (!tradeDate.value) return
  loading.value = true
  status.value = '重算中…'
  try {
    const res = await computeDailyReview(tradeDate.value, true)
    if (!res.success) {
      ElMessage.error(res.message || '重算失败')
      status.value = res.message || '重算失败'
      return
    }
    applyData(res.data)
    status.value = `重算完成 · ${res.data?.limit_source || ''} · ${res.data?.season || ''}`
    ElMessage.success('复盘重算完成')
  } catch (e: any) {
    status.value = e?.message || '重算失败'
    ElMessage.error(status.value)
  } finally {
    loading.value = false
  }
}

async function collectZt() {
  if (!tradeDate.value) return
  loading.value = true
  try {
    const res = await collectZtPool(tradeDate.value)
    if (res.success) {
      ElMessage.success(`涨停池写入 ${res.written ?? 0} 条`)
      status.value = `涨停池 OK written=${res.written}`
    } else {
      ElMessage.warning(res.error || res.message || '采集失败（可回退代理口径）')
      status.value = res.error || res.message || '涨停池采集失败'
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '采集异常')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!tradeDate.value) return
  loading.value = true
  try {
    const res = await saveDailyReviewText(tradeDate.value, {
      viewpoint_md: viewpoint.value,
      advice_md: advice.value,
    })
    if (!res.success) {
      ElMessage.error(res.message || '保存失败')
      return
    }
    applyData(res.data)
    ElMessage.success('已保存')
    status.value = '观点/建议已保存'
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    loading.value = false
  }
}

async function exportMd() {
  if (!tradeDate.value) return
  loading.value = true
  try {
    const res = await exportDailyReviewMd(tradeDate.value)
    if (!res.success) {
      ElMessage.error(res.message || '导出失败')
      return
    }
    if (res.markdown) markdown.value = res.markdown
    ElMessage.success(res.path ? `已导出 ${res.path}` : '已导出')
    status.value = res.path || '导出完成'
  } catch (e: any) {
    ElMessage.error(e?.message || '导出失败')
  } finally {
    loading.value = false
  }
}

async function exportPdf() {
  if (!tradeDate.value) return
  loading.value = true
  status.value = '正在生成 PDF…'
  try {
    const res = await exportDailyReviewPdf(tradeDate.value)
    if (!res.ok) {
      ElMessage.error(res.message || 'PDF 导出失败')
      status.value = res.message || 'PDF 导出失败'
      return
    }
    ElMessage.success(res.path ? `已导出 ${res.path}` : `已下载 ${res.filename}`)
    status.value = res.path || res.filename || 'PDF 导出完成'
  } catch (e: any) {
    ElMessage.error(e?.message || 'PDF 导出失败')
    status.value = e?.message || 'PDF 导出失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.daily-review-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.dr-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.dr-status {
  color: #64748b;
  font-size: 13px;
}
.dr-metrics {
  margin-top: 4px;
}
.dr-metric-card {
  margin-bottom: 8px;
}
.dr-metric-card .label {
  font-size: 12px;
  color: #64748b;
}
.dr-metric-card .value {
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}
.dr-block {
  margin-top: 4px;
}
.muted {
  color: #64748b;
  font-size: 13px;
}
.dr-md {
  white-space: pre-wrap;
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 8px;
  max-height: 420px;
  overflow: auto;
  font-size: 12px;
}
.dr-board-link {
  color: #1d4ed8;
  text-decoration: none;
  font-weight: 600;
}
.dr-board-link:hover {
  text-decoration: underline;
  color: #1e40af;
}
</style>
