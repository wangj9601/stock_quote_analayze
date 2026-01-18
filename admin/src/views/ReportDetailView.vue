<template>
  <div class="report-detail-view">
    <ReportDetail />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import ReportDetail from '@/components/pvfrs/ReportDetail.vue'

const route = useRoute()

onMounted(() => {
  console.log('ReportDetailView 已挂载，reportId:', route.params.id)
})
</script>

<style scoped>
.report-detail-view {
  width: 100%;
  min-height: 100%;
  padding: 20px;
  background: #f5f5f5;
}
</style>
