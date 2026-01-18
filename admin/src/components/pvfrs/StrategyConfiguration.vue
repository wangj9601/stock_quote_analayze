<template>
  <div class="strategy-configuration">
    <!-- 配置概览 -->
    <el-row :gutter="20" class="config-overview">
      <el-col :span="8">
        <el-card class="overview-card">
          <div class="card-header">
            <el-icon class="card-icon"><Setting /></el-icon>
            <span class="card-title">当前配置</span>
          </div>
          <div class="card-content">
            <div class="config-item">
              <span class="config-label">配置版本:</span>
              <span class="config-value">{{ currentConfig.version || 'v1.0.0' }}</span>
            </div>
            <div class="config-item">
              <span class="config-label">最后更新:</span>
              <span class="config-value">{{ formatDateTime(currentConfig.updatedAt) }}</span>
            </div>
            <div class="config-item">
              <span class="config-label">配置状态:</span>
              <el-tag :type="currentConfig.isActive ? 'success' : 'warning'">
                {{ currentConfig.isActive ? '已激活' : '未激活' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="overview-card">
          <div class="card-header">
            <el-icon class="card-icon"><DataAnalysis /></el-icon>
            <span class="card-title">策略参数</span>
          </div>
          <div class="card-content">
            <div class="config-item">
              <span class="config-label">买入信号强度:</span>
              <span class="config-value">{{ currentConfig.buySignalStrength || 0.7 }}</span>
            </div>
            <div class="config-item">
              <span class="config-label">卖出信号强度:</span>
              <span class="config-value">{{ currentConfig.sellSignalStrength || 0.8 }}</span>
            </div>
            <div class="config-item">
              <span class="config-label">风险控制等级:</span>
              <el-tag :type="getRiskLevelType(currentConfig.riskLevel)">
                {{ getRiskLevelLabel(currentConfig.riskLevel) }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="overview-card">
          <div class="card-header">
            <el-icon class="card-icon"><TrendCharts /></el-icon>
            <span class="card-title">性能指标</span>
          </div>
          <div class="card-content">
            <div class="config-item">
              <span class="config-label">历史胜率:</span>
              <span class="config-value text-green-600">{{ currentConfig.winRate || 65 }}%</span>
            </div>
            <div class="config-item">
              <span class="config-label">平均收益:</span>
              <span class="config-value text-blue-600">{{ currentConfig.avgReturn || 12.5 }}%</span>
            </div>
            <div class="config-item">
              <span class="config-label">最大回撤:</span>
              <span class="config-value text-red-600">{{ currentConfig.maxDrawdown || 8.2 }}%</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 配置表单 -->
    <el-card class="config-form-card" header="策略参数配置">
      <el-form 
        ref="configFormRef" 
        :model="configForm" 
        :rules="configRules" 
        label-width="180px"
        class="config-form"
      >
        <!-- 买入条件配置 -->
        <el-divider content-position="left">
          <el-icon><TrendCharts /></el-icon>
          买入条件配置
        </el-divider>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="宏观位移最小值" prop="buyMacroDisplacementMin">
              <el-input-number 
                v-model="configForm.buyMacroDisplacementMin" 
                :step="0.001" 
                :precision="4"
                placeholder="Δ > 0"
                class="w-full"
              />
              <div class="form-help">价格相对于起始位置的位移，通常 > 0</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="即时偏离度最小值" prop="buyInstantDeviationMin">
              <el-input-number 
                v-model="configForm.buyInstantDeviationMin" 
                :step="0.001" 
                :precision="4"
                placeholder="d20 > d"
                class="w-full"
              />
              <div class="form-help">当前价格相对于20日均线的偏离度</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="上涨频率优势" prop="buyRisingDaysAdvantage">
              <el-switch v-model="configForm.buyRisingDaysAdvantage" />
              <div class="form-help">要求上涨天数 > 下跌天数（Z > F）</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="效率最小值" prop="buyEfficiencyMin">
              <el-input-number 
                v-model="configForm.buyEfficiencyMin" 
                :step="0.001" 
                :precision="4"
                placeholder="m20 > m"
                class="w-full"
              />
              <div class="form-help">成交量效率指标，m20 > m</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="乖离率最小值" prop="buyBiasMin">
              <el-input-number 
                v-model="configForm.buyBiasMin" 
                :step="0.01" 
                :precision="3"
                placeholder="2%"
                class="w-full"
              />
              <div class="form-help">价格相对于均线的乖离率，通常 > 2%</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="相对位移最小值" prop="buyRelativeDisplacementMin">
              <el-input-number 
                v-model="configForm.buyRelativeDisplacementMin" 
                :step="0.01" 
                :precision="3"
                placeholder="5%"
                class="w-full"
              />
              <div class="form-help">相对位移 Δ/d，通常 > 5%</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="连续确认天数" prop="buyConsecutiveDays">
          <el-input-number 
            v-model="configForm.buyConsecutiveDays" 
            :min="1" 
            :max="10"
            placeholder="3天"
            class="w-full"
          />
          <div class="form-help">信号连续确认的天数，提高可靠性</div>
        </el-form-item>

        <!-- 卖出条件配置 -->
        <el-divider content-position="left">
          <el-icon><Warning /></el-icon>
          卖出条件配置
        </el-divider>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="乖离率最大值" prop="sellBiasMax">
              <el-input-number 
                v-model="configForm.sellBiasMax" 
                :step="0.01" 
                :precision="3"
                placeholder="8%"
                class="w-full"
              />
              <div class="form-help">超买信号，乖离率 > 8% 时卖出</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="即时偏离度最大值" prop="sellInstantDeviationMax">
              <el-input-number 
                v-model="configForm.sellInstantDeviationMax" 
                :step="0.01" 
                :precision="3"
                placeholder="5%"
                class="w-full"
              />
              <div class="form-help">价格偏离度过大时的卖出信号</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="价涨量缩背离" prop="sellPriceVolumeDivergence">
          <el-switch v-model="configForm.sellPriceVolumeDivergence" />
          <div class="form-help">检测价格上涨但成交量下降的背离信号</div>
        </el-form-item>

        <!-- 风控参数配置 -->
        <el-divider content-position="left">
          <el-icon><Lock /></el-icon>
          风险控制配置
        </el-divider>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="止损比例" prop="stopLoss">
              <el-input-number 
                v-model="configForm.stopLoss" 
                :step="0.01" 
                :precision="3"
                :max="0"
                placeholder="-10%"
                class="w-full"
              />
              <div class="form-help">最大亏损比例，建议 -5% 到 -15%</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="止盈比例" prop="takeProfit">
              <el-input-number 
                v-model="configForm.takeProfit" 
                :step="0.01" 
                :precision="3"
                :min="0"
                placeholder="20%"
                class="w-full"
              />
              <div class="form-help">目标盈利比例，建议 15% 到 30%</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="最大仓位比例" prop="maxPositionSize">
              <el-input-number 
                v-model="configForm.maxPositionSize" 
                :step="0.01" 
                :precision="3"
                :min="0.01"
                :max="1"
                placeholder="10%"
                class="w-full"
              />
              <div class="form-help">单只股票最大仓位，建议 5% 到 20%</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大持有天数" prop="maxHoldingDays">
              <el-input-number 
                v-model="configForm.maxHoldingDays" 
                :min="1" 
                :max="365"
                placeholder="30天"
                class="w-full"
              />
              <div class="form-help">避免长期套牢，建议 20 到 60 天</div>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 高级配置 -->
        <el-divider content-position="left">
          <el-icon><Tools /></el-icon>
          高级配置
        </el-divider>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="信号强度阈值" prop="signalStrengthThreshold">
              <el-slider
                v-model="configForm.signalStrengthThreshold"
                :min="0.1"
                :max="1.0"
                :step="0.1"
                show-stops
                show-input
              />
              <div class="form-help">信号强度过滤阈值，越高越严格</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="风险等级" prop="riskLevel">
              <el-select v-model="configForm.riskLevel" placeholder="选择风险等级" class="w-full">
                <el-option label="保守" value="conservative" />
                <el-option label="平衡" value="balanced" />
                <el-option label="激进" value="aggressive" />
              </el-select>
              <div class="form-help">影响整体参数的风险偏好设置</div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="启用动态调整" prop="enableDynamicAdjustment">
          <el-switch v-model="configForm.enableDynamicAdjustment" />
          <div class="form-help">根据市场环境自动调整参数</div>
        </el-form-item>

        <!-- 操作按钮 -->
        <el-form-item>
          <div class="form-actions">
            <el-button 
              type="primary" 
              @click="saveConfig" 
              :loading="saving"
              size="large"
            >
              保存配置
            </el-button>
            <el-button @click="resetConfig" size="large">
              重置默认
            </el-button>
            <el-button @click="loadConfig" size="large">
              重新加载
            </el-button>
            <el-button 
              type="success" 
              @click="testConfig" 
              :loading="testing"
              size="large"
            >
              测试配置
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 配置历史 -->
    <el-card class="config-history-card" header="配置历史">
      <el-table :data="configHistory" stripe>
        <el-table-column prop="version" label="版本" width="100" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column prop="createdBy" label="创建者" width="120" />
        <el-table-column prop="createdAt" label="创建时间" width="160">
          <template #default="scope">
            {{ formatDateTime(scope.row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column prop="isActive" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.isActive ? 'success' : ''">
              {{ scope.row.isActive ? '当前' : '历史' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="scope">
            <el-button 
              size="small" 
              @click="loadHistoryConfig(scope.row)"
              :disabled="scope.row.isActive"
            >
              加载
            </el-button>
            <el-button 
              size="small" 
              type="danger" 
              @click="deleteHistoryConfig(scope.row)"
              :disabled="scope.row.isActive"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, inject } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Setting, 
  DataAnalysis, 
  TrendCharts, 
  Warning, 
  Lock, 
  Tools 
} from '@element-plus/icons-vue'

// 注入服务
const pvfrsApi = inject('pvfrsApi')

// 响应式数据
const configFormRef = ref()
const saving = ref(false)
const testing = ref(false)

// 当前配置概览
const currentConfig = reactive({
  version: '',
  updatedAt: '',
  isActive: true,
  buySignalStrength: 0,
  sellSignalStrength: 0,
  riskLevel: 'balanced',
  winRate: 0,
  avgReturn: 0,
  maxDrawdown: 0
})

// 配置表单
const configForm = reactive({
  buyMacroDisplacementMin: 0,
  buyInstantDeviationMin: 0,
  buyRisingDaysAdvantage: true,
  buyEfficiencyMin: 0,
  buyBiasMin: 0.02,
  buyRelativeDisplacementMin: 0.05,
  buyConsecutiveDays: 3,
  sellBiasMax: 0.08,
  sellInstantDeviationMax: 0.05,
  sellPriceVolumeDivergence: true,
  stopLoss: -0.1,
  takeProfit: 0.2,
  maxPositionSize: 0.1,
  maxHoldingDays: 30,
  signalStrengthThreshold: 0.7,
  riskLevel: 'balanced',
  enableDynamicAdjustment: false
})

// 表单验证规则
const configRules = {
  buyBiasMin: [
    { required: true, message: '请输入乖离率最小值', trigger: 'blur' }
  ],
  buyConsecutiveDays: [
    { required: true, message: '请输入连续确认天数', trigger: 'blur' }
  ],
  sellBiasMax: [
    { required: true, message: '请输入乖离率最大值', trigger: 'blur' }
  ],
  stopLoss: [
    { required: true, message: '请输入止损比例', trigger: 'blur' }
  ],
  takeProfit: [
    { required: true, message: '请输入止盈比例', trigger: 'blur' }
  ],
  maxPositionSize: [
    { required: true, message: '请输入最大仓位比例', trigger: 'blur' }
  ],
  maxHoldingDays: [
    { required: true, message: '请输入最大持有天数', trigger: 'blur' }
  ]
}

// 配置历史
const configHistory = ref([])

// 发射事件
const emit = defineEmits(['config-saved'])

// 方法
const loadConfig = async () => {
  try {
    const config = await pvfrsApi.getStrategyConfig()
    
    // 更新当前配置概览
    Object.assign(currentConfig, config.overview || {})
    
    // 更新表单数据
    Object.assign(configForm, config.parameters || {})
    
    ElMessage.success('配置加载成功')
  } catch (error) {
    ElMessage.error('配置加载失败')
    console.error('配置加载失败:', error)
  }
}

const saveConfig = async () => {
  try {
    await configFormRef.value.validate()
    
    saving.value = true
    
    await pvfrsApi.saveStrategyConfig({
      parameters: configForm,
      description: `配置更新于 ${new Date().toLocaleString()}`
    })
    
    ElMessage.success('配置保存成功')
    emit('config-saved', configForm)
    
    // 重新加载配置和历史
    await loadConfig()
    await loadConfigHistory()
    
  } catch (error) {
    ElMessage.error('配置保存失败')
    console.error('配置保存失败:', error)
  } finally {
    saving.value = false
  }
}

const resetConfig = async () => {
  try {
    await ElMessageBox.confirm('确定要重置为默认配置吗？', '确认重置', {
      type: 'warning'
    })
    
    // 重置为默认值
    Object.assign(configForm, {
      buyMacroDisplacementMin: 0,
      buyInstantDeviationMin: 0,
      buyRisingDaysAdvantage: true,
      buyEfficiencyMin: 0,
      buyBiasMin: 0.02,
      buyRelativeDisplacementMin: 0.05,
      buyConsecutiveDays: 3,
      sellBiasMax: 0.08,
      sellInstantDeviationMax: 0.05,
      sellPriceVolumeDivergence: true,
      stopLoss: -0.1,
      takeProfit: 0.2,
      maxPositionSize: 0.1,
      maxHoldingDays: 30,
      signalStrengthThreshold: 0.7,
      riskLevel: 'balanced',
      enableDynamicAdjustment: false
    })
    
    ElMessage.success('已重置为默认配置')
    
  } catch (error) {
    // 用户取消
  }
}

const testConfig = async () => {
  try {
    await configFormRef.value.validate()
    
    testing.value = true
    
    const result = await pvfrsApi.testStrategyConfig(configForm)
    
    ElMessageBox.alert(
      `测试结果：
      预期胜率: ${result.expectedWinRate}%
      预期收益: ${result.expectedReturn}%
      风险评级: ${result.riskRating}
      建议: ${result.recommendation}`,
      '配置测试结果',
      { type: 'info' }
    )
    
  } catch (error) {
    ElMessage.error('配置测试失败')
    console.error('配置测试失败:', error)
  } finally {
    testing.value = false
  }
}

const loadConfigHistory = async () => {
  try {
    const history = await pvfrsApi.getConfigHistory()
    configHistory.value = history || []
  } catch (error) {
    console.error('获取配置历史失败:', error)
  }
}

const loadHistoryConfig = async (historyConfig: any) => {
  try {
    await ElMessageBox.confirm('确定要加载这个历史配置吗？当前配置将被覆盖。', '确认加载', {
      type: 'warning'
    })
    
    Object.assign(configForm, historyConfig.parameters || {})
    ElMessage.success('历史配置已加载')
    
  } catch (error) {
    // 用户取消
  }
}

const deleteHistoryConfig = async (historyConfig: any) => {
  try {
    await ElMessageBox.confirm('确定要删除这个历史配置吗？', '确认删除', {
      type: 'warning'
    })
    
    await pvfrsApi.deleteConfigHistory(historyConfig.id)
    ElMessage.success('历史配置已删除')
    await loadConfigHistory()
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除历史配置失败')
    }
  }
}

// 辅助方法
const getRiskLevelType = (level: string) => {
  const types = {
    conservative: 'success',
    balanced: 'warning',
    aggressive: 'danger'
  }
  return types[level] || 'info'
}

const getRiskLevelLabel = (level: string) => {
  const labels = {
    conservative: '保守',
    balanced: '平衡',
    aggressive: '激进'
  }
  return labels[level] || level
}

const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString()
}

// 暴露方法给父组件
defineExpose({
  loadConfig
})

// 生命周期
onMounted(() => {
  loadConfig()
  loadConfigHistory()
})
</script>

<style scoped lang="postcss">
.strategy-configuration {
  @apply space-y-6;
}

.config-overview {
  @apply mb-6;
}

.overview-card {
  @apply h-full shadow-sm;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.overview-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
}

.card-header {
  @apply flex items-center p-4 border-b border-gray-200;
}

.card-icon {
  @apply mr-2 text-blue-600;
  font-size: 20px;
}

.card-title {
  @apply font-semibold text-gray-900;
}

.card-content {
  @apply p-4 space-y-3;
}

.config-item {
  @apply flex justify-between items-center;
}

.config-label {
  @apply text-sm text-gray-600;
}

.config-value {
  @apply font-medium text-gray-900;
}

.config-form-card {
  @apply shadow-sm;
}

.config-form {
  @apply max-w-none;
}

.form-help {
  @apply text-xs text-gray-500 mt-1;
}

.form-actions {
  @apply flex gap-4 justify-center pt-6;
}

.config-history-card {
  @apply shadow-sm;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .config-overview :deep(.el-col) {
    @apply mb-4;
  }
  
  .form-actions {
    @apply flex-wrap justify-center;
  }
}

@media (max-width: 768px) {
  .card-content {
    @apply p-3 space-y-2;
  }
  
  .config-item {
    @apply flex-col items-start gap-1;
  }
  
  .config-form {
    :deep(.el-form-item__label) {
      @apply text-sm;
    }
  }
  
  .form-actions {
    @apply flex-col;
  }
  
  .form-actions .el-button {
    @apply w-full;
  }
}

/* 动画效果 */
.overview-card {
  animation: fadeInUp 0.6s ease-out;
}

.overview-card:nth-child(1) { animation-delay: 0.1s; }
.overview-card:nth-child(2) { animation-delay: 0.2s; }
.overview-card:nth-child(3) { animation-delay: 0.3s; }

.config-form-card {
  animation: slideInUp 0.6s ease-out 0.3s both;
}

.config-history-card {
  animation: slideInUp 0.6s ease-out 0.5s both;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>