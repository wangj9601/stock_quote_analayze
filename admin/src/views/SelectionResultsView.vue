<template>
  <div class="selection-results">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1>PVFRS选股结果</h1>
      <div class="header-actions">
        <el-button type="primary" @click="loadSelectionResults" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
        <el-button @click="showFilterDialog = true">
          <el-icon><Filter /></el-icon>
          筛选条件
        </el-button>
      </div>
    </div>

    <!-- 统计概览 -->
    <el-row :gutter="20" class="stats-overview">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-item">
            <div class="stat-value">{{ selectionData.total || 0 }}</div>
            <div class="stat-label">选股总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-item">
            <div class="stat-value">{{ avgSignalStrength.toFixed(2) }}</div>
            <div class="stat-label">平均信号强度</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-item">
            <div class="stat-value">{{ highQualityCount }}</div>
            <div class="stat-label">高质量信号</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-item">
            <div class="stat-value">{{ selectionData.timestamp ? formatDate(selectionData.timestamp) : '-' }}</div>
            <div class="stat-label">更新时间</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 选股结果表格 -->
    <el-card class="results-table">
      <template #header>
        <div class="table-header">
          <span>选股结果详情</span>
          <span class="table-info" v-if="tableData.length > 0">
            共 {{ tableData.length }} 只股票
          </span>
        </div>
      </template>
      
      <el-table 
        :data="tableData" 
        stripe 
        :loading="loading"
        @row-click="handleRowClick"
        style="cursor: pointer;"
      >
        <el-table-column prop="symbol" label="股票代码" width="100" />
        <el-table-column prop="name" label="股票名称" width="120" />
        <el-table-column prop="price" label="当前价格" width="100">
          <template #default="scope">
            ¥{{ scope.row.price?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="signal_strength" label="信号强度" width="100">
          <template #default="scope">
            <el-progress 
              :percentage="scope.row.signal_strength * 100" 
              :stroke-width="8"
              :show-text="false"
            />
            <span class="signal-text">{{ (scope.row.signal_strength * 100).toFixed(1) }}%</span>
          </template>
        </el-table-column>
        
        <!-- 价格维度 -->
        <el-table-column label="价格维度" width="120">
          <template #default="scope">
            <div class="dimension-info">
              <div class="dimension-value">
                {{ scope.row.indicators?.price_dimension?.macro_displacement?.toFixed(2) || '-' }}
              </div>
              <div class="dimension-label">宏观位移</div>
            </div>
          </template>
        </el-table-column>
        
        <!-- 频率维度 -->
        <el-table-column label="频率维度" width="120">
          <template #default="scope">
            <div class="dimension-info">
              <div class="dimension-value">
                {{ scope.row.indicators?.frequency_dimension?.rising_days || '-' }}/{{ scope.row.indicators?.frequency_dimension?.falling_days || '-' }}
              </div>
              <div class="dimension-label">涨/跌天数</div>
            </div>
          </template>
        </el-table-column>
        
        <!-- 成交量维度 -->
        <el-table-column label="成交量维度" width="120">
          <template #default="scope">
            <div class="dimension-info">
              <div class="dimension-value">
                {{ scope.row.indicators?.volume_dimension?.efficiency_ratio?.toFixed(2) || '-' }}
              </div>
              <div class="dimension-label">效率比</div>
            </div>
          </template>
        </el-table-column>
        
        <!-- 入场时机 -->
        <el-table-column label="入场时机" width="120">
          <template #default="scope">
            <div class="timing-info">
              <div class="timing-score">
                {{ scope.row.indicators?.entry_timing_analysis?.comprehensive_assessment?.score?.toFixed(2) || '-' }}
              </div>
              <div class="timing-label">综合评分</div>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="investment_advice" label="投资建议" width="100">
          <template #default="scope">
            <el-tag 
              :type="scope.row.investment_advice === 'BUY' ? 'success' : 'info'"
              size="small"
            >
              {{ scope.row.investment_advice }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="100">
          <template #default="scope">
            <el-button size="small" @click.stop="openDetailDialog(scope.row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog 
      v-model="showDetailDialog" 
      :title="`选股详情 - ${selectedStock?.symbol} (${selectedStock?.name})`"
      width="80%"
    >
      <div v-if="selectedStock" class="stock-detail">
        <!-- 基本信息 -->
        <el-descriptions :column="3" border class="basic-info">
          <el-descriptions-item label="股票代码">{{ selectedStock.symbol }}</el-descriptions-item>
          <el-descriptions-item label="股票名称">{{ selectedStock.name }}</el-descriptions-item>
          <el-descriptions-item label="当前价格">¥{{ selectedStock.price?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="信号强度">
            <el-progress 
              :percentage="selectedStock.signal_strength * 100" 
              :stroke-width="10"
            />
          </el-descriptions-item>
          <el-descriptions-item label="投资建议">
            <el-tag :type="selectedStock.investment_advice === 'BUY' ? 'success' : 'info'">
              {{ selectedStock.investment_advice }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="分析时间">{{ formatDate(selectedStock.analysis_time) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 维度分析详情 -->
        <el-row :gutter="20" class="dimension-details">
          <el-col :span="8">
            <el-card header="价格维度分析" class="dimension-card">
              <div class="dimension-content">
                <div class="dimension-item">
                  <span class="label">宏观位移:</span>
                  <span class="value">{{ selectedStock.indicators?.price_dimension?.macro_displacement?.toFixed(4) || '-' }}</span>
                </div>
                <div class="dimension-item">
                  <span class="label">即时偏离:</span>
                  <span class="value">{{ selectedStock.indicators?.price_dimension?.instant_deviation?.toFixed(4) || '-' }}</span>
                </div>
                <div class="dimension-item">
                  <span class="label">20日均价:</span>
                  <span class="value">¥{{ selectedStock.indicators?.price_dimension?.avg_price_20d?.toFixed(2) || '-' }}</span>
                </div>
                <div class="dimension-item">
                  <span class="label">幅度系数:</span>
                  <span class="value">{{ selectedStock.indicators?.amplitude_ratio?.toFixed(4) || '-' }}</span>
                </div>
              </div>
            </el-card>
          </el-col>
          
          <el-col :span="8">
            <el-card header="频率维度分析" class="dimension-card">
              <div class="dimension-content">
                <div class="dimension-item">
                  <span class="label">上涨天数:</span>
                  <span class="value">{{ selectedStock.indicators?.frequency_dimension?.rising_days || '-' }}</span>
                </div>
                <div class="dimension-item">
                  <span class="label">下跌天数:</span>
                  <span class="value">{{ selectedStock.indicators?.frequency_dimension?.falling_days || '-' }}</span>
                </div>
                <div class="dimension-item">
                  <span class="label">频率优势:</span>
                  <el-tag :type="selectedStock.indicators?.frequency_dimension?.frequency_advantage ? 'success' : 'danger'" size="small">
                    {{ selectedStock.indicators?.frequency_dimension?.frequency_advantage ? '是' : '否' }}
                  </el-tag>
                </div>
                <div class="dimension-item">
                  <span class="label">虚假繁荣:</span>
                  <el-tag :type="!selectedStock.indicators?.frequency_dimension?.has_false_prosperity ? 'success' : 'danger'" size="small">
                    {{ selectedStock.indicators?.frequency_dimension?.has_false_prosperity ? '是' : '否' }}
                  </el-tag>
                </div>
              </div>
            </el-card>
          </el-col>
          
          <el-col :span="8">
            <el-card header="成交量维度分析" class="dimension-card">
              <div class="dimension-content">
                <div class="dimension-item">
                  <span class="label">20日均量:</span>
                  <span class="value">{{ formatNumber(selectedStock.indicators?.volume_dimension?.avg_volume_20d) }}</span>
                </div>
                <div class="dimension-item">
                  <span class="label">当前成交量:</span>
                  <span class="value">{{ formatNumber(selectedStock.indicators?.volume_dimension?.current_volume) }}</span>
                </div>
                <div class="dimension-item">
                  <span class="label">效率比:</span>
                  <span class="value">{{ selectedStock.indicators?.volume_dimension?.efficiency_ratio?.toFixed(4) || '-' }}</span>
                </div>
                <div class="dimension-item">
                  <span class="label">量比:</span>
                  <span class="value">{{ selectedStock.indicators?.volume_multiplier?.toFixed(2) || '-' }}</span>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 入场时机分析 -->
        <el-card header="入场时机分析" class="timing-card">
          <div v-if="selectedStock.indicators?.entry_timing_analysis" class="timing-analysis">
            <el-row :gutter="20">
              <el-col :span="8">
                <div class="timing-section">
                  <h4>价格突破</h4>
                  <div class="timing-item">
                    <span class="label">检测状态:</span>
                    <el-tag :type="selectedStock.indicators.entry_timing_analysis.price_breakthrough?.detected ? 'success' : 'info'" size="small">
                      {{ selectedStock.indicators.entry_timing_analysis.price_breakthrough?.detected ? '已突破' : '未突破' }}
                    </el-tag>
                  </div>
                  <div class="timing-item">
                    <span class="label">突破强度:</span>
                    <span class="value">{{ selectedStock.indicators.entry_timing_analysis.price_breakthrough?.strength?.toFixed(2) || '-' }}</span>
                  </div>
                  <div class="timing-item">
                    <span class="label">状态描述:</span>
                    <span class="value">{{ selectedStock.indicators.entry_timing_analysis.price_breakthrough?.status || '-' }}</span>
                  </div>
                </div>
              </el-col>
              
              <el-col :span="8">
                <div class="timing-section">
                  <h4>成交量突破</h4>
                  <div class="timing-item">
                    <span class="label">检测状态:</span>
                    <el-tag :type="selectedStock.indicators.entry_timing_analysis.volume_breakthrough?.detected ? 'success' : 'info'" size="small">
                      {{ selectedStock.indicators.entry_timing_analysis.volume_breakthrough?.detected ? '已突破' : '未突破' }}
                    </el-tag>
                  </div>
                  <div class="timing-item">
                    <span class="label">时机得分:</span>
                    <span class="value">{{ selectedStock.indicators.entry_timing_analysis.volume_breakthrough?.timing_score?.toFixed(2) || '-' }}</span>
                  </div>
                  <div class="timing-item">
                    <span class="label">状态描述:</span>
                    <span class="value">{{ selectedStock.indicators.entry_timing_analysis.volume_breakthrough?.status || '-' }}</span>
                  </div>
                </div>
              </el-col>
              
              <el-col :span="8">
                <div class="timing-section">
                  <h4>幅度验证</h4>
                  <div class="timing-item">
                    <span class="label">验证状态:</span>
                    <el-tag :type="selectedStock.indicators.entry_timing_analysis.amplitude_validation?.valid ? 'success' : 'danger'" size="small">
                      {{ selectedStock.indicators.entry_timing_analysis.amplitude_validation?.valid ? '通过' : '未通过' }}
                    </el-tag>
                  </div>
                  <div class="timing-item">
                    <span class="label">幅度系数:</span>
                    <span class="value">{{ selectedStock.indicators.entry_timing_analysis.amplitude_validation?.coefficient?.toFixed(4) || '-' }}</span>
                  </div>
                  <div class="timing-item">
                    <span class="label">建议:</span>
                    <span class="value">{{ selectedStock.indicators.entry_timing_analysis.amplitude_validation?.recommendation || '-' }}</span>
                  </div>
                </div>
              </el-col>
            </el-row>
            
            <div class="comprehensive-assessment">
              <h4>综合评估</h4>
              <div class="assessment-item">
                <span class="label">综合得分:</span>
                <el-progress 
                  :percentage="(selectedStock.indicators.entry_timing_analysis.comprehensive_assessment?.score || 0) * 100"
                  :stroke-width="10"
                />
              </div>
              <div class="assessment-item">
                <span class="label">最佳时机:</span>
                <el-tag :type="selectedStock.indicators.entry_timing_analysis.comprehensive_assessment?.optimal_timing ? 'success' : 'info'" size="small">
                  {{ selectedStock.indicators.entry_timing_analysis.comprehensive_assessment?.optimal_timing ? '是' : '否' }}
                </el-tag>
              </div>
              <div class="assessment-item">
                <span class="label">建议:</span>
                <span class="value">{{ selectedStock.indicators.entry_timing_analysis.comprehensive_assessment?.recommendation || '-' }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </el-dialog>

    <!-- 筛选对话框 -->
    <el-dialog v-model="showFilterDialog" title="筛选条件" width="400px">
      <el-form :model="filterForm" label-width="100px">
        <el-form-item label="日期">
          <el-date-picker
            v-model="filterForm.date"
            type="date"
            placeholder="选择日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="最小信号强度">
          <el-slider
            v-model="filterForm.min_strength"
            :min="0"
            :max="1"
            :step="0.1"
            show-input
          />
        </el-form-item>
        <el-form-item label="返回数量">
          <el-input-number
            v-model="filterForm.limit"
            :min="1"
            :max="100"
            placeholder="限制返回数量"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showFilterDialog = false">取消</el-button>
        <el-button type="primary" @click="applyFilter">应用筛选</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Filter } from '@element-plus/icons-vue'
import { pvfrsApiService } from '@/services/pvfrsApi'

// 响应式数据
const loading = ref(false)
const selectionData = ref<any>({
  data: [],
  total: 0,
  timestamp: null
})
const selectedStock = ref<any>(null)
const showDetailDialog = ref(false)
const showFilterDialog = ref(false)

// 筛选表单
const filterForm = ref({
  date: '',
  min_strength: 0.3,
  limit: 50
})

// 计算属性
// 确保表格数据始终是数组
const tableData = computed(() => {
  const data = selectionData.value?.data
  return Array.isArray(data) ? data : []
})

const avgSignalStrength = computed(() => {
  const data = tableData.value
  if (!data || data.length === 0) return 0
  const total = data.reduce((sum: number, item: any) => sum + (item.signal_strength || 0), 0)
  return total / data.length
})

const highQualityCount = computed(() => {
  const data = tableData.value
  if (!data) return 0
  return data.filter((item: any) => (item.signal_strength || 0) >= 0.8).length
})

// 方法
const loadSelectionResults = async () => {
  try {
    loading.value = true
    const params: any = {}
    
    if (filterForm.value.date) {
      params.date = filterForm.value.date
    }
    if (filterForm.value.min_strength > 0.3) {
      params.min_strength = filterForm.value.min_strength
    }
    if (filterForm.value.limit !== 50) {
      params.limit = filterForm.value.limit
    }
    
    const response = await pvfrsApiService.getSelectionResults(params)
    
    // 确保 data 字段始终是数组
    if (response && typeof response === 'object') {
      // 如果响应包含 data 字段，使用它；否则使用整个响应（如果它是数组）
      if (Array.isArray(response.data)) {
        selectionData.value = {
          data: response.data,
          total: response.total || response.data.length,
          timestamp: response.timestamp || new Date().toISOString()
        }
      } else if (Array.isArray(response)) {
        // 如果响应本身就是数组
        selectionData.value = {
          data: response,
          total: response.length,
          timestamp: new Date().toISOString()
        }
      } else {
        // 如果数据结构不符合预期，使用空数组
        console.warn('API响应格式不符合预期:', response)
        selectionData.value = {
          data: [],
          total: 0,
          timestamp: new Date().toISOString()
        }
      }
    } else {
      // 如果响应不是对象，重置为空数组
      selectionData.value = {
        data: [],
        total: 0,
        timestamp: new Date().toISOString()
      }
    }
  } catch (error) {
    console.error('加载选股结果失败:', error)
    ElMessage.error('加载选股结果失败')
    // 确保即使出错，data 也是数组
    selectionData.value = {
      data: [],
      total: 0,
      timestamp: null
    }
  } finally {
    loading.value = false
  }
}

const handleRowClick = (stock: any) => {
  selectedStock.value = stock
  showDetailDialog.value = true
}

const openDetailDialog = (stock: any) => {
  selectedStock.value = stock
  showDetailDialog.value = true
}

const applyFilter = () => {
  showFilterDialog.value = false
  loadSelectionResults()
}

const formatDate = (dateString: string) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

const formatNumber = (num: number) => {
  if (!num) return '-'
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万'
  }
  return num.toFixed(0)
}

// 生命周期
onMounted(() => {
  // 设置默认日期为今天
  const today = new Date()
  filterForm.value.date = today.toISOString().split('T')[0]
  
  loadSelectionResults()
})
</script>

<style scoped lang="postcss">
.selection-results {
  @apply space-y-6;
}

.page-header {
  @apply flex justify-between items-center;
  
  h1 {
    @apply text-2xl font-bold text-gray-900;
  }
  
  .header-actions {
    @apply flex space-x-2;
  }
}

.stats-overview {
  @apply mb-6;
}

.stat-card {
  .stat-item {
    @apply text-center;
    
    .stat-value {
      @apply text-2xl font-bold text-blue-600;
    }
    
    .stat-label {
      @apply text-sm text-gray-500 mt-1;
    }
  }
}

.results-table {
  .table-header {
    @apply flex justify-between items-center;
    
    .table-info {
      @apply text-sm text-gray-500;
    }
  }
  
  .signal-text {
    @apply ml-2 text-sm;
  }
  
  .dimension-info, .timing-info {
    @apply text-center;
    
    .dimension-value, .timing-score {
      @apply font-semibold text-blue-600;
    }
    
    .dimension-label, .timing-label {
      @apply text-xs text-gray-500;
    }
  }
}

.stock-detail {
  @apply space-y-6;
}

.basic-info {
  @apply mb-6;
}

.dimension-details {
  @apply mb-6;
}

.dimension-card {
  .dimension-content {
    @apply space-y-3;
    
    .dimension-item {
      @apply flex justify-between items-center;
      
      .label {
        @apply text-sm text-gray-600;
      }
      
      .value {
        @apply font-medium text-gray-900;
      }
    }
  }
}

.timing-card {
  .timing-analysis {
    @apply space-y-6;
    
    .timing-section {
      h4 {
        @apply text-lg font-medium text-gray-900 mb-3;
      }
      
      .timing-item {
        @apply flex justify-between items-center mb-2;
        
        .label {
          @apply text-sm text-gray-600;
        }
        
        .value {
          @apply font-medium text-gray-900;
        }
      }
    }
    
    .comprehensive-assessment {
      h4 {
        @apply text-lg font-medium text-gray-900 mb-3;
      }
      
      .assessment-item {
        @apply flex justify-between items-center mb-2;
        
        .label {
          @apply text-sm text-gray-600;
        }
        
        .value {
          @apply font-medium text-gray-900;
        }
      }
    }
  }
}
</style>
