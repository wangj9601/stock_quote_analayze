<template>
  <div class="recommend-admin">
    <div class="page-header">
      <div>
        <h2>策略推荐</h2>
        <p class="subtitle">日终简报重跑、asof 历史核对、Excel/PDF 导出与纸面 KPI</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openRerun">重跑生成</el-button>
        <el-button @click="loadBrief">刷新</el-button>
        <el-button type="success" @click="exportXlsx">导出 Excel</el-button>
        <el-button @click="exportPdf">导出 PDF</el-button>
      </div>
    </div>

    <el-form :inline="true" class="toolbar">
      <el-form-item label="周期">
        <el-select v-model="horizon" style="width: 140px" @change="onHorizonChange">
          <el-option label="每日" value="daily" />
          <el-option label="每周" value="weekly" />
          <el-option label="每月" value="monthly" />
        </el-select>
      </el-form-item>
      <el-form-item label="asof">
        <el-select v-model="asofDate" clearable filterable style="width: 180px" @change="loadBrief">
          <el-option v-for="d in asofDates" :key="d" :label="d" :value="d" />
        </el-select>
      </el-form-item>
      <el-form-item label="触达买区 KPI">
        <el-button size="small" @click="loadTouchKpi">计算</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="12" class="cards">
      <el-col :span="6">
        <el-card shadow="never"><div class="metric">{{ brief?.market_stance || '-' }}</div><div class="label">大盘立场</div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><div class="metric">{{ execCount }}</div><div class="label">可执行</div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><div class="metric">{{ watchCount }}</div><div class="label">观察</div></el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never"><div class="metric">{{ kpiText }}</div><div class="label">板上 HHI / 触达率</div></el-card>
      </el-col>
    </el-row>

    <el-alert
      v-if="brief?.summary?.disclaimer"
      :title="brief.summary.disclaimer"
      type="info"
      :closable="false"
      show-icon
      class="mb"
    />

    <el-table :data="items" stripe border height="520" v-loading="loading">
      <el-table-column prop="code" label="代码" width="90" />
      <el-table-column prop="name" label="名称" width="100" />
      <el-table-column prop="stance" label="立场" width="90" />
      <el-table-column prop="role_label" label="角色" width="80" />
      <el-table-column prop="primary_strategy" label="主策略" width="90" />
      <el-table-column label="共振" width="120">
        <template #default="{ row }">{{ (row.strategies || []).join(',') }}</template>
      </el-table-column>
      <el-table-column label="行业" min-width="120">
        <template #default="{ row }">{{ row.industry || row.board_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="推荐分" min-width="200">
        <template #default="{ row }">
          <div>{{ row.recommend_score ?? '-' }}</div>
          <div v-if="scoreDetailText(row)" class="score-detail">{{ scoreDetailText(row) }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="summary" label="摘要" min-width="200" show-overflow-tooltip />
    </el-table>

    <el-dialog v-model="rerunVisible" title="重跑推荐简报" width="480px">
      <el-form label-width="110px">
        <el-form-item label="asof 日期">
          <el-date-picker v-model="rerunForm.asof_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="late_run">
          <el-switch v-model="rerunForm.late_run" />
        </el-form-item>
        <el-form-item label="强制周报">
          <el-switch v-model="rerunForm.force_weekly" />
        </el-form-item>
        <el-form-item label="强制月报">
          <el-switch v-model="rerunForm.force_monthly" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rerunVisible = false">取消</el-button>
        <el-button type="primary" :loading="rerunning" @click="doRerun">执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiService } from '@/services/api'

const PREFIX = '/recommend'

const horizon = ref('daily')
const asofDate = ref<string | undefined>()
const asofDates = ref<string[]>([])
const brief = ref<any>(null)
const loading = ref(false)
const rerunVisible = ref(false)
const rerunning = ref(false)
const touchRate = ref<number | null>(null)
const rerunForm = reactive({
  asof_date: '' as string,
  late_run: false,
  force_weekly: false,
  force_monthly: false,
})

const items = computed(() => (brief.value?.items as any[]) || [])
const execCount = computed(() => items.value.filter((x) => x.action === 'buy').length)
const watchCount = computed(() => items.value.filter((x) => x.action !== 'buy').length)
const kpiText = computed(() => {
  const hhi = brief.value?.kpi?.board_hhi
  const tr = touchRate.value
  const a = hhi != null ? `HHI ${hhi}` : 'HHI -'
  const b = tr != null ? `触达 ${(tr * 100).toFixed(1)}%` : '触达 -'
  return `${a} / ${b}`
})

function errDetail(e: any): string {
  return e?.response?.data?.detail || e?.message || '请求失败'
}

