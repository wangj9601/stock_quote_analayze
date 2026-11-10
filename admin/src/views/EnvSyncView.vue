<template>
  <div class="env-sync-view">
    <el-card class="mb-3">
      <template #header>
        <div class="card-head">
          <span>环境数据同步</span>
          <el-tag type="info" size="small">策略/观察/行情/资金流·两融/预计算复盘/财务/权限</el-tag>
        </div>
      </template>
      <p class="hint">
        本地发起 Pull（从生产拉取并写入本地）或 Push（导出本地写入生产）。生产端维护 Sync Key 并校验；
        管理端只调本地包装接口，Key 不由浏览器直连生产。行情、资金流与预计算/复盘数据量大，勾选后必须指定日期范围；
        同步策略信号前建议先同步对应策略配置。大体量请用「异步 Pull / 异步 Push」（落盘分片，避免 Nginx 502）；
        原同步按钮仍保留给小数据。
      </p>
    </el-card>

    <el-row :gutter="16">
      <el-col :xs="24" :sm="24" :md="12">
        <el-card v-loading="loadingClient">
          <template #header>客户端配置（本地 → 生产）</template>
          <el-form label-width="120px" class="env-sync-form">
            <el-form-item label="启用">
              <el-switch v-model="clientForm.enabled" />
            </el-form-item>
            <el-form-item label="生产 Base URL">
              <el-input
                v-model="clientForm.prod_base_url"
                placeholder="例如 https://www.icemaplecity.com 或 http://IP:5000"
              />
            </el-form-item>
            <el-form-item label="Sync Key">
              <el-input
                v-model="clientForm.sync_key"
                type="password"
                show-password
                placeholder="留空则不修改已保存密钥"
              />
              <div class="sub-hint" v-if="clientMeta.sync_key_masked">
                当前：{{ clientMeta.sync_key_masked }}
              </div>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="savingClient" @click="saveClient">保存</el-button>
              <el-button :loading="testing" @click="testConn">测试连通</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="24" :md="12">
        <el-card v-loading="loadingServer">
          <template #header>服务端 Sync Key（本机作为被同步方）</template>
          <el-form label-width="120px" class="env-sync-form">
            <el-form-item label="启用校验">
              <el-switch v-model="serverForm.enabled" @change="saveServerEnabled" />
            </el-form-item>
            <el-form-item label="Key 列表">
              <span class="sub-hint">
                {{
                  serverKeys.length
                    ? `共 ${serverKeys.length} 把，任一启用中的 Key 均可通过校验`
                    : '尚未配置'
                }}
              </span>
            </el-form-item>
            <el-table :data="serverKeys" size="small" empty-text="暂无 Key" class="server-keys-table">
              <el-table-column prop="label" label="备注" min-width="90">
                <template #default="{ row }">
                  <span>{{ row.label || '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="key_hint" label="提示" min-width="100" />
              <el-table-column label="启用" width="72" align="center">
                <template #default="{ row }">
                  <el-switch
                    :model-value="row.enabled"
                    :loading="togglingKeyId === row.id"
                    @change="(v: boolean | string | number) => toggleServerKey(row, !!v)"
                  />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="72" align="center">
                <template #default="{ row }">
                  <el-button
                    link
                    type="danger"
                    :loading="deletingKeyId === row.id"
                    @click="removeServerKey(row)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-form-item label="备注" class="mt-2">
              <el-input v-model="newKeyLabel" placeholder="可选，如：本机开发 / 办公机" maxlength="100" />
            </el-form-item>
            <el-form-item label="粘贴 Key">
              <el-input
                v-model="serverForm.sync_key"
                type="password"
                show-password
                placeholder="可选：粘贴已有 Key；留空则自动生成"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="addingKey" @click="addServerKey">
                添加 Key
              </el-button>
              <el-button type="warning" :loading="addingKey" @click="generateServerKey">
                生成并添加
              </el-button>
            </el-form-item>
            <el-alert
              v-if="rotatedKey"
              type="success"
              :closable="true"
              show-icon
              title="请立即复制明文 Key（仅展示一次）"
              :description="rotatedKey"
              class="mt-2"
              @close="rotatedKey = ''"
            />
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="mt-3">
      <template #header>
        <div class="card-head">
          <span>同步操作</span>
          <div class="head-actions">
            <el-button link type="primary" @click="selectDefault">默认（策略+观察）</el-button>
            <el-button link type="primary" @click="selectAll">全选</el-button>
            <el-button link @click="clearAll">清空</el-button>
          </div>
        </div>
      </template>
      <el-form label-width="100px">
        <el-form-item label="数据项">
          <div class="module-groups">
            <div v-for="g in moduleGroups" :key="g.group" class="module-group">
              <div class="group-title">
                <el-checkbox
                  :model-value="isGroupChecked(g)"
                  :indeterminate="isGroupIndeterminate(g)"
                  @change="(v: boolean | string | number) => toggleGroup(g, !!v)"
                >
                  {{ g.group_name }}
                  <el-tag v-if="g.requires_date_range" size="small" type="warning" class="ml-tag">
                    须日期
                  </el-tag>
                  <el-tag
                    v-else-if="g.date_range_optional"
                    size="small"
                    type="info"
                    class="ml-tag"
                  >
                    日期可选/全库
                  </el-tag>
                </el-checkbox>
              </div>
              <el-checkbox-group v-model="selectedModules" class="group-items">
                <el-checkbox
                  v-for="m in g.items"
                  :key="m.code"
                  :label="m.code"
                >
                  {{ m.name }}
                </el-checkbox>
              </el-checkbox-group>
            </div>
          </div>
        </el-form-item>
        <el-form-item v-if="showDateRange" label="日期区间">
          <div class="date-row">
            <el-date-picker
              v-model="startDate"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="开始日期"
            />
            <span class="date-sep">至</span>
            <el-date-picker
              v-model="endDate"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="结束日期"
            />
            <span class="sub-hint inline">{{ dateRangeHint }}</span>
          </div>
        </el-form-item>
        <el-form-item>
          <el-button type="success" :loading="pulling" @click="confirmPull">从生产 Pull</el-button>
          <el-button type="danger" :loading="pushing" @click="confirmPush">Push 到生产</el-button>
          <el-button type="success" plain :loading="asyncPulling" @click="confirmAsyncPull">
            异步 Pull
          </el-button>
          <el-button type="danger" plain :loading="asyncPushing" @click="confirmAsyncPush">
            异步 Push
          </el-button>
        </el-form-item>
        <el-form-item v-if="jobProgressText">
          <el-alert
            :type="jobAlertType"
            :closable="false"
            show-icon
            :title="jobProgressTitle"
            :description="jobProgressText"
          />
          <el-button
            v-if="activeJobId && jobRunning"
            class="mt-2"
            size="small"
            @click="cancelActiveJob"
          >
            取消任务
          </el-button>
        </el-form-item>
      </el-form>
      <el-alert
        v-if="lastResultText"
        :type="lastOk ? 'success' : 'error'"
        :closable="true"
        show-icon
        class="mt-2"
        :title="lastOk ? '同步完成' : '同步失败'"
        :description="lastResultText"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { envSyncApi } from '@/services/envSyncApi'

type ModuleItem = {
  code: string
  name: string
  desc?: string
  requires_date_range?: boolean
  date_range_optional?: boolean
}
type ModuleGroup = {
  group: string
  group_name: string
  requires_date_range?: boolean
  date_range_optional?: boolean
  items: ModuleItem[]
}

const loadingClient = ref(false)
const loadingServer = ref(false)
const savingClient = ref(false)
const savingServer = ref(false)
const addingKey = ref(false)
const togglingKeyId = ref<number | null>(null)
const deletingKeyId = ref<number | null>(null)
const testing = ref(false)
const pulling = ref(false)
const pushing = ref(false)
const asyncPulling = ref(false)
const asyncPushing = ref(false)
const activeJobId = ref('')
const jobProgressTitle = ref('')
const jobProgressText = ref('')
const jobAlertType = ref<'info' | 'success' | 'warning' | 'error'>('info')
const jobRunning = ref(false)
let jobPollTimer: ReturnType<typeof setInterval> | null = null

function stopJobPoll() {
  if (jobPollTimer) {
    clearInterval(jobPollTimer)
    jobPollTimer = null
  }
  jobRunning.value = false
  asyncPulling.value = false
  asyncPushing.value = false
}

async function pollJobOnce(jobId: string) {
  const j = await envSyncApi.getJob(jobId)
  const pct = typeof j.progress === 'number' ? j.progress : 0
  jobProgressTitle.value = `任务 ${j.job_id.slice(0, 8)}… ${j.status} ${pct}%`
  jobProgressText.value = [
    `方向: ${j.direction}`,
    j.stage ? `阶段: ${j.stage}` : '',
    j.message || '',
    j.error_message ? `错误: ${j.error_message}` : '',
  ]
    .filter(Boolean)
    .join('\n')
  if (j.status === 'succeeded') {
    jobAlertType.value = 'success'
    stopJobPoll()
    lastOk.value = true
    lastResultText.value = jobProgressText.value
    ElMessage.success('异步任务完成')
  } else if (j.status === 'failed') {
    jobAlertType.value = 'error'
    stopJobPoll()
    lastOk.value = false
    lastResultText.value = j.error_message || jobProgressText.value
    ElMessage.error(j.error_message || '异步任务失败')
  } else {
    jobAlertType.value = 'info'
    jobRunning.value = true
  }
}

function startJobPoll(jobId: string) {
  stopJobPoll()
  activeJobId.value = jobId
  jobRunning.value = true
  jobAlertType.value = 'info'
  jobProgressTitle.value = `任务已创建 ${jobId.slice(0, 8)}…`
  jobProgressText.value = '等待进度…'
  void pollJobOnce(jobId)
  jobPollTimer = setInterval(() => {
    void pollJobOnce(jobId).catch((e: any) => {
      jobAlertType.value = 'error'
      jobProgressText.value = e.message || '轮询失败'
      stopJobPoll()
    })
  }, 2000)
}

async function cancelActiveJob() {
  if (!activeJobId.value) return
  try {
    await envSyncApi.cancelJob(activeJobId.value)
    ElMessage.success('已请求取消')
  } catch (e: any) {
    ElMessage.error(e.message || '取消失败')
  }
}
const rotatedKey = ref('')
const newKeyLabel = ref('')
const lastOk = ref(true)
const lastResultText = ref('')

type ServerKeyRow = {
  id: number
  label: string
  key_hint: string
  enabled: boolean
  created_at?: string | null
}

const clientForm = reactive({
  enabled: false,
  prod_base_url: '',
  sync_key: '',
})
const clientMeta = reactive({ sync_key_masked: '', has_key: false })

const serverForm = reactive({
  enabled: false,
  sync_key: '',
})
const serverKeys = ref<ServerKeyRow[]>([])

const moduleGroups = ref<ModuleGroup[]>([])
const selectedModules = ref<string[]>([])
const defaultResources = ref<string[]>([])
const dateRangeRequired = ref<string[]>([])
const dateRangeOptional = ref<string[]>([])
const startDate = ref<string>('')
const endDate = ref<string>('')

const quotesSelected = computed(() =>
  selectedModules.value.some((c) => dateRangeRequired.value.includes(c))
)
const adjSelected = computed(() =>
  selectedModules.value.some((c) => dateRangeOptional.value.includes(c))
)
const showDateRange = computed(() => quotesSelected.value || adjSelected.value)
const dateRangeHint = computed(() => {
  if (quotesSelected.value && adjSelected.value) {
    return '行情/资金流/预计算复盘必须填日期（默认≤366天）；同批时复权因子也按该区间。全库同步请单独勾选复权因子且不填日期。'
  }
  if (quotesSelected.value) {
    return '行情/资金流/预计算复盘必须填日期；跨度由 ENV_SYNC_*_MAX_DAYS 控制（默认 366 天）'
  }
  return '复权因子可不填=全库；填写则按 trade_date 过滤，跨度由 ENV_SYNC_ADJ_FACTOR_MAX_DAYS 控制（默认约 11 年）'
})

function allCodes(): string[] {
  return moduleGroups.value.flatMap((g) => g.items.map((i) => i.code))
}

function isGroupChecked(g: ModuleGroup): boolean {
  const codes = g.items.map((i) => i.code)
  return codes.length > 0 && codes.every((c) => selectedModules.value.includes(c))
}

function isGroupIndeterminate(g: ModuleGroup): boolean {
  const codes = g.items.map((i) => i.code)
  const n = codes.filter((c) => selectedModules.value.includes(c)).length
  return n > 0 && n < codes.length
}

function toggleGroup(g: ModuleGroup, checked: boolean) {
  const codes = g.items.map((i) => i.code)
  if (checked) {
    const set = new Set(selectedModules.value)
    codes.forEach((c) => set.add(c))
    selectedModules.value = Array.from(set)
  } else {
    selectedModules.value = selectedModules.value.filter((c) => !codes.includes(c))
  }
}

function selectDefault() {
  selectedModules.value = defaultResources.value.length
    ? [...defaultResources.value]
    : allCodes().filter((c) => !dateRangeRequired.value.includes(c) && !c.includes('board') && !c.includes('stock_basic'))
}

function selectAll() {
  selectedModules.value = allCodes()
}

function clearAll() {
  selectedModules.value = []
}

function assertDateRange(): boolean {
  const hasStart = !!startDate.value
  const hasEnd = !!endDate.value
  if (quotesSelected.value) {
    if (!hasStart || !hasEnd) {
      ElMessage.warning('勾选行情、资金流或预计算/复盘时必须填写开始/结束日期')
      return false
    }
  } else if (adjSelected.value && (hasStart || hasEnd) && !(hasStart && hasEnd)) {
    ElMessage.warning('复权因子若按区间同步，请同时填写开始与结束日期；都不填则为全库')
    return false
  }
  if (hasStart && hasEnd && startDate.value > endDate.value) {
    ElMessage.warning('开始日期不能晚于结束日期')
    return false
  }
  return true
}

function datePayload() {
  if (startDate.value && endDate.value) {
    return { start_date: startDate.value, end_date: endDate.value }
  }
  return undefined
}

function formatConfirmRange(): string {
  if (startDate.value && endDate.value) {
    return `\n日期区间：${startDate.value} ~ ${endDate.value}`
  }
  if (adjSelected.value && !quotesSelected.value) {
    return '\n复权因子：全库同步'
  }
  return ''
}

async function loadAll() {
  loadingClient.value = true
  loadingServer.value = true
  try {
    const [c, s, mods] = await Promise.all([
      envSyncApi.getClientConfig(),
      envSyncApi.getServerConfig(),
      envSyncApi.listModules(),
    ])
    clientForm.enabled = !!c.enabled
    clientForm.prod_base_url = c.prod_base_url || ''
    clientForm.sync_key = ''
    clientMeta.sync_key_masked = c.sync_key_masked || ''
    clientMeta.has_key = !!c.has_key

    serverForm.enabled = !!s.enabled
    serverForm.sync_key = ''
    serverKeys.value = (s.keys || []) as ServerKeyRow[]

    moduleGroups.value = (mods.groups || []) as ModuleGroup[]
    defaultResources.value = mods.default_resources || []
    dateRangeRequired.value = mods.date_range_required || [
      'historical_quotes',
      'historical_quotes_hk',
    ]
    dateRangeOptional.value = mods.date_range_optional || [
      'stock_adj_factor',
      'stock_fina_indicator',
    ]
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loadingClient.value = false
    loadingServer.value = false
  }
}

async function saveClient() {
  savingClient.value = true
  try {
    const body: any = {
      enabled: clientForm.enabled,
      prod_base_url: clientForm.prod_base_url,
    }
    if (clientForm.sync_key.trim()) body.sync_key = clientForm.sync_key.trim()
    const c = await envSyncApi.updateClientConfig(body)
    clientForm.sync_key = ''
    clientMeta.sync_key_masked = c.sync_key_masked || ''
    clientMeta.has_key = !!c.has_key
    ElMessage.success('客户端配置已保存')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingClient.value = false
  }
}

async function saveServerEnabled() {
  savingServer.value = true
  try {
    const s = await envSyncApi.updateServerConfig({ enabled: serverForm.enabled })
    serverForm.enabled = !!s.enabled
    serverKeys.value = (s.keys || serverKeys.value) as ServerKeyRow[]
    ElMessage.success(serverForm.enabled ? '已启用校验' : '已关闭校验')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
    await loadAll()
  } finally {
    savingServer.value = false
  }
}

function applyServerConfig(cfg: any) {
  if (!cfg) return
  serverForm.enabled = !!cfg.enabled
  if (Array.isArray(cfg.keys)) {
    serverKeys.value = cfg.keys as ServerKeyRow[]
  }
}

async function createKey(payload: { label?: string; sync_key?: string }) {
  addingKey.value = true
  try {
    const res = await envSyncApi.createServerKey(payload)
    rotatedKey.value = res.sync_key || ''
    applyServerConfig(res.config)
    serverForm.sync_key = ''
    newKeyLabel.value = ''
    ElMessage.success('已添加 Key，请复制明文后配置到客户端')
  } catch (e: any) {
    ElMessage.error(e.message || '添加失败')
  } finally {
    addingKey.value = false
  }
}

async function addServerKey() {
  const pasted = serverForm.sync_key.trim()
  if (!pasted) {
    ElMessage.warning('请粘贴已有 Key，或使用「生成并添加」')
    return
  }
  await createKey({ label: newKeyLabel.value.trim() || undefined, sync_key: pasted })
}

async function generateServerKey() {
  await createKey({ label: newKeyLabel.value.trim() || undefined })
}

async function toggleServerKey(row: ServerKeyRow, enabled: boolean) {
  togglingKeyId.value = row.id
  try {
    const res = await envSyncApi.updateServerKey(row.id, { enabled })
    applyServerConfig(res.config)
    if (res.key) {
      const idx = serverKeys.value.findIndex((k) => k.id === row.id)
      if (idx >= 0) serverKeys.value[idx] = { ...serverKeys.value[idx], ...res.key }
    }
  } catch (e: any) {
    ElMessage.error(e.message || '更新失败')
    await loadAll()
  } finally {
    togglingKeyId.value = null
  }
}

async function removeServerKey(row: ServerKeyRow) {
  try {
    await ElMessageBox.confirm(
      `确认删除 Key「${row.label || row.key_hint || row.id}」？删除后使用该 Key 的客户端将无法同步。`,
      '删除 Sync Key',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  deletingKeyId.value = row.id
  try {
    const cfg = await envSyncApi.deleteServerKey(row.id)
    applyServerConfig(cfg)
    ElMessage.success('已删除')
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  } finally {
    deletingKeyId.value = null
  }
}

async function testConn() {
  testing.value = true
  try {
    const res = await envSyncApi.testConnection()
    ElMessage.success(res.message || '连通成功')
  } catch (e: any) {
    ElMessage.error(e.message || '连通失败')
  } finally {
    testing.value = false
  }
}

function summarize(res: any): string {
  const results = res?.results || {}
  const lines: string[] = []
  if (res?.date_range) {
    if (res.date_range.mode === 'full') {
      lines.push('date_range: full（全库）')
    } else if (res.date_range.start_date && res.date_range.end_date) {
      lines.push(`date_range: ${res.date_range.start_date} ~ ${res.date_range.end_date}`)
    }
  }
  for (const [mod, r] of Object.entries(results)) {
    const x = r as any
    lines.push(
      `${mod}: created=${x.created ?? 0}, updated=${x.updated ?? 0}, skipped=${x.skipped ?? 0}` +
        (x.errors?.length ? `, errors=${x.errors.length}` : '')
    )
    if (x.errors?.length) {
      lines.push(...x.errors.slice(0, 8).map((e: string) => `  - ${e}`))
    }
  }
  return lines.join('\n') || JSON.stringify(res, null, 2)
}

async function confirmPull() {
  if (!selectedModules.value.length) {
    ElMessage.warning('请至少选择一个模块')
    return
  }
  if (!assertDateRange()) return
  const mods = selectedModules.value.join('、')
  const range = formatConfirmRange()
  try {
    await ElMessageBox.confirm(
      `将从生产拉取并写入本地数据库（选中模块：${mods}）${range}\n本地同名数据可能被覆盖，是否继续？`,
      '从生产 Pull',
      { type: 'warning', confirmButtonText: '确认 Pull', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  pulling.value = true
  lastResultText.value = ''
  try {
    const res = await envSyncApi.pull(selectedModules.value, datePayload())
    lastOk.value = true
    lastResultText.value = summarize(res)
    ElMessage.success('Pull 完成')
  } catch (e: any) {
    lastOk.value = false
    lastResultText.value = e.message || 'Pull 失败'
    ElMessage.error(lastResultText.value)
  } finally {
    pulling.value = false
  }
}

async function confirmPush() {
  if (!selectedModules.value.length) {
    ElMessage.warning('请至少选择一个模块')
    return
  }
  if (!assertDateRange()) return
  const mods = selectedModules.value.join('、')
  const range = formatConfirmRange()
  try {
    await ElMessageBox.prompt(
      `将把本地选中模块覆盖写入生产（${mods}）${range}\n请确认生产已备份。输入 PUSH 以继续。`,
      'Push 到生产',
      {
        confirmButtonText: '确认覆盖生产',
        cancelButtonText: '取消',
        inputPattern: /^PUSH$/,
        inputErrorMessage: '请输入大写 PUSH',
        confirmButtonClass: 'el-button--danger',
      }
    )
  } catch {
    return
  }
  pushing.value = true
  lastResultText.value = ''
  try {
    const res = await envSyncApi.push(selectedModules.value, datePayload())
    lastOk.value = true
    lastResultText.value = summarize(res)
    ElMessage.success('Push 完成')
  } catch (e: any) {
    lastOk.value = false
    lastResultText.value = e.message || 'Push 失败'
    ElMessage.error(lastResultText.value)
  } finally {
    pushing.value = false
  }
}

async function confirmAsyncPull() {
  if (!selectedModules.value.length) {
    ElMessage.warning('请至少选择一个模块')
    return
  }
  if (!assertDateRange()) return
  try {
    await ElMessageBox.confirm(
      '将创建异步 Pull：生产端落盘分片后本机下载导入。大体量行情请优先用此方式。是否继续？',
      '异步 Pull',
      { type: 'warning', confirmButtonText: '开始', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  asyncPulling.value = true
  try {
    const res = await envSyncApi.createAsyncPull(selectedModules.value, datePayload())
    startJobPoll(res.job_id)
    ElMessage.success('异步 Pull 已启动')
  } catch (e: any) {
    asyncPulling.value = false
    ElMessage.error(e.message || '创建异步 Pull 失败')
  }
}

async function confirmAsyncPush() {
  if (!selectedModules.value.length) {
    ElMessage.warning('请至少选择一个模块')
    return
  }
  if (!assertDateRange()) return
  try {
    await ElMessageBox.prompt(
      '将创建异步 Push：本机落盘分片后逐片上传生产。输入 PUSH 继续。',
      '异步 Push',
      {
        confirmButtonText: '开始',
        cancelButtonText: '取消',
        inputPattern: /^PUSH$/,
        inputErrorMessage: '请输入大写 PUSH',
        confirmButtonClass: 'el-button--danger',
      }
    )
  } catch {
    return
  }
  asyncPushing.value = true
  try {
    const res = await envSyncApi.createAsyncPush(selectedModules.value, datePayload())
    startJobPoll(res.job_id)
    ElMessage.success('异步 Push 已启动')
  } catch (e: any) {
    asyncPushing.value = false
    ElMessage.error(e.message || '创建异步 Push 失败')
  }
}

onMounted(loadAll)
onUnmounted(stopJobPoll)
</script>

<style scoped>
.env-sync-view {
  padding: 0;
}
@media (max-width: 768px) {
  .env-sync-form {
    --el-form-label-width: auto;
  }
  .env-sync-form :deep(.el-form-item) {
    display: block;
  }
  .env-sync-form :deep(.el-form-item__label) {
    justify-content: flex-start;
    margin-bottom: 4px;
  }
  .card-head,
  .head-actions {
    flex-wrap: wrap;
  }
}
.card-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.hint {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.6;
}
.sub-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #9ca3af;
}
.server-keys-table {
  width: 100%;
  margin-bottom: 8px;
}
.mt-2 {
  margin-top: 8px;
}
.sub-hint.inline {
  margin-top: 0;
  margin-left: 8px;
}
.head-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}
.module-groups {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.module-group {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 10px 12px;
}
.group-title {
  font-weight: 600;
  margin-bottom: 6px;
}
.group-items {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  padding-left: 22px;
}
.date-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.date-sep {
  color: #6b7280;
}
.ml-tag {
  margin-left: 6px;
}
.mb-3 {
  margin-bottom: 16px;
}
.mt-3 {
  margin-top: 16px;
}
.mt-2 {
  margin-top: 8px;
}
</style>
