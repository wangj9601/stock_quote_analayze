<template>
  <div class="pvfrs-strategy">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1>PVFRS交易策略</h1>
      <div class="header-actions">
        <el-button type="primary" @click="showHelpDialog = true">
          <el-icon><QuestionFilled /></el-icon>
          策略说明
        </el-button>
      </div>
    </div>

    <!-- 主要内容区 -->
    <el-tabs v-model="activeTab" class="strategy-tabs">
      <!-- 策略配置 -->
      <el-tab-pane label="策略配置" name="config">
        <div class="config-section">
          <el-card header="策略参数配置">
            <el-form :model="strategyConfig" label-width="200px" class="config-form">
              <!-- 买入条件 -->
              <el-divider content-position="left">买入条件</el-divider>
              
              <el-form-item label="宏观位移最小值">
                <el-input-number 
                  v-model="strategyConfig.buy_macro_displacement_min" 
                  :step="0.001" 
                  :precision="4"
                  placeholder="Δ > 0"
                />
              </el-form-item>
              
              <el-form-item label="即时偏离度最小值">
                <el-input-number 
                  v-model="strategyConfig.buy_instant_deviation_min" 
                  :step="0.001" 
                  :precision="4"
                  placeholder="d20 > d"
                />
              </el-form-item>
              
              <el-form-item label="上涨频率优势">
                <el-switch v-model="strategyConfig.buy_rising_days_advantage" />
                <span class="form-help">Z > F（上涨天数 > 下跌天数）</span>
              </el-form-item>
              
              <el-form-item label="效率最小值">
                <el-input-number 
                  v-model="strategyConfig.buy_efficiency_min" 
                  :step="0.001" 
                  :precision="4"
                  placeholder="m20 > m"
                />
              </el-form-item>
              
              <el-form-item label="乖离率最小值">
                <el-input-number 
                  v-model="strategyConfig.buy_bias_min" 
                  :step="0.001" 
                  :precision="4"
                  placeholder="bias > 2%"
                />
              </el-form-item>
              
              <el-form-item label="相对位移最小值">
                <el-input-number 
                  v-model="strategyConfig.buy_relative_displacement_min" 
                  :step="0.001" 
                  :precision="4"
                  placeholder="Δ/d > 5%"
                />
              </el-form-item>
              
              <el-form-item label="连续确认天数">
                <el-input-number 
                  v-model="strategyConfig.buy_consecutive_days" 
                  :min="1" 
                  :max="10"
                  placeholder="连续3天确认"
                />
              </el-form-item>

              <!-- 卖出条件 -->
              <el-divider content-position="left">卖出条件</el-divider>
              
              <el-form-item label="乖离率最大值">
                <el-input-number 
                  v-model="strategyConfig.sell_bias_max" 
                  :step="0.001" 
                  :precision="4"
                  placeholder="bias > 8%"
                />
              </el-form-item>
              
              <el-form-item label="即时偏离度最大值">
                <el-input-number 
                  v-model="strategyConfig.sell_instant_deviation_max" 
                  :step="0.001" 
                  :precision="4"
                  placeholder="d20 - d > 5%"
                />
              </el-form-item>
              
              <el-form-item label="价涨量缩背离">
                <el-switch v-model="strategyConfig.sell_price_volume_divergence" />
              </el-form-item>

              <!-- 风控参数 -->
              <el-divider content-position="left">风控参数</el-divider>
              
              <el-form-item label="止损比例">
                <el-input-number 
                  v-model="strategyConfig.stop_loss" 
                  :step="0.01" 
                  :precision="3"
                  placeholder="-10%"
                />
              </el-form-item>
              
              <el-form-item label="止盈比例">
                <el-input-number 
                  v-model="strategyConfig.take_profit" 
                  :step="0.01" 
                  :precision="3"
                  placeholder="20%"
                />
              </el-form-item>
              
              <el-form-item label="最大仓位比例">
                <el-input-number 
                  v-model="strategyConfig.max_position_size" 
                  :step="0.01" 
                  :precision="3"
                  :min="0.01"
                  :max="1"
                  placeholder="10%"
                />
              </el-form-item>
              
              <el-form-item label="最大持有天数">
                <el-input-number 
                  v-model="strategyConfig.max_holding_days" 
                  :min="1" 
                  :max="365"
                  placeholder="30天"
                />
              </el-form-item>
            </el-form>
            
            <div class="config-actions">
              <el-button type="primary" @click="saveConfig" :loading="saving">
                保存配置
              </el-button>
              <el-button @click="resetConfig">
                重置默认
              </el-button>
              <el-button @click="loadConfig">
                重新加载
              </el-button>
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- 回测任务 -->
      <el-tab-pane label="回测任务" name="backtest">
        <div class="backtest-section">
          <el-row :gutter="20">
            <!-- 回测配置 -->
            <el-col :span="12">
              <el-card header="回测配置">
                <el-form :model="backtestForm" label-width="120px">
                  <el-form-item label="回测模式">
                    <el-radio-group v-model="backtestForm.mode">
                      <el-radio label="single">单股回测</el-radio>
                      <el-radio label="batch">批量回测</el-radio>
                      <el-radio label="optimize">参数优化</el-radio>
                    </el-radio-group>
                  </el-form-item>
                  
                  <el-form-item label="股票代码" v-if="backtestForm.mode === 'single'">
                    <el-input 
                      v-model="backtestForm.code" 
                      placeholder="例如：688256"
                    />
                  </el-form-item>
                  
                  <el-form-item label="批量股票" v-if="backtestForm.mode === 'batch'">
                    <el-tabs v-model="batchInputMode" type="border-card">
                      <el-tab-pane label="文件上传" name="upload">
                        <el-upload
                          class="upload-demo"
                          drag
                          :auto-upload="false"
                          :on-change="handleStockFileChange"
                          accept=".txt,.csv"
                        >
                          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                          <div class="el-upload__text">
                            将股票列表文件拖到此处，或<em>点击上传</em>
                          </div>
                          <template #tip>
                            <div class="el-upload__tip">
                              支持 txt/csv 文件，每行一个股票代码（如：688256 或 600519）
                            </div>
                          </template>
                        </el-upload>
                        <div v-if="uploadedStocks.length > 0" style="margin-top: 10px;">
                          <el-alert
                            title="已上传股票列表"
                            type="success"
                            :closable="false"
                            show-icon
                          >
                            <template #default>
                              <div style="max-height: 100px; overflow-y: auto;">
                                {{ uploadedStocks.join(', ') }}
                              </div>
                              <div style="margin-top: 5px;">
                                共 {{ uploadedStocks.length }} 只股票
                              </div>
                            </template>
                          </el-alert>
                        </div>
                      </el-tab-pane>
                      
                      <el-tab-pane label="手动录入" name="manual">
                        <el-input
                          v-model="batchStockCodes"
                          type="textarea"
                          :rows="6"
                          placeholder="请输入股票代码，每行一个，例如：&#10;688256&#10;600519&#10;000001&#10;300750"
                        />
                        <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center;">
                          <span style="color: #909399; font-size: 12px;">
                            支持 A 股（6 位数字）和港股（5 位数字）
                          </span>
                          <el-button 
                            type="primary" 
                            size="small" 
                            @click="parseBatchStocks"
                            :disabled="!batchStockCodes.trim()"
                          >
                            解析股票代码
                          </el-button>
                        </div>
                        <div v-if="parsedStocks.length > 0" style="margin-top: 10px;">
                          <el-alert
                            title="已解析股票列表"
                            type="success"
                            :closable="false"
                            show-icon
                          >
                            <template #default>
                              <div style="max-height: 100px; overflow-y: auto;">
                                {{ parsedStocks.join(', ') }}
                              </div>
                              <div style="margin-top: 5px;">
                                共 {{ parsedStocks.length }} 只股票
                              </div>
                            </template>
                          </el-alert>
                        </div>
                      </el-tab-pane>
                    </el-tabs>
                  </el-form-item>
                  
                  <el-form-item label="市场类型">
                    <el-select v-model="backtestForm.market">
                      <el-option label="A股" value="CN" />
                      <el-option label="港股" value="HK" />
                    </el-select>
                  </el-form-item>
                  
                  <el-form-item label="开始日期">
                    <el-date-picker
                      v-model="backtestForm.startDate"
                      type="date"
                      placeholder="选择开始日期"
                      format="YYYY-MM-DD"
                      value-format="YYYY-MM-DD"
                    />
                  </el-form-item>
                  
                  <el-form-item label="结束日期">
                    <el-date-picker
                      v-model="backtestForm.endDate"
                      type="date"
                      placeholder="选择结束日期"
                      format="YYYY-MM-DD"
                      value-format="YYYY-MM-DD"
                    />
                  </el-form-item>
                  
                  <el-form-item label="初始资金">
                    <el-input-number
                      v-model="backtestForm.initialCapital"
                      :min="10000"
                      :step="10000"
                      placeholder="100000"
                    />
                  </el-form-item>
                </el-form>
                
                <div class="backtest-actions">
                  <!-- 调试信息 -->
                  <div v-if="backtestForm.mode === 'batch'" style="margin-bottom: 10px; font-size: 12px; color: #909399;">
                    调试: {{ batchInputMode === 'manual' ? `手动模式(${parsedStocks.length}只)` : `上传模式(${uploadedStocks.length}只)` }} 
                    | 按钮{{ canStartBacktest ? '可' : '不可' }}点击
                  </div>
                  
                  <el-button 
                    type="primary" 
                    @click="startBacktest" 
                    :loading="backtestLoading"
                    :disabled="!canStartBacktest"
                  >
                    开始回测
                  </el-button>
                  <el-button @click="resetBacktestForm">
                    重置
                  </el-button>
                </div>
              </el-card>
            </el-col>
            
            <!-- 任务状态 -->
            <el-col :span="12">
              <el-card header="任务状态">
                <div v-if="currentTask" class="task-status">
                  <el-steps :active="currentTask.step || 0" align-center>
                    <el-step title="数据准备" />
                    <el-step title="信号生成" />
                    <el-step title="回测执行" />
                    <el-step title="结果分析" />
                  </el-steps>
                  
                  <div class="task-progress">
                    <el-progress 
                      :percentage="currentTask?.progress_percentage || currentTask?.progress || 0" 
                      :status="progressStatus"
                    />
                    <p class="task-message">{{ currentTask.current_step || currentTask.message }}</p>
                  </div>
                  
                  <div v-if="currentTask.log" class="task-log">
                    <el-scrollbar height="200px">
                      <pre>{{ currentTask.log }}</pre>
                    </el-scrollbar>
                  </div>
                </div>
                
                <div v-else class="no-task">
                  <el-empty description="暂无运行中的任务" />
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <!-- 回测结果 -->
      <el-tab-pane label="回测结果" name="results">
        <div class="results-section">
          <el-row :gutter="20">
            <!-- 结果列表 -->
            <el-col :span="8">
              <el-card header="历史回测">
                <div class="results-list">
                  <div 
                    v-for="result in backtestResults" 
                    :key="result.id"
                    class="result-item"
                    @click="selectResult(result)"
                    :class="{ active: selectedResult?.id === result.id }"
                  >
                    <div class="result-header">
                      <span class="result-code">{{ result.code }}</span>
                      <span class="result-date">{{ result.date }}</span>
                      <el-tag 
                        :type="(result.totalReturn ?? 0) > 0 ? 'success' : 'danger'"
                        size="small"
                      >
                        {{ formatPercent(result.totalReturn, 2) }}
                      </el-tag>
                    </div>
                    <div class="result-stats">
                      <span>年化: {{ formatPercent(result.annualReturn, 2) }}</span>
                      <span>夏普: {{ formatNumber(result.sharpeRatio, 2) }}</span>
                      <span>胜率: {{ formatPercent(result.winRate, 1) }}</span>
                    </div>
                  </div>
                </div>
                
                <div class="results-actions">
                  <el-button size="small" @click="loadResults">
                    <el-icon><Refresh /></el-icon>
                    刷新
                  </el-button>
                  <el-button size="small" @click="clearResults" type="danger">
                    <el-icon><Delete /></el-icon>
                    清空
                  </el-button>
                </div>
              </el-card>
            </el-col>
            
            <!-- 结果详情 -->
            <el-col :span="16">
              <el-card v-if="selectedResult" header="回测详情">
                <div class="result-details">
                  <!-- 基本指标 -->
                  <el-descriptions :column="2" border>
                    <el-descriptions-item label="股票代码">
                      {{ selectedResult.code }}
                    </el-descriptions-item>
                    <el-descriptions-item label="市场类型">
                      {{ selectedResult.market }}
                    </el-descriptions-item>
                    <el-descriptions-item label="回测期间">
                      {{ selectedResult.startDate }} 至 {{ selectedResult.endDate }}
                    </el-descriptions-item>
                    <el-descriptions-item label="初始资金">
                      ¥{{ selectedResult.initialCapital?.toLocaleString() }}
                    </el-descriptions-item>
                    <el-descriptions-item label="最终资金">
                      ¥{{ selectedResult.finalCapital?.toLocaleString() }}
                    </el-descriptions-item>
                    <el-descriptions-item label="总收益率">
                      <span :class="(selectedResult.totalReturn ?? 0) > 0 ? 'text-success' : 'text-danger'">
                        {{ formatPercent(selectedResult.totalReturn, 2) }}
                      </span>
                    </el-descriptions-item>
                    <el-descriptions-item label="年化收益率">
                      <span :class="(selectedResult.annualReturn ?? 0) > 0 ? 'text-success' : 'text-danger'">
                        {{ formatPercent(selectedResult.annualReturn, 2) }}
                      </span>
                    </el-descriptions-item>
                    <el-descriptions-item label="最大回撤">
                      {{ formatPercent(selectedResult.maxDrawdown, 2) }}
                    </el-descriptions-item>
                    <el-descriptions-item label="夏普比率">
                      {{ formatNumber(selectedResult.sharpeRatio, 2) }}
                    </el-descriptions-item>
                    <el-descriptions-item label="胜率">
                      {{ formatPercent(selectedResult.winRate, 1) }}
                    </el-descriptions-item>
                    <el-descriptions-item label="盈亏比">
                      {{ formatNumber(selectedResult.profitFactor, 2) }}
                    </el-descriptions-item>
                    <el-descriptions-item label="交易次数">
                      {{ selectedResult.totalTrades }}
                    </el-descriptions-item>
                    <el-descriptions-item label="平均持有天数">
                      {{ formatNumber(selectedResult.avgHoldingPeriod, 1) }}天
                    </el-descriptions-item>
                  </el-descriptions>
                  
                  <!-- 操作按钮 -->
                  <div class="result-actions">
                    <el-button type="primary" @click="showDetailedTrades">
                      查看交易明细
                    </el-button>
                    <el-button @click="showEquityCurve">
                      查看收益曲线
                    </el-button>
                    <el-button @click="exportReport">
                      导出报告
                    </el-button>
                  </div>
                </div>
              </el-card>
              
              <el-card v-else header="请选择回测结果">
                <el-empty description="选择左侧历史回测结果查看详情" />
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <!-- 交易明细 -->
      <el-tab-pane label="交易明细" name="trades" :disabled="!selectedResult">
        <div class="trades-section">
          <el-card v-if="selectedResult" :header="`交易明细 - ${selectedResult.code}`">
            <el-table :data="selectedResultTrades" stripe style="width: 100%">
              <el-table-column prop="entryDate" label="买入日期" width="120" />
              <el-table-column prop="exitDate" label="卖出日期" width="120" />
              <el-table-column prop="entryPrice" label="买入价格" width="100">
                <template #default="scope">
                  ¥{{ scope.row.entryPrice?.toFixed(2) }}
                </template>
              </el-table-column>
              <el-table-column prop="exitPrice" label="卖出价格" width="100">
                <template #default="scope">
                  ¥{{ scope.row.exitPrice?.toFixed(2) }}
                </template>
              </el-table-column>
              <el-table-column prop="pnl" label="盈亏金额" width="120">
                <template #default="scope">
                  <span :class="scope.row.pnl > 0 ? 'text-success' : 'text-danger'">
                    ¥{{ scope.row.pnl?.toFixed(2) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="pnlPercent" label="盈亏比例" width="120">
                <template #default="scope">
                  <span :class="scope.row.pnlPercent > 0 ? 'text-success' : 'text-danger'">
                    {{ (scope.row.pnlPercent * 100).toFixed(2) }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="holdingDays" label="持有天数" width="100" />
              <el-table-column prop="exitReason" label="退出原因" />
            </el-table>
          </el-card>
          <el-card v-else>
            <el-empty description="请先在'回测结果'中选择一个结果" />
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 帮助对话框 -->
    <el-dialog
      v-model="showHelpDialog"
      title="PVFARS策略说明"
      width="80%"
      :before-close="handleHelpClose"
    >
      <div class="help-content">
        <el-tabs>
          <el-tab-pane label="策略概述" name="overview">
            <div class="help-section">
              <h3>PVFARS（量价频幅度共振）策略</h3>
              <p>
                PVFARS策略基于量价频幅度共振理论，将"高效率上涨"定义为市场在价格方向、微观共识与资金动力三个维度达成向上共振的状态，并结合幅度分析、横盘识别与风险预警。
              </p>
              
              <h4>三个维度</h4>
              <ul>
                <li><strong>价格维度</strong>：宏观位移 + 即时强度</li>
                <li><strong>频率维度</strong>：上涨频率优势</li>
                <li><strong>成交量维度</strong>：进出效率验证</li>
              </ul>
              
              <h4>买入条件</h4>
              <p>当三个维度同时满足以下条件时，认为进入高效率演化轨道：</p>
              <ul>
                <li>宏观位移 Δ > 0（期末价格 > 起始价格）</li>
                <li>即时强度 d20 > d（当前价格 > 20日均线）</li>
                <li>上涨频率 Z > F（上涨天数 > 下跌天数）</li>
                <li>进出效率 m20 > m（当前成交量 > 20日平均量）</li>
              </ul>
            </div>
          </el-tab-pane>
          
          <el-tab-pane label="参数说明" name="params">
            <div class="help-section">
              <h3>策略参数说明</h3>
              <el-descriptions :column="1" border>
                <el-descriptions-item label="buy_bias_min">
                  买入乖离率最小值，默认2%，过滤幅度不足的信号
                </el-descriptions-item>
                <el-descriptions-item label="buy_consecutive_days">
                  连续确认天数，默认3天，提高信号可靠性
                </el-descriptions-item>
                <el-descriptions-item label="sell_bias_max">
                  卖出乖离率最大值，默认8%，超买回调
                </el-descriptions-item>
                <el-descriptions-item label="stop_loss">
                  止损比例，默认-10%，控制下行风险
                </el-descriptions-item>
                <el-descriptions-item label="take_profit">
                  止盈比例，默认20%，锁定收益
                </el-descriptions-item>
                <el-descriptions-item label="max_position_size">
                  最大仓位比例，默认10%，分散风险
                </el-descriptions-item>
                <el-descriptions-item label="max_holding_days">
                  最大持有天数，默认30天，避免长期套牢
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </el-tab-pane>
          
          <el-tab-pane label="使用指南" name="guide">
            <div class="help-section">
              <h3>使用指南</h3>
              <h4>1. 策略配置</h4>
              <p>在"策略配置"标签页中调整各项参数，点击"保存配置"生效。</p>
              
              <h4>2. 回测任务</h4>
              <p>在"回测任务"标签页中选择回测模式：</p>
              <ul>
                <li><strong>单股回测</strong>：测试单只股票的历史表现</li>
                <li><strong>批量回测</strong>：测试多只股票的整体表现</li>
                <li><strong>参数优化</strong>：网格搜索最优参数组合</li>
              </ul>
              
              <h4>3. 结果分析</h4>
              <p>在"回测结果"标签页查看历史回测结果，包括：</p>
              <ul>
                <li>基本指标：收益率、夏普比率、最大回撤等</li>
                <li>交易明细：每一笔买入卖出的详细信息</li>
                <li>收益曲线：资金变化的可视化展示</li>
              </ul>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-dialog>

    <!-- 收益曲线对话框 -->
    <el-dialog
      v-model="showChartDialog"
      title="收益曲线"
      width="80%"
    >
      <div ref="chartContainer" class="chart-container"></div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { API_BASE } from '../config/api'
import { useAuthStore } from '@/stores/auth'
import { 
  QuestionFilled, 
  Refresh, 
  Delete, 
  UploadFilled 
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'

const authStore = useAuthStore()

const getAuthToken = () => {
  return authStore.token || localStorage.getItem('admin_token')
}

const getAuthHeaders = (): Record<string, string> => {
  const t = getAuthToken()
  return (t ? { Authorization: `Bearer ${t}` } : {}) as Record<string, string>
}

const toNumberOrNull = (v: any): number | null => {
  if (v === null || v === undefined || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

const formatNumber = (v: any, digits = 2): string => {
  const n = toNumberOrNull(v)
  if (n === null) return 'N/A'
  return n.toFixed(digits)
}

const formatPercent = (v: any, digits = 2): string => {
  const n = toNumberOrNull(v)
  if (n === null) return 'N/A'
  return `${(n * 100).toFixed(digits)}%`
}

const normalizeBacktestResult = (raw: any) => {
  const totalReturn = toNumberOrNull(raw.totalReturn ?? raw.total_return) ?? 0
  const annualReturn = toNumberOrNull(raw.annualReturn ?? raw.annual_return) ?? 0
  const maxDrawdown = toNumberOrNull(raw.maxDrawdown ?? raw.max_drawdown) ?? 0

  return {
    ...raw,
    code: raw.code ?? raw.stock_code ?? raw.stockCode,
    market: raw.market ?? raw.market_type ?? raw.marketType,
    startDate: raw.startDate ?? raw.start_date,
    endDate: raw.endDate ?? raw.end_date,
    initialCapital: toNumberOrNull(raw.initialCapital ?? raw.initial_capital),
    finalCapital: toNumberOrNull(raw.finalCapital ?? raw.final_capital),
    totalReturn,
    annualReturn,
    maxDrawdown,
    sharpeRatio: toNumberOrNull(raw.sharpeRatio ?? raw.sharpe_ratio),
    winRate: toNumberOrNull(raw.winRate ?? raw.win_rate),
    profitFactor: toNumberOrNull(raw.profitFactor ?? raw.profit_factor),
    totalTrades: raw.totalTrades ?? raw.total_trades,
    avgHoldingPeriod: toNumberOrNull(raw.avgHoldingPeriod ?? raw.avg_holding_period),
    equityCurve: raw.equityCurve ?? raw.equity_curve,
    trades: raw.trades ?? []
  }
}

// 任务与结果类型（与后端字段兼容）
interface BacktestTask {
  id?: string | number
  task_id?: string | number
  status?: string
  step?: number
  progress?: number
  progress_percentage?: number
  current_step?: string
  message?: string
  log?: string
  [key: string]: unknown
}

interface BacktestResult {
  id?: string | number
  code?: string
  market?: string
  startDate?: string
  endDate?: string
  initialCapital?: number | null
  finalCapital?: number | null
  totalReturn?: number
  annualReturn?: number | null
  maxDrawdown?: number | null
  sharpeRatio?: number | null
  winRate?: number | null
  profitFactor?: number | null
  totalTrades?: number
  avgHoldingPeriod?: number | null
  equityCurve?: Array<{ date: string; equity: number }>
  taskId?: string | number
  [key: string]: unknown
}

// 响应式数据
const activeTab = ref('config')
const showHelpDialog = ref(false)
const showChartDialog = ref(false)
const chartContainer = ref<HTMLElement>()
const saving = ref(false)
const backtestLoading = ref(false)

// 策略配置
const strategyConfig = reactive({
  buy_macro_displacement_min: 0,
  buy_instant_deviation_min: 0,
  buy_rising_days_advantage: true,
  buy_efficiency_min: 0,
  buy_bias_min: 0.02,
  buy_relative_displacement_min: 0.05,
  buy_consecutive_days: 3,
  sell_bias_max: 0.08,
  sell_instant_deviation_max: 0.05,
  sell_price_volume_divergence: true,
  stop_loss: -0.1,
  take_profit: 0.2,
  max_position_size: 0.1,
  max_holding_days: 30
})

// 回测表单
const backtestForm = reactive({
  mode: 'single',
  code: '',
  market: 'CN',
  startDate: '',
  endDate: '',
  initialCapital: 100000,
  stockFile: null
})

// 批量录入相关
const batchInputMode = ref('upload')
const uploadedStocks = ref<string[]>([])
const parsedStocks = ref<string[]>([])
const batchStockCodes = ref('')

// 当前任务
const currentTask = ref<BacktestTask | null>(null)

// 回测结果
const backtestResults = ref<BacktestResult[]>([])
const selectedResult = ref<BacktestResult | null>(null)
const selectedResultTrades = ref<any[]>([])

// 计算属性
const canStartBacktest = computed(() => {
  if (!backtestForm.startDate || !backtestForm.endDate) {
    return false
  }
  
  if (backtestForm.mode === 'single') {
    return backtestForm.code.trim() !== ''
  } else if (backtestForm.mode === 'batch') {
    // 批量模式：检查文件上传或手动录入
    const hasFile = backtestForm.stockFile !== null
    const hasManualStocks = batchInputMode.value === 'manual' && parsedStocks.value.length > 0
    const hasUploadedStocks = batchInputMode.value === 'upload' && uploadedStocks.value.length > 0
    return hasFile || hasManualStocks || hasUploadedStocks
  } else if (backtestForm.mode === 'optimize') {
    return backtestForm.code.trim() !== ''
  }
  return false
})

const progressStatus = computed(() => {
  const status = (currentTask.value as any)?.status
  if (!status) return ''
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  if (status === 'cancelled') return 'warning'
  return ''
})

// 方法
const loadConfig = async () => {
  try {
    const response = await fetch(`${API_BASE}/api/admin/pvfrs/config`, {
      headers: {
        ...getAuthHeaders()
      }
    })
    const config = await response.json()
    Object.assign(strategyConfig, config.strategy_params || {})
    ElMessage.success('配置加载成功')
  } catch (error) {
    ElMessage.error('配置加载失败')
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    const response = await fetch(`${API_BASE}/api/admin/pvfrs/config`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify({
        strategy_params: strategyConfig
      })
    })
    
    if (response.ok) {
      ElMessage.success('配置保存成功')
    } else {
      ElMessage.error('配置保存失败')
    }
  } catch (error) {
    ElMessage.error('配置保存失败')
  } finally {
    saving.value = false
  }
}

const resetConfig = () => {
  ElMessageBox.confirm('确定要重置为默认配置吗？', '确认重置', {
    type: 'warning'
  }).then(() => {
    // 重置为默认值
    Object.assign(strategyConfig, {
      buy_macro_displacement_min: 0,
      buy_instant_deviation_min: 0,
      buy_rising_days_advantage: true,
      buy_efficiency_min: 0,
      buy_bias_min: 0.02,
      buy_relative_displacement_min: 0.05,
      buy_consecutive_days: 3,
      sell_bias_max: 0.08,
      sell_instant_deviation_max: 0.05,
      sell_price_volume_divergence: true,
      stop_loss: -0.1,
      take_profit: 0.2,
      max_position_size: 0.1,
      max_holding_days: 30
    })
    ElMessage.success('已重置为默认配置')
  })
}

const handleStockFileChange = async (file: any) => {
  backtestForm.stockFile = file.raw
  
  // 解析上传的文件内容
  try {
    const text = await readFileContent(file.raw)
    const stocks = parseStockCodes(text)
    uploadedStocks.value = stocks
    ElMessage.success(`成功解析 ${stocks.length} 只股票`)
  } catch (error) {
    ElMessage.error('文件解析失败，请检查文件格式')
    uploadedStocks.value = []
  }
}

const readFileContent = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      if (e.target?.result) {
        resolve(e.target.result as string)
      } else {
        reject(new Error('文件读取失败'))
      }
    }
    reader.onerror = () => reject(new Error('文件读取错误'))
    reader.readAsText(file, 'utf-8')
  })
}

const parseStockCodes = (text: string): string[] => {
  const lines = text.split('\n')
  const stocks: string[] = []
  
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed) {
      // 支持多种格式：纯数字、带后缀的代码
      const code = trimmed.replace(/[^\d]/g, '') // 只保留数字
      if (code.length >= 5 && code.length <= 6) {
        stocks.push(code)
      }
    }
  }
  
  // 去重并排序
  return [...new Set(stocks)].sort()
}

