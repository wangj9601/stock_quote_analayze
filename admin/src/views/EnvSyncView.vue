<template>
  <div class="env-sync-view">
    <el-card class="mb-3">
      <template #header>
        <div class="card-head">
          <span>环境数据同步</span>
          <el-tag type="info" size="small">策略/观察/基本信息/板块/行情</el-tag>
        </div>
      </template>
      <p class="hint">
        本地发起 Pull（从生产拉取并写入本地）或 Push（导出本地写入生产）。生产端维护 Sync Key 并校验；
        管理端只调本地包装接口，Key 不由浏览器直连生产。行情数据量大，勾选后必须指定日期范围。
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
              <el-switch v-model="serverForm.enabled" />
            </el-form-item>
            <el-form-item label="Key 状态">
              <span>{{ serverMeta.has_key ? `已配置（${serverMeta.key_hint || '***'}）` : '未配置' }}</span>
            </el-form-item>
            <el-form-item label="手动设置 Key">
              <el-input
                v-model="serverForm.sync_key"
                type="password"
                show-password
                placeholder="可选：粘贴已有 Key；留空不改"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="savingServer" @click="saveServer">保存</el-button>
              <el-button type="warning" :loading="rotating" @click="rotateKey">生成并轮换 Key</el-button>
            </el-form-item>
            <el-alert
              v-if="rotatedKey"
              type="success"
              :closable="false"
              show-icon
              title="请立即复制明文 Key（仅展示一次）"
              :description="rotatedKey"
              class="mt-2"
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
        <el-form-item v-if="quotesSelected" label="行情区间">
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
            <span class="sub-hint inline">单次跨度上限由服务端 ENV_SYNC_QUOTE_MAX_DAYS 控制（默认 366 天）</span>
          </div>
        </el-form-item>
        <el-form-item>
          <el-button type="success" :loading="pulling" @click="confirmPull">从生产 Pull</el-button>
          <el-button type="danger" :loading="pushing" @click="confirmPush">Push 到生产</el-button>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { envSyncApi } from '@/services/envSyncApi'

type ModuleItem = { code: string; name: string; desc?: string; requires_date_range?: boolean }
type ModuleGroup = {
  group: string
  group_name: string
  requires_date_range?: boolean
  items: ModuleItem[]
}

const loadingClient = ref(false)
const loadingServer = ref(false)
const savingClient = ref(false)
const savingServer = ref(false)
const rotating = ref(false)
const testing = ref(false)
const pulling = ref(false)
const pushing = ref(false)
const rotatedKey = ref('')
const lastOk = ref(true)
const lastResultText = ref('')

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
const serverMeta = reactive({ has_key: false, key_hint: '' })

const moduleGroups = ref<ModuleGroup[]>([])
const selectedModules = ref<string[]>([])
const defaultResources = ref<string[]>([])
const dateRangeRequired = ref<string[]>([])
const startDate = ref<string>('')
const endDate = ref<string>('')

const quotesSelected = computed(() =>
  selectedModules.value.some((c) => dateRangeRequired.value.includes(c))
)

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
  if (!quotesSelected.value) return true
  if (!startDate.value || !endDate.value) {
    ElMessage.warning('勾选行情时必须填写开始/结束日期')
    return false
  }
  if (startDate.value > endDate.value) {
    ElMessage.warning('开始日期不能晚于结束日期')
    return false
  }
  return true
}

function datePayload() {
  if (!quotesSelected.value) return undefined
  return { start_date: startDate.value, end_date: endDate.value }
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
    serverMeta.has_key = !!s.has_key
    serverMeta.key_hint = s.key_hint || ''

    moduleGroups.value = (mods.groups || []) as ModuleGroup[]
    defaultResources.value = mods.default_resources || []
    dateRangeRequired.value = mods.date_range_required || ['historical_quotes', 'historical_quotes_hk']
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

async function saveServer() {
  savingServer.value = true
  try {
    const body: any = { enabled: serverForm.enabled, rotate: false }
    if (serverForm.sync_key.trim()) body.sync_key = serverForm.sync_key.trim()
    await envSyncApi.updateServerConfig(body)
    serverForm.sync_key = ''
    await loadAll()
    ElMessage.success('服务端配置已保存')
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    savingServer.value = false
  }
}

async function rotateKey() {
  rotating.value = true
  try {
    const res = await envSyncApi.updateServerConfig({
      enabled: true,
      rotate: true,
    })
    rotatedKey.value = res.sync_key || ''
    serverMeta.has_key = true
    serverMeta.key_hint = res.key_hint || ''
    serverForm.enabled = true
    ElMessage.success('已生成新 Key，请复制后配置到本地客户端')
  } catch (e: any) {
    ElMessage.error(e.message || '轮换失败')
  } finally {
    rotating.value = false
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
    lines.push(`date_range: ${res.date_range.start_date} ~ ${res.date_range.end_date}`)
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
  const range =
    quotesSelected.value && startDate.value && endDate.value
      ? `\n行情区间：${startDate.value} ~ ${endDate.value}`
      : ''
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
  try {
    await ElMessageBox.confirm(
      '将把本地选中模块数据覆盖写入生产环境，请确认生产已备份且 Sync Key 正确。是否继续？',
      'Push 到生产',
      { type: 'warning', confirmButtonText: '确认 Push', cancelButtonText: '取消' }
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

onMounted(loadAll)
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
