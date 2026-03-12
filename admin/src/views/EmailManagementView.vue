<template>
  <div class="report-management-view">
    <el-tabs v-model="activeTab" type="border-card" @tab-change="onTabChange">
      <el-tab-pane label="发送邮箱配置" name="sender">
        <EmailSenderConfigView />
      </el-tab-pane>
      <el-tab-pane label="报告推送配置" name="push">
        <PushConfigView />
      </el-tab-pane>
      <el-tab-pane label="报告发送日志" name="logs">
        <EmailLogsView />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EmailSenderConfigView from './EmailSenderConfigView.vue'
import PushConfigView from './PushConfigView.vue'
import EmailLogsView from './EmailLogsView.vue'

const route = useRoute()
const router = useRouter()
const activeTab = ref<'sender' | 'push' | 'logs'>('sender')

function onTabChange(name: string) {
  router.replace({ query: { ...route.query, tab: name } }).catch(() => {})
}

watch(
  () => route.query.tab,
  (tab) => {
    if (tab === 'sender' || tab === 'push' || tab === 'logs') {
      activeTab.value = tab
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.report-management-view {
  padding: 0;
}
.report-management-view :deep(.el-tabs__content) {
  padding: 16px 0 0;
}
</style>
