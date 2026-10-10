<template>
  <div class="login-logs-view">
    <el-card shadow="never" class="login-logs-card">
      <el-form :inline="true" class="filter-form">
        <el-form-item label="渠道">
          <el-select v-model="filters.channel" placeholder="全部" clearable style="width: 120px">
            <el-option label="网站用户" value="user" />
            <el-option label="管理端" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="用户名">
          <el-input
            v-model="filters.username"
            placeholder="模糊匹配"
            clearable
            style="width: 140px"
            @keyup.enter="onSearch"
          />
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker
            v-model="filters.start_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            clearable
            style="width: 160px"
          />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="filters.end_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            clearable
            style="width: 160px"
          />
        </el-form-item>
        <el-form-item label="结果">
          <el-select v-model="filters.success" placeholder="全部" clearable style="width: 100px">
            <el-option label="成功" :value="true" />
            <el-option label="失败" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSearch">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="logs" v-loading="loading" border stripe>
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="channel" label="渠道" width="100">
          <template #default="{ row }">
            {{ row.channel === 'admin' ? '管理端' : '网站用户' }}
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="user_id" label="用户ID" width="90">
          <template #default="{ row }">
            {{ row.user_id ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="success" label="结果" width="80">
          <template #default="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'" size="small">
              {{ row.success ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" width="130" show-overflow-tooltip />
        <el-table-column prop="failure_reason" label="失败原因" min-width="140" show-overflow-tooltip />
        <el-table-column prop="user_agent" label="User-Agent" min-width="200" show-overflow-tooltip />
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
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { loginLogsService, type LoginLogItem } from '@/services/loginLogs.service'

const loading = ref(false)
const logs = ref<LoginLogItem[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

const filters = reactive<{
  channel?: string
  username?: string
  start_date?: string
  end_date?: string
  success?: boolean
}>({
  channel: undefined,
  username: undefined,
  start_date: undefined,
  end_date: undefined,
  success: undefined,
})

function formatTime(v: string | null | undefined) {
  if (!v) return '-'
  return v.replace('T', ' ').slice(0, 19)
}

async function query() {
  loading.value = true
  try {
    const res = await loginLogsService.query({
      channel: filters.channel,
      username: filters.username || undefined,
      start_date: filters.start_date,
      end_date: filters.end_date,
      success: filters.success,
      page: currentPage.value,
      page_size: pageSize.value,
    })
    logs.value = res.items ?? []
    total.value = res.total ?? 0
  } catch (e: unknown) {
    const msg =
      e && typeof e === 'object' && 'response' in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : String(e)
    ElMessage.error('查询失败：' + (msg || '未知错误'))
    logs.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function onSearch() {
  currentPage.value = 1
  query()
}

function resetFilters() {
  filters.channel = undefined
  filters.username = undefined
  filters.start_date = undefined
  filters.end_date = undefined
  filters.success = undefined
  currentPage.value = 1
  query()
}

onMounted(() => {
  query()
})
</script>

<style scoped>
.login-logs-view {
  padding: 0;
}
.login-logs-card {
  border: none;
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
