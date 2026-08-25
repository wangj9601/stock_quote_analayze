<template>
  <div class="dashboard-view">
    <!-- <div class="dashboard-header">
      <h1 class="text-2xl font-bold text-gray-900">仪表板</h1>
    </div> -->

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <el-row :gutter="16">
        <el-col :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon users">
                <el-icon><User /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.users || 0 }}</div>
                <div class="stat-label">用户总数</div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon logs">
                <el-icon><Document /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.logs || 0 }}</div>
                <div class="stat-label">日志总数</div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon quotes">
                <el-icon><TrendCharts /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.quotes || 0 }}</div>
                <div class="stat-label">行情数据</div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <el-col :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-icon system">
                <el-icon><Monitor /></el-icon>
              </div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.system || '正常' }}</div>
                <div class="stat-label">系统状态</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 快速操作 -->
    <div class="quick-actions">
      <el-card>
        <template #header>
          <span>快速操作</span>
        </template>
        
        <div class="actions-grid">
          <el-button
            v-for="action in quickActions"
            :key="action.path"
            :type="action.type"
            :icon="action.icon"
            class="action-button"
            @click="navigateTo(action.path)"
          >
            {{ action.name }}
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 最近活动 -->
    <div class="recent-activity">
      <el-card>
        <template #header>
          <span>最近活动</span>
        </template>
        
        <el-timeline>
          <el-timeline-item
            v-for="activity in recentActivities"
            :key="activity.id"
            :timestamp="activity.time"
            :type="activity.type"
          >
            {{ activity.content }}
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  User,
  Document,
  TrendCharts,
  Monitor,
  Setting,
  DataAnalysis
} from '@element-plus/icons-vue'

const router = useRouter()

// 统计数据
const stats = ref({
  users: 0,
  logs: 0,
  quotes: 0,
  system: '正常'
})

// 快速操作
const quickActions: { name: string; path: string; type: '' | 'text' | 'default' | 'success' | 'primary' | 'warning' | 'info' | 'danger'; icon: any }[] = [
  { name: '查看日志', path: '/logs', type: 'primary', icon: Document },
  { name: '用户与权限', path: '/access-management', type: 'success', icon: User },
  { name: '行情数据', path: '/quotes', type: 'warning', icon: TrendCharts },
  { name: '系统监控', path: '/monitoring', type: 'info', icon: Monitor },
  { name: '数据采集', path: '/datacollect', type: 'primary', icon: DataAnalysis },
  { name: '系统设置', path: '/datasource', type: 'success', icon: Setting }
]

// 最近活动
const recentActivities = ref<{
  id: number
  content: string
  time: string
  type: 'success' | 'primary' | 'warning' | 'info' | 'danger'
}[]>([
  {
    id: 1,
    content: '系统启动完成',
    time: '2024-01-01 08:00:00',
    type: 'success'
  },
  {
    id: 2,
    content: '数据采集任务开始',
    time: '2024-01-01 08:30:00',
    type: 'primary'
  },
  {
    id: 3,
    content: '用户登录：admin',
    time: '2024-01-01 09:00:00',
    type: 'info'
  },
  {
    id: 4,
    content: '系统备份完成',
    time: '2024-01-01 10:00:00',
    type: 'success'
  }
])

// 导航到指定页面
const navigateTo = (path: string) => {
  router.push(path)
}

