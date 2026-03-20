<template>
  <div class="email-logs-view">
    <el-card>
      <template #header>
        <span>报告发送日志</span>
      </template>
      <el-form :inline="true" class="filter-form">
        <el-form-item label="用户">
          <el-select
            v-model="filters.user_id"
            placeholder="全部"
            clearable
            filterable
            style="width: 160px;"
          >
            <el-option
              v-for="u in userOptions"
              :key="u.id"
              :label="u.username"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker
            v-model="filters.start_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            clearable
            style="width: 160px;"
          />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="filters.end_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            clearable
            style="width: 160px;"
          />
        </el-form-item>
        <el-form-item label="发送结果">
          <el-select v-model="filters.success" placeholder="全部" clearable style="width: 100px;">
            <el-option label="成功" :value="true" />
            <el-option label="失败" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="query">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="logs" v-loading="loading" border stripe>
        <el-table-column prop="sent_at" label="发送时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.sent_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="100" />
        <el-table-column prop="to_email" label="收件邮箱" min-width="180" />
        <el-table-column prop="subject" label="主题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="report_type" label="报告类型" width="120">
          <template #default="{ row }">
            {{ reportTypeLabel(row.report_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="success" label="结果" width="80">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="失败原因" min-width="180" show-overflow-tooltip />
      </el-table>
      <div class="pagination-section">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="query"
          @current-change="query"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { pushService } from '@/services/push.service'
import { usersService } from '@/services/users.service'
import type { EmailSendLogResponse } from '@/services/push.service'
import type { User } from '@/types/users.types'

const REPORT_TYPE_LABELS: Record<string, string> = {
  summary: '汇总报告',
  detailed: '详细报告',
  gms_daily: '自选股GSM策略指标信号列表'
}

const loading = ref(false)
const logs = ref<EmailSendLogResponse[]>([])
const userOptions = ref<User[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

const filters = reactive<{
  user_id?: number
  start_date?: string
  end_date?: string
  success?: boolean
}>({
  user_id: undefined,
  start_date: undefined,
  end_date: undefined,
  success: undefined
})

function formatTime(v: string | undefined) {
  if (!v) return '-'
  return v.replace('T', ' ').slice(0, 19)
}

function reportTypeLabel(t: string) {
  return REPORT_TYPE_LABELS[t] ?? t
}

async function loadUserOptions() {
  try {
    const res = await usersService.getUsers(1, 500)
    userOptions.value = res.data ?? []
  } catch {
    userOptions.value = []
  }
}

async function query() {
  loading.value = true
  try {
    const list = await pushService.getEmailLogs({
      user_id: filters.user_id,
      start_date: filters.start_date,
      end_date: filters.end_date,
      success: filters.success,
      limit: pageSize.value,
      offset: (currentPage.value - 1) * pageSize.value
    })
    logs.value = list
    if (list.length < pageSize.value) {
      total.value = (currentPage.value - 1) * pageSize.value + list.length
    } else {
      total.value = currentPage.value * pageSize.value + 1
    }
  } catch (e: unknown) {
    const msg = e && typeof e === 'object' && 'response' in e
      ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : String(e)
    ElMessage.error('查询失败：' + msg)
    logs.value = []
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.user_id = undefined
  filters.start_date = undefined
  filters.end_date = undefined
  filters.success = undefined
  currentPage.value = 1
  query()
}

onMounted(() => {
  loadUserOptions()
  query()
})
</script>

<style scoped>
.email-logs-view {
  padding: 0;
}
.filter-form {
  margin-bottom: 16px;
}
.pagination-section {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
