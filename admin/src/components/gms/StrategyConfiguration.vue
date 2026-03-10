<template>
  <div class="strategy-configuration">
    <el-card header="GMS 策略配置（gms_config.json）">
      <div class="config-actions mb-4">
        <el-button type="primary" @click="saveConfig" :loading="saving">保存配置</el-button>
        <el-button @click="loadConfig" :loading="loading">重新加载</el-button>
        <el-button @click="resetDefault">重置为默认</el-button>
      </div>
      <el-alert v-if="message" :title="message" :type="messageType" show-icon class="mb-4" />
      <el-input
        v-model="configJson"
        type="textarea"
        :rows="20"
        placeholder="JSON 配置"
        class="font-mono text-sm"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, inject } from 'vue'
import { ElMessage } from 'element-plus'

const gmsApi = inject<any>('gmsApi')
const configJson = ref('{}')
const loading = ref(false)
const saving = ref(false)
const message = ref('')
const messageType = ref<'success' | 'warning' | 'info' | 'error'>('info')

async function loadConfig() {
  loading.value = true
  message.value = ''
  try {
    const data = await gmsApi.getConfig()
    configJson.value = JSON.stringify(data, null, 2)
  } catch (e) {
    ElMessage.error('加载配置失败')
    message.value = '加载配置失败'
    messageType.value = 'error'
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  let obj: any
  try {
    obj = JSON.parse(configJson.value)
  } catch (e) {
    ElMessage.error('JSON 格式错误')
    return
  }
  saving.value = true
  message.value = ''
  try {
    await gmsApi.saveConfig(obj)
    ElMessage.success('配置已保存')
    message.value = '配置已保存'
    messageType.value = 'success'
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
    message.value = '保存失败'
    messageType.value = 'error'
  } finally {
    saving.value = false
  }
}

function resetDefault() {
  configJson.value = JSON.stringify({
    observation_period: 20,
    ratio_indicators: { use_ratio_d: true, use_ratio_d_for_exit: false },
    left_buy: { ratio_d20_abs_max: 0.015, volume_ratio_max: 0.8 },
    right_buy: { volume_ratio_min: 1.5 },
    scoring: {
      accumulation_fz_min: 1.5,
      balance_ratio_max: 0.01,
      momentum_volume_ratio_min: 1.5,
      watch_threshold: 60,
      alert_threshold: 90
    },
    exit: { trend_break_days: 3, overbought_ratio: 0.15 }
  }, null, 2)
  message.value = '已填充默认配置（未保存）'
  messageType.value = 'info'
}

const emit = defineEmits<{ (e: 'config-saved'): void }>()
defineExpose({ loadConfig })

onMounted(() => loadConfig())
</script>

<style scoped>
.mb-4 { margin-bottom: 1rem; }
.font-mono { font-family: ui-monospace, monospace; }
</style>
