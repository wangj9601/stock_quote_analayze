<template>
  <div class="email-sender-config-view">
    <el-card>
      <template #header>
        <span>发送邮箱配置</span>
      </template>
      <el-form
        ref="formRef"
        :model="form"
        label-width="120px"
        style="max-width: 560px;"
      >
        <el-form-item label="SMTP 主机">
          <el-input v-model="form.host" placeholder="例如 smtp.qq.com" />
        </el-form-item>
        <el-form-item label="端口">
          <el-input-number v-model="form.port" :min="1" :max="65535" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="SMTP 登录用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="不修改请留空"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="发件人邮箱">
          <el-input v-model="form.from_email" placeholder="显示的发件人邮箱" />
        </el-form-item>
        <el-form-item label="发件人名称">
          <el-input v-model="form.from_name" placeholder="例如：股票分析系统" />
        </el-form-item>
        <el-form-item label="启用 TLS">
          <el-switch v-model="form.use_tls" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
          <el-button :loading="testing" @click="showTestDialog = true">发送测试邮件</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-dialog v-model="showTestDialog" title="发送测试邮件" width="400px">
      <el-form label-width="80px">
        <el-form-item label="收件邮箱">
          <el-input v-model="testToEmail" placeholder="请输入收件邮箱" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTestDialog = false">取消</el-button>
        <el-button type="primary" :loading="testing" :disabled="!testToEmail" @click="handleTestSend">
          发送
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { pushService } from '@/services/push.service'
import type { EmailSenderConfigResponse, EmailSenderConfigUpdateRequest } from '@/services/push.service'

const formRef = ref()
const saving = ref(false)
const testing = ref(false)
const showTestDialog = ref(false)
const testToEmail = ref('')

const form = reactive<{
  host: string
  port: number
  username: string
  password: string
  from_email: string
  from_name: string
  use_tls: boolean
}>({
  host: '',
  port: 587,
  username: '',
  password: '',
  from_email: '',
  from_name: '股票分析系统',
  use_tls: true
})

async function loadConfig() {
  try {
    const res = await pushService.getEmailSenderConfig()
    form.host = res.host ?? ''
    form.port = res.port ?? 587
    form.username = res.username ?? ''
    form.password = ''
    form.from_email = res.from_email ?? ''
    form.from_name = res.from_name ?? '股票分析系统'
    form.use_tls = res.use_tls ?? true
  } catch (e: unknown) {
    const msg = e && typeof e === 'object' && 'response' in e
      ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : String(e)
    ElMessage.error('加载配置失败：' + msg)
  }
}

async function handleSave() {
  saving.value = true
  try {
    const payload: EmailSenderConfigUpdateRequest = {
      host: form.host || undefined,
      port: form.port,
      username: form.username || undefined,
      from_email: form.from_email || undefined,
      from_name: form.from_name || undefined,
      use_tls: form.use_tls
    }
    if (form.password) payload.password = form.password
    await pushService.updateEmailSenderConfig(payload)
    ElMessage.success('保存成功')
    form.password = ''
    await loadConfig()
  } catch (e: unknown) {
    const msg = e && typeof e === 'object' && 'response' in e
      ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : String(e)
    ElMessage.error('保存失败：' + msg)
  } finally {
    saving.value = false
  }
}

async function handleTestSend() {
  if (!testToEmail.value) return
  testing.value = true
  try {
    const res = await pushService.testEmailSenderConfig(testToEmail.value)
    if (res.success) {
      ElMessage.success('测试邮件已发送')
      showTestDialog.value = false
      testToEmail.value = ''
    } else {
      ElMessage.error(res.message || '发送失败')
    }
  } catch (e: unknown) {
    const msg = e && typeof e === 'object' && 'response' in e
      ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : String(e)
    ElMessage.error('发送失败：' + msg)
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.email-sender-config-view {
  padding: 0;
}
</style>
