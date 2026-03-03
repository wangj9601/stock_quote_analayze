<template>
  <div class="push-config-view">
    <el-card>
      <template #header>
        <span>邮件推送配置</span>
        <el-button type="primary" style="float: right;" :loading="loading" @click="loadConfigs">
          刷新
        </el-button>
      </template>
      <el-table :data="displayList" v-loading="loading" border stripe>
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="enabled" label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="channels" label="渠道" width="120">
          <template #default="{ row }">
            {{ (row.channels || []).join('、') || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="push_times" label="推送时间" width="140">
          <template #default="{ row }">
            {{ (row.push_times || []).join('、') || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="report_type_label" label="报告类型" width="160" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-section">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadConfigs"
          @current-change="loadConfigs"
        />
      </div>
    </el-card>

    <el-dialog v-model="editVisible" title="编辑推送配置" width="480px" @close="resetEditForm">
      <el-form ref="editFormRef" :model="editForm" label-width="100px">
        <el-form-item label="用户名">
          <el-input :model-value="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="启用推送">
          <el-switch v-model="editForm.enabled" />
        </el-form-item>
        <el-form-item label="渠道">
          <el-checkbox-group v-model="editForm.channels">
            <el-checkbox label="email">邮件</el-checkbox>
            <el-checkbox label="wechat">微信</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="推送时间">
          <el-select
            v-model="editForm.push_times"
            multiple
            placeholder="选择推送时间"
            style="width: 100%;"
          >
            <el-option label="08:00" value="08:00" />
            <el-option label="09:00" value="09:00" />
            <el-option label="10:00" value="10:00" />
            <el-option label="11:00" value="11:00" />
            <el-option label="12:00" value="12:00" />
            <el-option label="15:00" value="15:00" />
            <el-option label="16:00" value="16:00" />
            <el-option label="17:00" value="17:00" />
            <el-option label="18:00" value="18:00" />
          </el-select>
        </el-form-item>
        <el-form-item label="报告类型">
          <el-select v-model="editForm.report_type" placeholder="请选择" style="width: 100%;">
            <el-option label="汇总报告" value="summary" />
            <el-option label="详细报告" value="detailed" />
            <el-option label="GMS自选股选股" value="gms_daily" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitEdit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { pushService } from '@/services/push.service'
import { usersService } from '@/services/users.service'
import type { UserPushConfigResponse } from '@/services/push.service'
import type { User } from '@/types/users.types'

const REPORT_TYPE_LABELS: Record<string, string> = {
  summary: '汇总报告',
  detailed: '详细报告',
  gms_daily: 'GMS自选股选股'
}

const loading = ref(false)
const submitLoading = ref(false)
const editVisible = ref(false)
const editFormRef = ref()
const configs = ref<UserPushConfigResponse[]>([])
const userMap = ref<Record<number, User>>({})
const currentPage = ref(1)
const pageSize = ref(20)

const total = computed(() => configs.value.length)
const displayList = computed(() => {
  const list = configs.value.map((c) => {
    const u = userMap.value[c.user_id]
    return {
      ...c,
      username: u?.username ?? `用户${c.user_id}`,
      email: u?.email ?? '-',
      report_type_label: REPORT_TYPE_LABELS[c.report_type] ?? c.report_type
    }
  })
  const start = (currentPage.value - 1) * pageSize.value
  return list.slice(start, start + pageSize.value)
})

const editForm = ref({
  user_id: 0,
  username: '',
  enabled: true,
  channels: [] as string[],
  push_times: [] as string[],
  report_type: 'summary'
})

async function loadConfigs() {
  loading.value = true
  try {
    const [configList, userRes] = await Promise.all([
      pushService.getAllPushConfigs(500, 0),
      usersService.getUsers(1, 500)
    ])
    configs.value = configList
    const map: Record<number, User> = {}
    ;(userRes.data || []).forEach((u: User) => { map[u.id] = u })
    userMap.value = map
  } catch (e: unknown) {
    const msg = e && typeof e === 'object' && 'response' in e
      ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : String(e)
    ElMessage.error('加载失败：' + msg)
  } finally {
    loading.value = false
  }
}

function openEdit(row: { user_id: number; username?: string; enabled: boolean; channels: string[]; push_times: string[]; report_type: string }) {
  editForm.value = {
    user_id: row.user_id,
    username: row.username ?? '',
    enabled: row.enabled,
    channels: Array.isArray(row.channels) ? [...row.channels] : [],
    push_times: Array.isArray(row.push_times) ? [...row.push_times] : [],
    report_type: row.report_type || 'summary'
  }
  editVisible.value = true
}

function resetEditForm() {
  editForm.value = {
    user_id: 0,
    username: '',
    enabled: true,
    channels: [],
    push_times: [],
    report_type: 'summary'
  }
}

async function submitEdit() {
  submitLoading.value = true
  try {
    await pushService.adminUpdatePushConfig(editForm.value.user_id, {
      enabled: editForm.value.enabled,
      channels: editForm.value.channels,
      push_times: editForm.value.push_times,
      report_type: editForm.value.report_type
    })
    ElMessage.success('保存成功')
    editVisible.value = false
    await loadConfigs()
  } catch (e: unknown) {
    const msg = e && typeof e === 'object' && 'response' in e
      ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : String(e)
    ElMessage.error('保存失败：' + msg)
  } finally {
    submitLoading.value = false
  }
}

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped>
.push-config-view {
  padding: 0;
}
.pagination-section {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