// 加载统计数据
const loadStats = () => {
  // 这里可以调用API获取真实的统计数据
  stats.value = {
    users: 1250,
    logs: 45678,
    quotes: 2345,
    system: '正常'
  }
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped>
.dashboard-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.dashboard-header {
  margin-bottom: 1.5rem;
}

.stats-grid {
  margin-bottom: 1.5rem;
}

.stat-card {
  height: 6rem;
}

.stat-content {
  display: flex;
  align-items: center;
  height: 100%;
}

.stat-icon {
  width: 3rem;
  height: 3rem;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 1rem;
}

.stat-icon.users {
  background-color: rgb(219 234 254);
  color: rgb(37 99 235);
}

.stat-icon.logs {
  background-color: rgb(220 252 231);
  color: rgb(22 163 74);
}

.stat-icon.quotes {
  background-color: rgb(254 249 195);
  color: rgb(202 138 4);
}

.stat-icon.system {
  background-color: rgb(243 232 255);
  color: rgb(147 51 234);
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: rgb(17 24 39);
}

.stat-label {
  font-size: 0.875rem;
  color: rgb(107 114 128);
  margin-top: 0.25rem;
}

.quick-actions {
  margin-bottom: 1.5rem;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  align-items: stretch;
  justify-items: stretch;
}

.action-button {
  height: 48px;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  white-space: nowrap;
  min-width: 0;
  max-width: none;
  padding-left: 1rem;
}

@media (min-width: 768px) {
  .actions-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (min-width: 1200px) {
  .actions-grid {
    grid-template-columns: repeat(5, 1fr);
  }
}



.recent-activity {
  margin-bottom: 1.5rem;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .dashboard-view {
    gap: 1.25rem;
    padding: 20px;
  }
  
  .stats-grid {
    margin-bottom: 1.25rem;
  }
  
  .actions-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .dashboard-view {
    gap: 1rem;
    padding: 16px;
  }
  
  .stats-grid {
    margin-bottom: 1rem;
  }
  
  .stat-card {
    height: 5rem;
    margin-bottom: 16px;
  }
  
  .stat-icon {
    width: 2.5rem;
    height: 2.5rem;
    margin-right: 0.75rem;
  }
  
  .stat-value {
    font-size: 1.25rem;
  }
  
  .stat-label {
    font-size: 0.75rem;
  }
  
  .quick-actions {
    margin-bottom: 1rem;
  }
  
  .actions-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.75rem;
  }
  
  .action-button {
    height: 40px;
    font-size: 14px;
    padding-left: 0.75rem;
  }
  
  .recent-activity {
    margin-bottom: 1rem;
  }
}

@media (max-width: 640px) {
  .dashboard-view {
    gap: 0.875rem;
    padding: 14px;
  }
  
  .stats-grid {
    margin-bottom: 0.875rem;
  }
  
  .stat-card {
    height: 4.75rem;
  }
  
  .stat-icon {
    width: 2.25rem;
    height: 2.25rem;
    margin-right: 0.625rem;
  }
  
  .stat-value {
    font-size: 1.125rem;
  }
  
  .stat-label {
    font-size: 0.7rem;
  }
  
  .actions-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 0.625rem;
  }
  
  .action-button {
    height: 38px;
    font-size: 13px;
    padding-left: 0.625rem;
  }
}

@media (max-width: 480px) {
  .dashboard-view {
    gap: 0.75rem;
    padding: 12px;
  }
  
  .stats-grid {
    margin-bottom: 0.75rem;
  }
  
  .stat-card {
    height: 4.5rem;
  }
  
  .stat-icon {
    width: 2rem;
    height: 2rem;
    margin-right: 0.5rem;
  }
  
  .stat-value {
    font-size: 1rem;
  }
  
  .stat-label {
    font-size: 0.65rem;
  }
  
  .actions-grid {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }
  
  .action-button {
    height: 36px;
    font-size: 12px;
    padding-left: 0.5rem;
  }
  
  .quick-actions .el-card {
    margin-bottom: 0.75rem;
  }
  
  .recent-activity .el-card {
    margin-bottom: 0.75rem;
  }
}

@media (max-width: 360px) {
  .dashboard-view {
    gap: 0.625rem;
    padding: 10px;
  }
  
  .stats-grid {
    margin-bottom: 0.625rem;
  }
  
  .stat-card {
    height: 4rem;
  }
  
  .stat-icon {
    width: 1.75rem;
    height: 1.75rem;
    margin-right: 0.375rem;
  }
  
  .stat-value {
    font-size: 0.875rem;
  }
  
  .stat-label {
    font-size: 0.6rem;
  }
  
  .actions-grid {
    grid-template-columns: 1fr;
    gap: 0.375rem;
  }
  
  .action-button {
    height: 32px;
    font-size: 11px;
    padding-left: 0.375rem;
  }
}
</style> 