const parseBatchStocks = () => {
  try {
    const stocks = parseStockCodes(batchStockCodes.value)
    parsedStocks.value = stocks
    if (stocks.length > 0) {
      ElMessage.success(`成功解析 ${stocks.length} 只股票`)
    } else {
      ElMessage.warning('未找到有效的股票代码')
    }
  } catch (error) {
    ElMessage.error('股票代码解析失败')
    parsedStocks.value = []
  }
}

const startBacktest = async () => {
  backtestLoading.value = true
  
  try {
    const token = getAuthToken()
    if (!token) {
      ElMessage.error('请先登录')
      return
    }

    // 验证输入
    if (backtestForm.mode === 'single' && !backtestForm.code.trim()) {
      ElMessage.error('请输入股票代码')
      backtestLoading.value = false
      return
    }
    
    const requestData: Record<string, unknown> = {
      mode: backtestForm.mode,
      market: backtestForm.market,
      start_date: backtestForm.startDate,
      end_date: backtestForm.endDate,
      initial_capital: backtestForm.initialCapital
    }
    
    if (backtestForm.mode === 'single') {
      requestData.code = backtestForm.code
    } else if (backtestForm.mode === 'batch') {
      const stocks = batchInputMode.value === 'upload' ? uploadedStocks.value : parsedStocks.value
      if (stocks.length === 0) {
        ElMessage.error('请提供股票代码列表')
        backtestLoading.value = false
        return
      }
      
      if (batchInputMode.value === 'upload' && backtestForm.stockFile) {
        // 文件上传方式
        const formData = new FormData()
        Object.keys(requestData).forEach(key => {
          formData.append(key, String(requestData[key] ?? ''))
        })
        formData.append('stock_file', backtestForm.stockFile)
        
        const response = await fetch(`${API_BASE}/api/admin/pvfrs/backtest/upload`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`
          },
          body: formData
        })
        
        const result = await response.json()
        if (response.ok) {
          ElMessage.success('回测任务提交成功')
          currentTask.value = result.data || result
          pollTaskStatus()
        } else {
          ElMessage.error(result.detail || '回测任务提交失败')
        }
        
        backtestLoading.value = false
        return
      } else {
        // 手动录入方式，直接发送股票代码列表
        requestData.stock_codes = stocks
      }
    } else if (backtestForm.mode === 'optimize') {
      requestData.code = backtestForm.code
    }
    
    const response = await fetch(`${API_BASE}/api/admin/pvfrs/backtest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(requestData)
    })
    
    const result = await response.json()
    if (response.ok) {
      ElMessage.success('回测任务提交成功')
      currentTask.value = result.data || result
      pollTaskStatus()
    } else {
      ElMessage.error(result.detail || '回测任务提交失败')
    }
  } catch (error) {
    ElMessage.error('回测任务提交失败')
    console.error(error)
  } finally {
    backtestLoading.value = false
  }
}

const pollTaskStatus = async () => {
  if (!currentTask.value) return
  
  const taskId = currentTask.value.task_id || currentTask.value.id
  if (!taskId) {
    console.error('无法获取任务ID:', currentTask.value)
    return
  }
  
  try {
    const response = await fetch(`${API_BASE}/api/admin/pvfrs/backtest/progress/${taskId}`, {
      headers: {
        ...getAuthHeaders()
      }
    })
    const task = await response.json()
    
    // 更新当前任务状态，使用data字段中的实际任务数据
    currentTask.value = task.data || task
    
    const taskData = task.data || task
    if (taskData.status === 'completed') {
      ElMessage.success('回测完成')
      loadResults()
    } else if (taskData.status === 'failed') {
      ElMessage.error('回测失败')
    } else {
      // 继续轮询
      setTimeout(pollTaskStatus, 2000)
    }
  } catch (error) {
    console.error('轮询任务状态失败:', error)
  }
}

const resetBacktestForm = () => {
  Object.assign(backtestForm, {
    mode: 'single',
    code: '',
    market: 'CN',
    startDate: '',
    endDate: '',
    initialCapital: 100000,
    stockFile: null
  })
  
  // 重置批量录入相关状态
  batchInputMode.value = 'upload'
  uploadedStocks.value = []
  parsedStocks.value = []
  batchStockCodes.value = ''
}

const loadResults = async () => {
  try {
    const response = await fetch(`${API_BASE}/api/admin/pvfrs/reports`, {
      headers: {
        ...getAuthHeaders()
      }
    })
    const result = await response.json()
    
    // 处理增强版API的响应格式
    if (result.success && result.data) {
      backtestResults.value = Array.isArray(result.data)
        ? result.data.map(normalizeBacktestResult)
        : []
    } else {
      backtestResults.value = []
    }
  } catch (error) {
    ElMessage.error('获取回测结果失败')
    console.error('获取回测结果失败:', error)
  }
}

const selectResult = async (result: any) => {
  selectedResult.value = result
  selectedResultTrades.value = [] // 先清空
  
  // 获取交易明细
  if (result.taskId) {
    try {
      const response = await fetch(`${API_BASE}/api/admin/pvfrs/backtest/trades/${result.taskId}`, {
        headers: {
          ...getAuthHeaders()
        }
      })
      
      if (response.ok) {
        const tradesData = await response.json()
        if (tradesData.success && tradesData.data) {
          selectedResultTrades.value = Array.isArray(tradesData.data) ? tradesData.data : []
        }
      } else {
        console.warn('获取交易明细失败:', response.status)
      }
    } catch (error) {
      console.error('获取交易明细异常:', error)
    }
  }
}

const clearResults = async () => {
  ElMessageBox.confirm('确定要清空所有回测结果吗？此操作不可恢复！', '确认清空', {
    type: 'warning'
  }).then(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/admin/pvfrs/reports?confirm=true`, {
        method: 'DELETE',
        headers: {
          ...getAuthHeaders()
        }
      })
      
      if (response.ok) {
        ElMessage.success('回测结果已清空')
        loadResults()
      } else {
        ElMessage.error('清空失败')
      }
    } catch (error) {
      ElMessage.error('清空失败')
      console.error('清空失败:', error)
    }
  })
}

const showDetailedTrades = () => {
  activeTab.value = 'trades'
}

const showEquityCurve = async () => {
  showChartDialog.value = true
  
  await nextTick()
  
  if (chartContainer.value && selectedResult.value?.equityCurve) {
    const chart = echarts.init(chartContainer.value)
    
    const option = {
      title: {
        text: `${selectedResult.value.code} 收益曲线`
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const data = params[0]
          return `日期: ${data.name}<br/>权益: ¥${data.value?.toFixed(2)}`
        }
      },
      xAxis: {
        type: 'category',
        data: selectedResult.value.equityCurve.map((item: any) => item.date)
      },
      yAxis: {
        type: 'value',
        name: '权益资金'
      },
      series: [{
        name: '权益资金',
        type: 'line',
        data: selectedResult.value.equityCurve.map((item: any) => item.equity),
        smooth: true
      }]
    }
    
    chart.setOption(option)
    
    // 响应式调整
    window.addEventListener('resize', () => {
      chart.resize()
    })
  }
}

const exportReport = () => {
  if (!selectedResult.value) return
  
  const reportContent = generateReport(selectedResult.value)
  
  const blob = new Blob([reportContent], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `PVFARS回测报告_${selectedResult.value.code}_${new Date().toISOString().split('T')[0]}.md`
  link.click()
  URL.revokeObjectURL(url)
}

const generateReport = (result: any) => {
  return `# PVFARS策略回测报告

## 基本信息
- 股票代码: ${result.code}
- 市场类型: ${result.market}
- 回测期间: ${result.startDate} 至 ${result.endDate}
- 初始资金: ¥${result.initialCapital?.toLocaleString()}
- 最终资金: ¥${result.finalCapital?.toLocaleString()}

## 收益表现
- 总收益率: ${(result.totalReturn * 100).toFixed(2)}%
- 年化收益率: ${(result.annualReturn * 100).toFixed(2)}%
- 最大回撤: ${(result.maxDrawdown * 100).toFixed(2)}%
- 夏普比率: ${result.sharpeRatio?.toFixed(2) || 'N/A'}

## 交易统计
- 交易次数: ${result.totalTrades}
- 胜率: ${(result.winRate * 100).toFixed(1)}%
- 盈亏比: ${result.profitFactor?.toFixed(2) || 'N/A'}
- 平均持有天数: ${result.avgHoldingPeriod?.toFixed(1)}天

## 交易明细
${result.trades?.map((trade: any, index: number) => `
${index + 1}. ${trade.entryDate} -> ${trade.exitDate}
   买入: ¥${trade.entryPrice?.toFixed(2)}
   卖出: ¥${trade.exitPrice?.toFixed(2)}
   盈亏: ¥${trade.pnl?.toFixed(2)} (${(trade.pnlPercent * 100).toFixed(2)}%)
   原因: ${trade.exitReason}
`).join('\n') || '无交易记录'}

---
*报告生成时间: ${new Date().toLocaleString()}*
`
}

const handleHelpClose = () => {
  showHelpDialog.value = false
}

// 生命周期
onMounted(() => {
  loadConfig()
  loadResults()
})
</script>

<style scoped>
.pvfrs-strategy {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.strategy-tabs {
  margin-top: 20px;
}

.config-section {
  max-width: 800px;
}

.config-form {
  max-width: 600px;
}

.form-help {
  font-size: 12px;
  color: #909399;
  margin-left: 10px;
}

.config-actions {
  margin-top: 20px;
  text-align: center;
}

.backtest-section {
  margin-top: 20px;
}

.backtest-actions {
  margin-top: 20px;
  text-align: center;
}

.task-status {
  padding: 20px;
}

.task-progress {
  margin: 20px 0;
}

.task-message {
  margin-top: 10px;
  font-size: 14px;
  color: #606266;
}

.task-log {
  margin-top: 20px;
}

.task-log pre {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.4;
}

.no-task {
  padding: 40px;
}

.results-section {
  margin-top: 20px;
}

.results-list {
  max-height: 400px;
  overflow-y: auto;
}

.result-item {
  padding: 15px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  margin-bottom: 10px;
  cursor: pointer;
  transition: all 0.3s;
}

.result-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 4px rgba(64, 158, 255, 0.12);
}

.result-item.active {
  border-color: #409eff;
  background-color: #f0f9ff;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.result-code {
  font-weight: bold;
  font-size: 16px;
}

.result-date {
  font-size: 12px;
  color: #909399;
}

.result-stats {
  display: flex;
  gap: 15px;
  font-size: 12px;
  color: #606266;
}

.results-actions {
  margin-top: 15px;
  text-align: center;
}

.result-details {
  padding: 20px;
}

.result-actions {
  margin-top: 20px;
  text-align: center;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}

.help-content {
  max-height: 60vh;
  overflow-y: auto;
}

.help-section {
  padding: 20px;
}

.help-section h3 {
  color: #303133;
  margin-bottom: 15px;
}

.help-section h4 {
  color: #606266;
  margin: 15px 0 10px 0;
}

.help-section ul {
  margin-left: 20px;
}

.help-section li {
  margin-bottom: 10px;
}

.chart-container {
  width: 100%;
  height: 500px;
}

.upload-demo {
  width: 100%;
}

:deep(.el-upload-dragger) {
  width: 100%;
  height: 120px;
}

.batch-input-tabs {
  margin-top: 10px;
}

.stock-preview {
  margin-top: 10px;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}

.stock-preview-title {
  font-weight: bold;
  margin-bottom: 8px;
  color: #606266;
}

.stock-list {
  max-height: 80px;
  overflow-y: auto;
  font-family: monospace;
  font-size: 12px;
  line-height: 1.4;
  color: #303133;
  background-color: #fff;
  padding: 8px;
  border-radius: 3px;
  border: 1px solid #dcdfe6;
}

.stock-count {
  margin-top: 5px;
  font-size: 12px;
  color: #909399;
}

.manual-input-hint {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.hint-text {
  color: #909399;
  font-size: 12px;
}
</style>
