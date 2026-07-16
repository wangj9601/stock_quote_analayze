<template>
  <div class="sbbr-management">
    <div class="page-header">
      <h1 class="page-title">做小做底（SBBR）管理</h1>
      <p class="page-subtitle">参数版本 · 回测任务 · 手动预计算</p>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="策略配置" name="config">
        <div class="toolbar">
          <el-button type="primary" @click="loadConfigs">刷新</el-button>
          <el-button @click="showCreate = true">新建版本</el-button>
          <el-button type="warning" :loading="precomputing" @click="onPrecompute">手动预计算</el-button>
        </div>
        <el-table :data="configs" stripe v-loading="loadingConfigs">
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="name" label="名称" width="160" />
          <el-table-column prop="description" label="说明" />
          <el-table-column label="默认" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.is_default" type="success">是</el-tag>
              <el-button v-else link type="primary" @click="onSetDefault(row.id)">设为默认</el-button>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEdit(row)">编辑 JSON</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="回测任务" name="backtest">
        <div class="toolbar">
          <el-button type="primary" @click="loadBacktests">刷新</el-button>
          <el-button type="success" @click="showBt = true">创建回测</el-button>
        </div>
        <el-table :data="backtests" stripe v-loading="loadingBt">
          <el-table-column prop="task_id" label="任务ID" min-width="220" />
          <el-table-column prop="name" label="名称" width="160" />
          <el-table-column prop="backtest_type" label="类型" width="140" />
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column prop="progress" label="进度" width="80" />
          <el-table-column prop="created_at" label="创建时间" width="180" />
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button link type="primary" @click="viewBt(row.task_id)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="showCreate" title="新建配置版本" width="640px">
      <el-form label-width="100px">
        <el-form-item label="名称"><el-input v-model="createForm.name" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="createForm.description" /></el-form-item>
        <el-form-item label="设为默认"><el-switch v-model="createForm.set_default" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="onCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showEdit" title="编辑 config_params" width="720px">
      <el-input v-model="editJson" type="textarea" :rows="18" />
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" @click="onSaveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showBt" title="创建回测" width="560px">
      <el-form label-width="120px">
        <el-form-item label="任务名"><el-input v-model="btForm.task_name" /></el-form-item>
        <el-form-item label="开始日"><el-input v-model="btForm.start_date" placeholder="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日"><el-input v-model="btForm.end_date" placeholder="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="btForm.backtest_type">
            <el-option label="命中率 signal_hit_rate" value="signal_hit_rate" />
            <el-option label="交易模拟 trade_simulation" value="trade_simulation" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标涨幅"><el-input-number v-model="btForm.target_pct" :min="0.1" :max="2" :step="0.1" /></el-form-item>
        <el-form-item label="持有天数"><el-input-number v-model="btForm.horizon_days" :min="5" :max="120" /></el-form-item>
        <el-form-item label="宇宙上限"><el-input-number v-model="btForm.universe_limit" :min="10" :max="500" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBt = false">取消</el-button>
        <el-button type="primary" @click="onCreateBt">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showDetail" title="回测详情" width="720px">
      <pre class="json-pre">{{ detailText }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import sbbrApi from '@/services/sbbrApi'

const activeTab = ref('config')
const configs = ref<any[]>([])
const backtests = ref<any[]>([])
const loadingConfigs = ref(false)
const loadingBt = ref(false)
const precomputing = ref(false)
const showCreate = ref(false)
const showEdit = ref(false)
const showBt = ref(false)
const showDetail = ref(false)
const editId = ref<number | null>(null)
const editJson = ref('')
const detailText = ref('')

const createForm = reactive({ name: '', description: '', set_default: false })
const btForm = reactive({
  task_name: 'sbbr-bt',
  start_date: '',
  end_date: '',
  backtest_type: 'signal_hit_rate',
  target_pct: 0.5,
  horizon_days: 60,
  universe_limit: 50,
  date_step: 5,
})

async function loadConfigs() {
  loadingConfigs.value = true
  try {
    const { data } = await sbbrApi.listConfigs()
    configs.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '加载配置失败')
  } finally {
    loadingConfigs.value = false
  }
}

async function loadBacktests() {
  loadingBt.value = true
  try {
    const { data } = await sbbrApi.listBacktests()
    backtests.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message || '加载回测失败')
  } finally {
    loadingBt.value = false
  }
}

async function onCreate() {
  try {
    await sbbrApi.createConfig({ ...createForm })
    showCreate.value = false
    createForm.name = ''
    createForm.description = ''
    createForm.set_default = false
    ElMessage.success('已创建')
    await loadConfigs()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message)
  }
}

function openEdit(row: any) {
  editId.value = row.id
  editJson.value = JSON.stringify(row.config_params || {}, null, 2)
  showEdit.value = true
}

async function onSaveEdit() {
  if (editId.value == null) return
  try {
    const params = JSON.parse(editJson.value)
    await sbbrApi.updateConfig(editId.value, { config_params: params })
    showEdit.value = false
    ElMessage.success('已保存')
    await loadConfigs()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  }
}

async function onSetDefault(id: number) {
  await sbbrApi.setDefault(id)
  ElMessage.success('已设为默认')
  await loadConfigs()
}

async function onPrecompute() {
  precomputing.value = true
  try {
    const { data } = await sbbrApi.triggerPrecompute()
    ElMessage.success(`预计算完成 screened=${data.screened ?? '-'} entry=${data.entry_count ?? '-'}`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message)
  } finally {
    precomputing.value = false
  }
}

async function onCreateBt() {
  try {
    const { data } = await sbbrApi.createBacktest({ ...btForm })
    showBt.value = false
    ElMessage.success(`已创建任务 ${data.task_id}`)
    activeTab.value = 'backtest'
    await loadBacktests()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e.message)
  }
}

async function viewBt(taskId: string) {
  const { data } = await sbbrApi.getBacktest(taskId)
  detailText.value = JSON.stringify(data, null, 2)
  showDetail.value = true
}

onMounted(() => {
  loadConfigs()
  loadBacktests()
})
</script>

<style scoped>
.sbbr-management { padding: 16px; }
.page-header { margin-bottom: 16px; }
.page-title { margin: 0; font-size: 22px; }
.page-subtitle { margin: 4px 0 0; color: #666; }
.toolbar { margin-bottom: 12px; display: flex; gap: 8px; }
.json-pre {
  max-height: 480px;
  overflow: auto;
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 8px;
  font-size: 12px;
}
</style>