function scoreDetailText(row: any): string {
  const d = row?.score_detail
  if (!d || typeof d !== 'object') return ''
  const parts: string[] = []
  if (d.resonance != null) parts.push(`共振 ${d.resonance}（${d.resonance_note || '命中×10'}）`)
  if (d.quality != null) parts.push(`质量 ${d.quality}（${d.quality_note || 'min(分,100)×0.3'}）`)
  if (d.action_bonus != null) parts.push(`立场 ${d.action_bonus}（${d.action_note || ''}）`)
  if (d.role_bonus != null) parts.push(`角色 ${d.role_bonus}（${d.role_note || ''}）`)
  if (d.note) parts.push(d.note)
  return parts.join('；')
}

async function loadAsOf() {
  try {
    // apiService 已解包 response.data
    const data = await apiService.get<{ success?: boolean; data?: string[] }>(
      `${PREFIX}/asof-dates`,
      { params: { horizon: horizon.value, limit: 90 } }
    )
    asofDates.value = data?.data || []
    if (!asofDate.value && asofDates.value.length) {
      asofDate.value = asofDates.value[0]
    }
  } catch (e: any) {
    asofDates.value = []
    if (e?.response?.status !== 401) {
      ElMessage.error(errDetail(e) || '加载 asof 列表失败')
    }
  }
}

async function loadBrief() {
  loading.value = true
  try {
    const data = await apiService.get<{ success?: boolean; data?: any }>(
      `${PREFIX}/brief`,
      { params: { horizon: horizon.value, asof_date: asofDate.value || undefined } }
    )
    brief.value = data?.data || null
    if (brief.value?.asof_date) asofDate.value = brief.value.asof_date
  } catch (e: any) {
    brief.value = null
    if (e?.response?.status !== 404 && e?.response?.status !== 401) {
      ElMessage.error(errDetail(e) || '加载失败')
    }
  } finally {
    loading.value = false
  }
}

async function onHorizonChange() {
  asofDate.value = undefined
  touchRate.value = null
  await loadAsOf()
  await loadBrief()
}

function openRerun() {
  rerunForm.asof_date = asofDate.value || ''
  rerunVisible.value = true
}

async function doRerun() {
  rerunning.value = true
  try {
    const data = await apiService.post<{ success?: boolean; data?: any }>(
      `${PREFIX}/rerun`,
      {
        asof_date: rerunForm.asof_date || null,
        late_run: rerunForm.late_run,
        force_weekly: rerunForm.force_weekly,
        force_monthly: rerunForm.force_monthly,
      }
    )
    ElMessage.success('重跑完成')
    rerunVisible.value = false
    await loadAsOf()
    if (data?.data?.asof_date) asofDate.value = data.data.asof_date
    await loadBrief()
  } catch (e: any) {
    ElMessage.error(errDetail(e) || '重跑失败')
  } finally {
    rerunning.value = false
  }
}

async function exportXlsx() {
  try {
    const blob = await apiService.get<Blob>(`${PREFIX}/export/xlsx`, {
      params: { horizon: horizon.value, asof_date: asofDate.value || undefined },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `recommend_${horizon.value}_${asofDate.value || 'latest'}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    ElMessage.error(errDetail(e) || 'Excel 导出失败')
  }
}

async function exportPdf() {
  try {
    const blob = await apiService.get<Blob>(`${PREFIX}/export/pdf`, {
      params: { horizon: horizon.value, asof_date: asofDate.value || undefined },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `recommend_${horizon.value}_${asofDate.value || 'latest'}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('PDF 导出失败（需 reportlab 与中文字体）')
  }
}

async function loadTouchKpi() {
  if (!asofDate.value) {
    ElMessage.warning('请先选择 asof')
    return
  }
  try {
    const data = await apiService.get<{ success?: boolean; data?: any }>(
      `${PREFIX}/kpi/touch-rate`,
      {
        params: {
          asof_date: asofDate.value,
          horizon: horizon.value,
          forward_days: 3,
        },
      }
    )
    touchRate.value = data?.data?.touch_rate ?? null
    ElMessage.success(`样本 ${data?.data?.sample ?? 0}，触达 ${data?.data?.touched ?? 0}`)
  } catch (e: any) {
    ElMessage.error(errDetail(e) || 'KPI 计算失败')
  }
}

onMounted(async () => {
  try {
    await loadAsOf()
    await loadBrief()
  } catch (e) {
    console.error(e)
  }
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.subtitle {
  color: #888;
  margin: 4px 0 0;
}
.header-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.cards {
  margin-bottom: 12px;
}
.metric {
  font-size: 22px;
  font-weight: 600;
}
.label {
  color: #888;
  margin-top: 4px;
}
.mb {
  margin-bottom: 12px;
}
.toolbar {
  margin-bottom: 8px;
}
.score-detail {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.35;
  white-space: normal;
}
</style>
